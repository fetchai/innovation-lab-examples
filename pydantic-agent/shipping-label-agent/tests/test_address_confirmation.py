"""The address-correction confirmation step (``AWAITING_SENDER_CONFIRM`` /
``AWAITING_PACKAGE_CONFIRM``).

Shippo's own address validator can call an address "valid" (deliverable)
while silently normalizing something the user typed wrong - most concretely,
a city that doesn't match its own ZIP (e.g. "Irvine" for a ZIP whose
USPS-preferred city is "Tustin"). That slipped straight through the old
"is_valid or bounce back to the form" check, only to fail later - after
money had already changed hands - when the carrier's own stricter address
validator rejected it at label-purchase time.

These tests cover the fix end to end: a correction pauses the flow with a
real ``review`` card offering "use suggested" vs "keep as typed", for both
the sender (ship-from) and recipient (package) addresses, plus the
fail-open behavior when Shippo's validation call itself errors.
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
from session_state import (
    AWAITING_PACKAGE,
    AWAITING_PACKAGE_CONFIRM,
    AWAITING_SENDER,
    AWAITING_SENDER_CONFIRM,
    SHOWING_RATES,
    default_state,
    save_state,
)

SENDER = "agent1qbuyer"

VALID_SENDER_SELECTION = {
    "action": "submit_sender",
    "from_name": "Phu Quach",
    "from_street1": "30 Preston Pl",
    "from_city": "Irvine",
    "from_state": "CA",
    "from_zip": "92782",
    "from_phone": "+1 555 111 2222",
    "from_email": "phu@example.com",
}

_SAVED_SENDER_PROFILE = {
    "from_name": "Phu Quach",
    "from_street1": "30 Preston Pl",
    "from_city": "Irvine",
    "from_state": "CA",
    "from_zip": "92782",
    "from_country": "US",
    "from_phone": "+1 555 111 2222",
    "from_email": "phu@example.com",
}

VALID_PACKAGE_SELECTION = {
    "action": "submit_package",
    "to_name": "Aditya Lagad",
    "to_street1": "99 Monroe Ave NW",
    "to_city": "Irvine",
    "to_state": "CA",
    "to_zip": "92782",
    "weight_lb": 2,
    "length_in": 12,
    "width_in": 9,
    "height_in": 4,
}


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

    def warning(self, *_: object) -> None:
        pass

    def error(self, *_: object) -> None:
        pass


class FakeContext:
    def __init__(self) -> None:
        self.session = "session-123"
        self.agent = SimpleNamespace(address="agent1qseller")
        self.storage = _FakeStorage()
        self.logger = _FakeLogger()
        self.sent: list[Any] = []

    async def send(self, _sender: str, message: Any) -> None:
        self.sent.append(message)


def _corrected_address_handler(request: httpx.Request) -> httpx.Response:
    """A "valid, but here's a normalized version" response - the Irvine/Tustin
    case that started this whole investigation."""
    return httpx.Response(
        201,
        json={
            "object_id": "addr_ok",
            "is_complete": True,
            "validation_results": {"is_valid": True, "messages": []},
            "name": "placeholder",
            "street1": "30 Preston Pl",
            "city": "Tustin",
            "state": "CA",
            "zip": "92782",
            "country": "US",
        },
    )


def _exact_match_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "object_id": "addr_ok",
            "is_complete": True,
            "validation_results": {"is_valid": True, "messages": []},
        },
    )


def _erroring_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, text="Shippo is down")


def _rate_shop_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "object_id": "ship_1",
            "status": "SUCCESS",
            "test": True,
            "rates": [
                {
                    "object_id": "r1",
                    "provider": "USPS",
                    "servicelevel": {"name": "Priority", "token": "usps_priority"},
                    "amount": "9.50",
                    "currency": "USD",
                    "estimated_days": 3,
                    "test": True,
                }
            ],
        },
    )


def _patch_shippo_client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    def _fake_shippo_client() -> chat_proto.ShippoClient:
        http = httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.goshippo.com"
        )
        return chat_proto.ShippoClient("shippo_test_dummy_token", client=http)

    monkeypatch.setattr(chat_proto, "shippo_client", _fake_shippo_client)


def _last_card_payload(ctx: FakeContext) -> dict[str, Any]:
    payloads = [c.metadata for m in ctx.sent for c in m.content if hasattr(c, "metadata")]
    return json.loads(payloads[-1]["card_payload"])


def _last_card_kind(ctx: FakeContext) -> str:
    payloads = [c.metadata for m in ctx.sent for c in m.content if hasattr(c, "metadata")]
    return str(payloads[-1]["card_kind"])


# sender address correction
async def test_sender_address_with_corrected_city_pauses_for_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shippo_client(monkeypatch, _corrected_address_handler)
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_stage(ctx, SENDER, state, "", VALID_SENDER_SELECTION)

    assert state["state"] == AWAITING_SENDER_CONFIRM
    assert state["sender_profile"] is None  # not committed yet
    assert _last_card_kind(ctx) == "review"
    payload = _last_card_payload(ctx)
    rows = {row["label"]: row["value"] for row in payload["summary_rows"]}
    assert "Irvine" in rows["You entered"]
    assert "Tustin" in rows["Suggested (USPS-verified)"]
    assert payload["approve_cta"]["selection"]["action"] == "use_suggested_address"
    assert payload["reject_cta"]["selection"]["action"] == "keep_typed_address"


async def test_sender_confirm_use_suggested_applies_the_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER_CONFIRM
    state["stripe_paid"] = True
    state["pending_sender_typed"] = _SAVED_SENDER_PROFILE
    state["pending_sender_corrected"] = {
        "name": "placeholder",
        "street1": "30 Preston Pl",
        "street2": "",
        "city": "Tustin",
        "state": "CA",
        "zip": "92782",
        "country": "US",
        "phone": "",
        "email": "",
    }
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_confirm_stage(
        ctx, SENDER, state, {"action": "use_suggested_address"}
    )

    assert state["state"] == AWAITING_PACKAGE
    assert state["sender_profile"]["from_city"] == "Tustin"
    assert "pending_sender_typed" not in state or state.get("pending_sender_typed") is None


async def test_sender_confirm_keep_typed_preserves_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER_CONFIRM
    state["stripe_paid"] = True
    state["pending_sender_typed"] = _SAVED_SENDER_PROFILE
    state["pending_sender_corrected"] = {
        "name": "placeholder",
        "street1": "30 Preston Pl",
        "street2": "",
        "city": "Tustin",
        "state": "CA",
        "zip": "92782",
        "country": "US",
        "phone": "",
        "email": "",
    }
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_confirm_stage(
        ctx, SENDER, state, {"action": "keep_typed_address"}
    )

    assert state["state"] == AWAITING_PACKAGE
    assert state["sender_profile"]["from_city"] == "Irvine"


async def test_sender_confirm_unclear_reply_re_shows_the_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER_CONFIRM
    state["stripe_paid"] = True
    state["pending_sender_typed"] = _SAVED_SENDER_PROFILE
    state["pending_sender_corrected"] = {
        "name": "placeholder",
        "street1": "30 Preston Pl",
        "street2": "",
        "city": "Tustin",
        "state": "CA",
        "zip": "92782",
        "country": "US",
        "phone": "",
        "email": "",
    }
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_confirm_stage(ctx, SENDER, state, {})

    assert state["state"] == AWAITING_SENDER_CONFIRM  # unchanged, still pending
    assert _last_card_kind(ctx) == "review"


async def test_sender_validation_outage_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Shippo outage during validation must not dead-end the whole demo -
    the user already typed a complete address, so proceed with it."""
    _patch_shippo_client(monkeypatch, _erroring_handler)
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_stage(ctx, SENDER, state, "", VALID_SENDER_SELECTION)

    assert state["state"] == AWAITING_PACKAGE
    assert state["sender_profile"]["from_name"] == "Phu Quach"


# recipient (package) address correction
def _state_with_sender(stage: str) -> dict[str, Any]:
    state = default_state()
    state["state"] = stage
    state["stripe_paid"] = True
    state["sender_profile"] = _SAVED_SENDER_PROFILE
    return state


async def test_package_address_with_corrected_city_pauses_for_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shippo_client(monkeypatch, _corrected_address_handler)
    ctx = FakeContext()
    state = _state_with_sender(AWAITING_PACKAGE)
    save_state(ctx, SENDER, state)

    await chat_proto._handle_package_stage(ctx, SENDER, state, "", VALID_PACKAGE_SELECTION)

    assert state["state"] == AWAITING_PACKAGE_CONFIRM
    assert state["package"] is None  # not committed / rate-shopped yet
    assert _last_card_kind(ctx) == "review"


async def test_package_confirm_use_suggested_then_rate_shops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shippo_client(monkeypatch, _rate_shop_handler)
    ctx = FakeContext()
    state = _state_with_sender(AWAITING_PACKAGE_CONFIRM)
    state["pending_package_typed"] = {
        "to_name": "Aditya Lagad",
        "to_street1": "99 Monroe Ave NW",
        "to_city": "Irvine",
        "to_state": "CA",
        "to_zip": "92782",
        "to_country": "US",
        "weight_lb": 2,
        "length_in": 12,
        "width_in": 9,
        "height_in": 4,
        "declared_value_usd": 0,
    }
    state["pending_package_corrected"] = {
        "name": "placeholder",
        "street1": "99 Monroe Ave NW",
        "street2": "",
        "city": "Tustin",
        "state": "CA",
        "zip": "92782",
        "country": "US",
        "phone": "",
        "email": "",
    }
    save_state(ctx, SENDER, state)

    await chat_proto._handle_package_confirm_stage(
        ctx, SENDER, state, {"action": "use_suggested_address"}
    )

    assert state["state"] == SHOWING_RATES
    assert state["package"]["to_city"] == "Tustin"
    assert len(state["rates"]) == 1


async def test_package_validation_outage_fails_open_into_rate_shop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/addresses/":
            return _erroring_handler(request)
        return _rate_shop_handler(request)

    _patch_shippo_client(monkeypatch, handler)
    ctx = FakeContext()
    state = _state_with_sender(AWAITING_PACKAGE)
    save_state(ctx, SENDER, state)

    await chat_proto._handle_package_stage(ctx, SENDER, state, "", VALID_PACKAGE_SELECTION)

    assert state["state"] == SHOWING_RATES
    assert "/addresses/" in calls
    assert "/shipments/" in calls


async def test_no_correction_needed_when_address_matches_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The common case - no mismatch - must not be interrupted by a
    confirmation step at all."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/addresses/":
            return _exact_match_handler(request)
        return _rate_shop_handler(request)

    _patch_shippo_client(monkeypatch, handler)
    ctx = FakeContext()
    state = _state_with_sender(AWAITING_PACKAGE)
    save_state(ctx, SENDER, state)

    await chat_proto._handle_package_stage(ctx, SENDER, state, "", VALID_PACKAGE_SELECTION)

    assert state["state"] == SHOWING_RATES
