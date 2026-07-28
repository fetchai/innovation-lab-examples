"""The sender-profile intake step (``AWAITING_SENDER``).

Before this, the ship-from address was a single hard-coded demo constant the
user was never asked about - a real gap, since a "shopping" agent that never
learns where *you* are shipping from isn't usable beyond this one demo
persona. This verifies the fix: right after payment, the agent asks for the
user's own ship-from address in a dedicated form, kept completely separate
from the recipient form, validates it through Shippo the same way the
recipient address is validated, and only then moves on to package intake.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("uagents")
pytest.importorskip("pydantic_ai")
pytest.importorskip("httpx")

import httpx
from pydantic_ai.models.test import TestModel

import chat_proto
from pydantic_agent import SenderProfile, extract_sender_profile
from session_state import AWAITING_PACKAGE, AWAITING_SENDER, default_state, save_state

VALID_SENDER_SELECTION = {
    "action": "submit_sender",
    "from_name": "Jane Sender",
    "from_street1": "1 Market St.",
    "from_city": "San Francisco",
    "from_state": "CA",
    "from_zip": "94105",
    "from_phone": "+1 555 111 2222",
    "from_email": "jane@example.com",
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


def _valid_address_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "object_id": "addr_ok",
            "is_complete": True,
            "validation_results": {"is_valid": True, "messages": []},
        },
    )


def _invalid_address_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "object_id": "addr_bad",
            "is_complete": False,
            "validation_results": {
                "is_valid": False,
                "messages": [{"text": "Unable to find a valid city, state or 5-digit zip."}],
            },
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


SENDER = "agent1qbuyer"


async def test_valid_sender_form_moves_to_package_intake(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_shippo_client(monkeypatch, _valid_address_handler)
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_stage(ctx, SENDER, state, "", VALID_SENDER_SELECTION)

    assert state["state"] == AWAITING_PACKAGE
    assert state["sender_profile"]["from_name"] == "Jane Sender"
    # The next thing sent must be the package (recipient) form, not another
    # sender form or a payment prompt.
    payloads = [c.metadata for m in ctx.sent for c in m.content if hasattr(c, "metadata")]
    assert payloads[-1]["card_kind"] == "form"
    import json as _json

    assert _json.loads(payloads[-1]["card_payload"])["title"] == "Package details"


async def test_invalid_sender_address_resends_the_sender_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_shippo_client(monkeypatch, _invalid_address_handler)
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)

    await chat_proto._handle_sender_stage(ctx, SENDER, state, "", VALID_SENDER_SELECTION)

    assert state["state"] == AWAITING_SENDER  # not advanced
    assert state["sender_profile"] is None
    payloads = [c.metadata for m in ctx.sent for c in m.content if hasattr(c, "metadata")]
    assert payloads[-1]["card_kind"] == "form"
    import json as _json

    assert _json.loads(payloads[-1]["card_payload"])["title"] == "Your shipping profile"


async def test_sender_missing_email_or_phone_resends_the_form_before_any_shippo_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: USPS rejects the label *purchase* call (not the earlier
    rate-shop or address-validation calls) if the sender's phone/email are
    blank - which used to only surface after a second Stripe charge had
    already cleared. Missing contact info must be caught here instead, and
    Shippo must never even be called."""
    calls: list[str] = []

    def counting_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return _valid_address_handler(request)

    _patch_shippo_client(monkeypatch, counting_handler)
    ctx = FakeContext()
    state = default_state()
    state["state"] = AWAITING_SENDER
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)

    selection = dict(VALID_SENDER_SELECTION)
    del selection["from_email"]
    del selection["from_phone"]

    await chat_proto._handle_sender_stage(ctx, SENDER, state, "", selection)

    assert state["state"] == AWAITING_SENDER  # not advanced
    assert state["sender_profile"] is None
    assert calls == []  # Shippo was never called
    payloads = [c.metadata for m in ctx.sent for c in m.content if hasattr(c, "metadata")]
    assert payloads[-1]["card_kind"] == "form"
    texts = [c.text for m in ctx.sent for c in m.content if hasattr(c, "text")]
    assert any("email" in t and "phone" in t for t in texts)


async def test_sender_form_requires_phone_and_email_fields() -> None:
    """The form itself must ask for both - not just accept them if typed."""
    import json

    payload = json.loads(chat_proto.sender_profile_form_card()["card_payload"])
    fields = {f["name"]: f for f in payload["fields"]}
    assert fields["from_phone"]["required"] is True
    assert fields["from_email"]["required"] is True


async def test_sender_form_never_reuses_recipient_style_fields() -> None:
    """The sender and recipient forms must be genuinely separate schemas -
    the sender form has no ``to_*`` fields at all."""
    import json

    payload = json.loads(chat_proto.sender_profile_form_card()["card_payload"])
    field_names = {f["name"] for f in payload["fields"]}
    assert not any(name.startswith("to_") for name in field_names)


async def test_extract_sender_profile_offline() -> None:
    profile: SenderProfile = await extract_sender_profile(
        "I'm Jane Sender at 1 Market St, San Francisco, CA 94105.",
        model=TestModel(),
    )
    assert isinstance(profile, SenderProfile)
    assert profile.from_name
