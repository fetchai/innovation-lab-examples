"""Hazmat self-certification and optional-insurance gates.

Both fire per shipment, after a rate is picked and before the purchase-approval
step. This verifies:

* "Continue to purchase" routes into the hazmat gate (not straight to approval).
* "This needs special handling" stops the purchase and links the two
  carrier-specific hazmat guides - it never buys a label.
* "Nothing hazardous" skips insurance when the declared value is already
  covered for free, and offers insurance only when it isn't.
* Adding insurance re-quotes the chosen service and carries the higher total
  forward; skipping keeps the base rate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("uagents")
pytest.importorskip("pydantic_ai")
pytest.importorskip("httpx")

import httpx

import chat_proto
import session_state
from shipping import (
    UPS_HAZMAT_GUIDE_URL,
    USPS_HAZMAT_GUIDE_URL,
    RateOption,
    ShippoClient,
)

SENDER = "agent1qbuyer"
TOKEN = "shippo_test_dummy_token"

RATE = RateOption(
    rate_id="r_base",
    provider="USPS",
    servicelevel_name="Ground Advantage",
    servicelevel_token="usps_ground_advantage",
    amount=9.55,
    currency="USD",
    estimated_days=3,
)

_PACKAGE = {
    "to_name": "Mrs Hippo",
    "to_street1": "965 Mission St",
    "to_city": "San Francisco",
    "to_state": "CA",
    "to_zip": "94105",
    "to_country": "US",
    "weight_lb": 2.0,
    "length_in": 5.0,
    "width_in": 5.0,
    "height_in": 5.0,
    "declared_value_usd": 500.0,
}

_SENDER_PROFILE = {
    "from_name": "Jane Sender",
    "from_street1": "1 Market St.",
    "from_city": "San Francisco",
    "from_state": "CA",
    "from_zip": "94105",
    "from_country": "US",
    "from_phone": "",
    "from_email": "",
}


class _FakeStorage:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


class _FakeLogger:
    def info(self, *_: object) -> None: ...
    def error(self, *_: object) -> None: ...
    def warning(self, *_: object) -> None: ...
    def debug(self, *_: object) -> None: ...


class FakeContext:
    def __init__(self) -> None:
        self.session = "session-1"
        self.agent = SimpleNamespace(address="agent1qseller")
        self.storage = _FakeStorage()
        self.logger = _FakeLogger()
        self.sent: list[Any] = []

    async def send(self, _sender: str, message: Any) -> None:
        self.sent.append(message)


def _fake_shippo(handler: Callable[[httpx.Request], httpx.Response]) -> ShippoClient:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.goshippo.com")
    return ShippoClient(TOKEN, client=http)


def _last_card(ctx: FakeContext) -> dict[str, str]:
    metas = [
        c.metadata for m in ctx.sent for c in getattr(m, "content", []) if hasattr(c, "metadata")
    ]
    return metas[-1]


def _last_card_payload(ctx: FakeContext) -> dict[str, Any]:
    return json.loads(_last_card(ctx)["card_payload"])


def _texts(ctx: FakeContext) -> str:
    out: list[str] = []
    for m in ctx.sent:
        for c in getattr(m, "content", []):
            if hasattr(c, "text"):
                out.append(c.text)
    return "\n".join(out)


def _state(stage: str, *, declared: float = 500.0) -> dict[str, Any]:
    state = session_state.default_state()
    state["stripe_paid"] = True
    state["state"] = stage
    state["sender_profile"] = _SENDER_PROFILE
    pkg = dict(_PACKAGE)
    pkg["declared_value_usd"] = declared
    state["package"] = pkg
    state["rates"] = [RATE.model_dump()]
    state["selected_rate_id"] = RATE.rate_id
    return state


# routing into the hazmat gate
async def test_continue_to_purchase_routes_to_hazmat_gate() -> None:
    ctx = FakeContext()
    state = _state(session_state.SHOWING_DETAIL)
    await chat_proto._handle_detail_stage(
        ctx, SENDER, state, {"action": "buy_rate", "rate_id": RATE.rate_id}
    )
    assert state["state"] == session_state.AWAITING_HAZMAT_CHECK
    payload = _last_card_payload(ctx)
    assert _last_card(ctx)["card_kind"] == "review"
    assert payload["approve_cta"]["selection"]["action"] == "hazmat_clear"
    assert payload["reject_cta"]["selection"]["action"] == "hazmat_stop"


# "this needs special handling" -> stop, link both guides, no purchase
async def test_hazmat_special_handling_stops_and_links_guides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    began: list[RateOption] = []

    async def _spy_begin(_ctx: Any, _sender: str, _state: Any, rate: RateOption) -> None:
        began.append(rate)

    monkeypatch.setattr(chat_proto, "_begin_purchase_approval", _spy_begin)
    ctx = FakeContext()
    state = _state(session_state.AWAITING_HAZMAT_CHECK)

    await chat_proto._handle_hazmat_stage(ctx, SENDER, state, "", {"action": "hazmat_stop"})

    assert state["state"] == session_state.DONE
    assert began == []  # never started a purchase
    body = _texts(ctx)
    assert USPS_HAZMAT_GUIDE_URL in body
    assert UPS_HAZMAT_GUIDE_URL in body


# "nothing hazardous" -> insurance gate behavior
async def test_hazmat_clear_skips_insurance_when_declared_value_is_covered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    began: list[RateOption] = []

    async def _spy_begin(_ctx: Any, _sender: str, _state: Any, rate: RateOption) -> None:
        began.append(rate)

    monkeypatch.setattr(chat_proto, "_begin_purchase_approval", _spy_begin)
    ctx = FakeContext()
    state = _state(session_state.AWAITING_HAZMAT_CHECK, declared=50.0)  # <= USPS free $100

    await chat_proto._handle_hazmat_stage(ctx, SENDER, state, "", {"action": "hazmat_clear"})

    assert state["state"] != session_state.AWAITING_INSURANCE_CHECK
    assert began and began[0].rate_id == RATE.rate_id  # went straight to approval


async def test_hazmat_clear_offers_insurance_when_underinsured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    began: list[RateOption] = []

    async def _spy_begin(_ctx: Any, _sender: str, _state: Any, rate: RateOption) -> None:
        began.append(rate)

    monkeypatch.setattr(chat_proto, "_begin_purchase_approval", _spy_begin)
    ctx = FakeContext()
    state = _state(session_state.AWAITING_HAZMAT_CHECK, declared=500.0)  # > USPS free $100

    await chat_proto._handle_hazmat_stage(ctx, SENDER, state, "", {"action": "hazmat_clear"})

    assert state["state"] == session_state.AWAITING_INSURANCE_CHECK
    assert began == []
    payload = _last_card_payload(ctx)
    assert payload["approve_cta"]["selection"]["action"] == "add_insurance"
    # 1.25% of $500 = $6.25.
    assert "6.25" in payload["approve_cta"]["label"]


# insurance decision
async def test_skip_insurance_keeps_base_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    began: list[RateOption] = []

    async def _spy_begin(_ctx: Any, _sender: str, _state: Any, rate: RateOption) -> None:
        began.append(rate)

    monkeypatch.setattr(chat_proto, "_begin_purchase_approval", _spy_begin)
    ctx = FakeContext()
    state = _state(session_state.AWAITING_INSURANCE_CHECK)

    await chat_proto._handle_insurance_stage(ctx, SENDER, state, "", {"action": "skip_insurance"})

    assert began and began[0].amount == RATE.amount
    assert began[0].included_insurance_price == 0.0


async def test_add_insurance_requotes_and_raises_total(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mode usually returns no ``included_insurance_price``; the documented
    1.25% domestic premium is added on top of the base price instead."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        assert body["extra"]["insurance"]["amount"] == "500.00"
        return httpx.Response(
            201,
            json={
                "object_id": "ship_ins",
                "status": "SUCCESS",
                "test": True,
                "rates": [
                    {
                        "object_id": "r_insured",
                        "provider": "USPS",
                        "servicelevel": {
                            "name": "Ground Advantage",
                            "token": "usps_ground_advantage",
                        },
                        "amount": "9.55",  # test mode: unchanged, no included price
                        "currency": "USD",
                        "estimated_days": 3,
                        "test": True,
                    }
                ],
            },
        )

    monkeypatch.setattr(chat_proto, "shippo_client", lambda: _fake_shippo(handler))
    began: list[RateOption] = []

    async def _spy_begin(_ctx: Any, _sender: str, _state: Any, rate: RateOption) -> None:
        began.append(rate)

    monkeypatch.setattr(chat_proto, "_begin_purchase_approval", _spy_begin)
    ctx = FakeContext()
    state = _state(session_state.AWAITING_INSURANCE_CHECK, declared=500.0)

    await chat_proto._handle_insurance_stage(ctx, SENDER, state, "", {"action": "add_insurance"})

    assert began, "purchase approval should begin after adding insurance"
    insured = began[0]
    assert insured.included_insurance_price == 6.25
    assert insured.amount == round(9.55 + 6.25, 2)


async def test_add_insurance_trusts_shippo_included_price_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "object_id": "ship_ins",
                "status": "SUCCESS",
                "test": True,
                "rates": [
                    {
                        "object_id": "r_insured",
                        "provider": "USPS",
                        "servicelevel": {
                            "name": "Ground Advantage",
                            "token": "usps_ground_advantage",
                        },
                        "amount": "13.55",  # Shippo folded the premium in
                        "currency": "USD",
                        "estimated_days": 3,
                        "included_insurance_price": "4.00",
                        "test": True,
                    }
                ],
            },
        )

    monkeypatch.setattr(chat_proto, "shippo_client", lambda: _fake_shippo(handler))
    began: list[RateOption] = []

    async def _spy_begin(_ctx: Any, _sender: str, _state: Any, rate: RateOption) -> None:
        began.append(rate)

    monkeypatch.setattr(chat_proto, "_begin_purchase_approval", _spy_begin)
    ctx = FakeContext()
    state = _state(session_state.AWAITING_INSURANCE_CHECK, declared=500.0)

    await chat_proto._handle_insurance_stage(ctx, SENDER, state, "", {"action": "add_insurance"})

    assert began
    assert began[0].amount == 13.55
    assert began[0].included_insurance_price == 4.00
