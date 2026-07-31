"""Native payment-protocol tests: the actual mechanism ASI:One renders natively.

This is the fix for the bug where the agent sent a hand-rolled ``review`` card
with a raw checkout URL dumped into chat text, instead of the native
``uagents_core.contrib.protocols.payment`` messages the quiz-agent uses (which
ASI:One renders as its own "Pay with Stripe / Reject" sheet).

Verifies:

* ``request_payment`` sends ONLY a bare ``RequestPayment`` (no narration text) -
  any accompanying text causes ASI:One to swallow the native card.
* ``on_commit`` grants access (sends the package form) only once Stripe actually
  shows the checkout as paid; otherwise it replies with ``RejectPayment``.
* ``on_reject`` resets the session back to the payment gate.

No network: the Stripe SDK is replaced with a small in-memory fake, exactly
like ``test_payment.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

# Skip cleanly (rather than erroring collection) if run outside the example venv.
# pydantic_ai is required too: on_commit's grant-access path lazily imports
# chat_proto, which in turn imports pydantic_agent (pydantic_ai-based).
pytest.importorskip("uagents")
pytest.importorskip("pydantic_ai")
pytest.importorskip("httpx")

from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    RejectPayment,
    RequestPayment,
)

import payment
import session_state


class _FakeSession:
    def __init__(self, session_id: str, payment_status: str) -> None:
        self.id = session_id
        self.client_secret = "cs_secret_test"
        self.payment_status = payment_status


class FakeStripe:
    def __init__(self) -> None:
        self._sessions: dict[str, _FakeSession] = {}
        self._next = ("cs_test_ok", "paid")
        self.checkout = SimpleNamespace(
            Session=SimpleNamespace(create=self._create, retrieve=self._retrieve)
        )

    def set_next(self, session_id: str, payment_status: str) -> None:
        self._next = (session_id, payment_status)

    def seed(self, session_id: str, payment_status: str) -> None:
        """Directly register a session as retrievable, bypassing ``create``."""
        self._sessions[session_id] = _FakeSession(session_id, payment_status)

    def _create(self, **_: object) -> _FakeSession:
        session_id, status = self._next
        session = _FakeSession(session_id, status)
        self._sessions[session_id] = session
        return session

    def _retrieve(self, session_id: str) -> _FakeSession:
        return self._sessions.get(session_id, _FakeSession(session_id, "unpaid"))


class FakeStorage:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


class FakeLogger:
    def info(self, *_: object) -> None:
        pass

    def error(self, *_: object) -> None:
        pass

    def warning(self, *_: object) -> None:
        pass


class FakeContext:
    """Just enough of ``uagents.Context`` for the payment protocol handlers."""

    def __init__(self) -> None:
        self.session = "session-123"
        self.agent = SimpleNamespace(address="agent1qseller")
        self.storage = FakeStorage()
        self.logger = FakeLogger()
        self.sent: list[Any] = []

    async def send(self, _sender: str, message: Any) -> None:
        self.sent.append(message)


@pytest.fixture()
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(payment, "_stripe", lambda: fake)
    return fake


async def test_request_payment_sends_only_request_payment(fake_stripe: FakeStripe) -> None:
    """No text/card may accompany RequestPayment, or ASI:One swallows the card."""
    ctx = FakeContext()
    state_data = session_state.default_state()

    await payment.request_payment(ctx, "agent1qbuyer", state_data)

    assert len(ctx.sent) == 1
    assert isinstance(ctx.sent[0], RequestPayment)
    assert state_data["state"] == session_state.AWAITING_PAYMENT
    assert state_data["stripe_session_id"] == "cs_test_ok"


async def test_on_commit_rejects_when_stripe_shows_unpaid(fake_stripe: FakeStripe) -> None:
    ctx = FakeContext()
    state_data = session_state.default_state()
    state_data["stripe_session_id"] = "cs_never_paid"
    session_state.save_state(ctx, "agent1qbuyer", state_data)

    await payment.on_commit(
        ctx,
        "agent1qbuyer",
        CommitPayment(
            funds={"amount": "5.00", "currency": "USD", "payment_method": "stripe"},
            recipient="agent1qseller",
            transaction_id="pi_test_1",
        ),
    )

    assert len(ctx.sent) == 1
    assert isinstance(ctx.sent[0], RejectPayment)
    reloaded = session_state.get_state(ctx, "agent1qbuyer")
    assert reloaded.get("stripe_paid") is not True


async def test_on_commit_grants_access_when_paid(fake_stripe: FakeStripe) -> None:
    fake_stripe.seed("cs_test_paid", "paid")
    ctx = FakeContext()
    state_data = session_state.default_state()
    state_data["stripe_session_id"] = "cs_test_paid"
    session_state.save_state(ctx, "agent1qbuyer", state_data)

    await payment.on_commit(
        ctx,
        "agent1qbuyer",
        CommitPayment(
            funds={"amount": "5.00", "currency": "USD", "payment_method": "stripe"},
            recipient="agent1qseller",
            transaction_id="pi_test_2",
        ),
    )

    kinds = [type(m).__name__ for m in ctx.sent]
    assert "CompletePayment" in kinds
    reloaded = session_state.get_state(ctx, "agent1qbuyer")
    assert reloaded["stripe_paid"] is True
    assert reloaded["state"] == session_state.AWAITING_SENDER


async def test_on_reject_resets_to_payment_gate() -> None:
    ctx = FakeContext()
    state_data = session_state.default_state()
    state_data["state"] = session_state.AWAITING_PACKAGE
    state_data["stripe_paid"] = True
    session_state.save_state(ctx, "agent1qbuyer", state_data)

    await payment.on_reject(ctx, "agent1qbuyer", RejectPayment(reason="cancelled"))

    reloaded = session_state.get_state(ctx, "agent1qbuyer")
    assert reloaded["state"] == session_state.AWAITING_PAYMENT
    assert reloaded["stripe_paid"] is False


async def test_confirm_payment_via_text_false_without_checkout() -> None:
    ctx = FakeContext()
    assert await payment.confirm_payment_via_text(ctx, "agent1qbuyer") is False
