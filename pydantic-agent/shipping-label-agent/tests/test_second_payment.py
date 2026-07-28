"""The second, separate Stripe payment for the label's exact price.

Before this fix, "Confirm and buy label" only resumed Pydantic AI's
``requires_approval`` gate and bought the label immediately - nothing ever
charged the user for the label itself, so only the flat intake fee ever moved
any money. This verifies the fix:

* Approving the purchase review card does NOT buy the label - it starts a
  second, separate Stripe ``RequestPayment`` for the exact rate price, and
  the deferred tool is left pending.
* A successful second payment (``handle_label_payment_success``) is what
  actually resumes the tool with ``approved=True`` and buys the label.
* A failed/declined second payment (``handle_label_payment_failed``) resumes
  the tool with ``approved=False`` - the Shippo transaction endpoint is never
  called - and sends the user back to rate-picking, not to a purchased label.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

# Skip cleanly (rather than erroring collection) if run outside the example venv.
pytest.importorskip("uagents")
pytest.importorskip("pydantic_ai")
pytest.importorskip("httpx")

import httpx
from pydantic_ai import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from uagents_core.contrib.protocols.payment import RequestPayment

import chat_proto
import payment
import session_state
from pydantic_agent import start_purchase
from shipping import RateOption, ShippoClient

TOKEN = "shippo_test_dummy_token"
RATE = RateOption(
    rate_id="r_ups_ground_saver",
    provider="UPS",
    servicelevel_name="Ground Saver",
    servicelevel_token="ups_ground_saver",
    amount=14.01,
    currency="USD",
)


def _fake_shippo(handler: Callable[[httpx.Request], httpx.Response]) -> ShippoClient:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.goshippo.com")
    return ShippoClient(TOKEN, client=http)


def _successful_transaction_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "object_id": "txn_42",
            "status": "SUCCESS",
            "test": True,
            "label_url": "https://deliver.goshippo.com/txn_42.pdf",
            "tracking_number": "1Z999AA10123456784",
            "rate": "819282d7ec8d4b1db3d03bbf8f0e1a7d",  # unexpanded, like real Shippo
            "messages": [],
        },
    )


def _purchase_script(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    for message in messages:
        for part in getattr(message, "parts", []):
            if part.__class__.__name__ == "ToolReturnPart":
                return ModelResponse(parts=[TextPart("Done — the test label was purchased.")])
    return ModelResponse(parts=[ToolCallPart("purchase_label", {"rate_id": RATE.rate_id})])


class _FakeStripeSession:
    def __init__(self, session_id: str, payment_status: str) -> None:
        self.id = session_id
        self.client_secret = "cs_secret_test"
        self.payment_status = payment_status


class FakeStripe:
    def __init__(self) -> None:
        self._sessions: dict[str, _FakeStripeSession] = {}
        self._next = ("cs_test_ok", "paid")
        self.checkout = SimpleNamespace(
            Session=SimpleNamespace(create=self._create, retrieve=self._retrieve)
        )

    def set_next(self, session_id: str, payment_status: str) -> None:
        self._next = (session_id, payment_status)

    def _create(self, **_: object) -> _FakeStripeSession:
        session_id, status = self._next
        session = _FakeStripeSession(session_id, status)
        self._sessions[session_id] = session
        return session

    def _retrieve(self, session_id: str) -> _FakeStripeSession:
        return self._sessions.get(session_id, _FakeStripeSession(session_id, "unpaid"))


class FakeContext:
    def __init__(self) -> None:
        self.session = "session-123"
        self.agent = SimpleNamespace(address="agent1qseller")
        self.storage = _FakeStorage()
        self.logger = _FakeLogger()
        self.sent: list[Any] = []

    async def send(self, _sender: str, message: Any) -> None:
        self.sent.append(message)


class _FakeStorage:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


class _FakeLogger:
    def info(self, *_: object) -> None:
        pass

    def error(self, *_: object) -> None:
        pass

    def warning(self, *_: object) -> None:
        pass


@pytest.fixture()
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(payment, "_stripe", lambda: fake)
    return fake


async def _deferred_state(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A session state as it would look right after the review card is sent -
    the deferred tool is pending, waiting on an approval decision."""
    monkeypatch.setattr(
        chat_proto, "shippo_client", lambda: _fake_shippo(_successful_transaction_handler)
    )
    from pydantic_agent import ShippingDeps

    deps = ShippingDeps(shippo=_fake_shippo(_successful_transaction_handler), selected_rate=RATE)
    model = FunctionModel(_purchase_script)
    start = await start_purchase(deps, RATE.rate_id, model=model)

    state_data = session_state.default_state()
    state_data["stripe_paid"] = True
    state_data["state"] = session_state.AWAITING_PURCHASE_APPROVAL
    state_data["rates"] = [RATE.model_dump()]
    state_data["selected_rate_id"] = RATE.rate_id
    state_data["purchase_history_json"] = start.history_json
    state_data["purchase_tool_call_id"] = start.tool_call_id
    return state_data


async def test_approving_purchase_does_not_buy_the_label_it_charges_first(
    monkeypatch: pytest.MonkeyPatch, fake_stripe: FakeStripe
) -> None:
    """The old bug: approving went straight to a real Shippo purchase with no
    payment for the label price. Now it must only request a second charge."""
    calls: list[str] = []

    def counting_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return _successful_transaction_handler(request)

    monkeypatch.setattr(chat_proto, "shippo_client", lambda: _fake_shippo(counting_handler))
    fake_stripe.set_next("cs_test_label_ok", "paid")

    state_data = await _deferred_state(monkeypatch)
    ctx = FakeContext()

    await chat_proto._handle_approval_stage(
        ctx, "agent1qbuyer", state_data, {"action": "approve_purchase"}
    )

    assert "/transactions/" not in calls  # Shippo was NOT charged/called yet
    assert len(ctx.sent) == 1
    assert isinstance(ctx.sent[0], RequestPayment)
    assert state_data["state"] == session_state.AWAITING_LABEL_PAYMENT
    assert state_data["payment_purpose"] == "label"
    # The charge must be for the exact rate price, not the flat intake fee.
    assert ctx.sent[0].accepted_funds[0].amount == "14.01"


async def test_second_payment_success_buys_the_label(
    monkeypatch: pytest.MonkeyPatch, fake_stripe: FakeStripe
) -> None:
    monkeypatch.setattr(
        chat_proto, "shippo_client", lambda: _fake_shippo(_successful_transaction_handler)
    )
    state_data = await _deferred_state(monkeypatch)
    ctx = FakeContext()

    await chat_proto.handle_label_payment_success(ctx, "agent1qbuyer", state_data)

    assert state_data["purchase"] is not None
    assert state_data["purchase"]["status"] == "SUCCESS"
    # UPS Ground Saver doesn't support API pickups -> straight to DONE + confirmation.
    assert state_data["state"] == session_state.DONE
    texts = [m for m in ctx.sent if hasattr(m, "content")]
    assert texts  # label link + drop-off note + confirmation card were sent


async def test_second_payment_failure_cancels_purchase_and_returns_to_rates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def counting_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return _successful_transaction_handler(request)

    monkeypatch.setattr(chat_proto, "shippo_client", lambda: _fake_shippo(counting_handler))
    state_data = await _deferred_state(monkeypatch)
    ctx = FakeContext()

    await chat_proto.handle_label_payment_failed(ctx, "agent1qbuyer", state_data)

    assert "/transactions/" not in calls  # the label was never purchased
    assert state_data.get("purchase") in (None, {})
    assert state_data["state"] == session_state.SHOWING_RATES
    assert len(ctx.sent) == 1
    sent_metadata = [c for c in ctx.sent[0].content if hasattr(c, "metadata")]
    assert sent_metadata and sent_metadata[0].metadata["card_kind"] == "carousel"


async def test_on_reject_during_label_payment_cancels_purchase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A RejectPayment while awaiting the label charge must not leave a
    dangling deferred tool or a purchase - it must fall through to the same
    cancel-and-return-to-rates path as a failed payment."""
    from uagents_core.contrib.protocols.payment import RejectPayment

    monkeypatch.setattr(
        chat_proto, "shippo_client", lambda: _fake_shippo(_successful_transaction_handler)
    )
    state_data = await _deferred_state(monkeypatch)
    state_data["payment_purpose"] = "label"
    state_data["state"] = session_state.AWAITING_LABEL_PAYMENT
    ctx = FakeContext()
    session_state.save_state(ctx, "agent1qbuyer", state_data)

    await payment.on_reject(ctx, "agent1qbuyer", RejectPayment(reason="cancelled"))

    reloaded = session_state.get_state(ctx, "agent1qbuyer")
    assert reloaded["state"] == session_state.SHOWING_RATES
    assert reloaded.get("purchase") in (None, {})
