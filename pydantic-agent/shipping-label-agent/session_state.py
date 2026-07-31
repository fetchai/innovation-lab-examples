from __future__ import annotations

import json
from typing import Any

from uagents import Context

UNINITIALIZED = "UNINITIALIZED"
AWAITING_PAYMENT = "AWAITING_PAYMENT"
AWAITING_SENDER = "AWAITING_SENDER"
AWAITING_SENDER_CONFIRM = "AWAITING_SENDER_CONFIRM"
AWAITING_PACKAGE = "AWAITING_PACKAGE"
AWAITING_PACKAGE_CONFIRM = "AWAITING_PACKAGE_CONFIRM"
SHOWING_RATES = "SHOWING_RATES"
SHOWING_DETAIL = "SHOWING_DETAIL"
AWAITING_HAZMAT_CHECK = "AWAITING_HAZMAT_CHECK"
AWAITING_INSURANCE_CHECK = "AWAITING_INSURANCE_CHECK"
AWAITING_PURCHASE_APPROVAL = "AWAITING_PURCHASE_APPROVAL"
AWAITING_LABEL_PAYMENT = "AWAITING_LABEL_PAYMENT"
AWAITING_PICKUP = "AWAITING_PICKUP"
DONE = "DONE"

_SESSION_KEY = "session:{}"


def default_state() -> dict[str, Any]:
    return {
        "state": UNINITIALIZED,
        "stripe_session_id": None,
        "stripe_paid": False,
        "payment_purpose": "gate",
        "sender_profile": None,
        "pending_sender_typed": None,
        "pending_sender_corrected": None,
        "package": None,
        "pending_package_typed": None,
        "pending_package_corrected": None,
        "rates": [],
        "selected_rate_id": None,
        "purchase_history_json": None,
        "purchase_tool_call_id": None,
        "purchase": None,
    }


def get_state(ctx: Context, sender: str) -> dict[str, Any]:
    raw = ctx.storage.get(_SESSION_KEY.format(sender))
    if not raw:
        return default_state()
    try:
        data: dict[str, Any] = json.loads(raw)
        return data
    except (TypeError, json.JSONDecodeError):
        return default_state()


def save_state(ctx: Context, sender: str, data: dict[str, Any]) -> None:
    ctx.storage.set(_SESSION_KEY.format(sender), json.dumps(data))


_WINDOW_KEY = "chat:window:{}"


def check_new_window_and_reset(ctx: Context, sender: str) -> None:
    """Force a full session reset when a message arrives on a new chat window.

    ``ctx.storage`` is keyed purely by ``sender``, and ASI:One reuses the same
    ``sender`` address across a user's separate chat conversations - so without
    this, starting a brand-new chat would silently resume an already-paid
    session from a previous, unrelated conversation instead of asking to pay
    again. ``ctx.session`` changes per chat window, so comparing it against the
    last-seen value lets each new conversation start truly fresh. Mirrors
    quiz-agent's identical "hackflow pattern" fix.
    """
    current_window = str(ctx.session)
    stored_window = ctx.storage.get(_WINDOW_KEY.format(sender))
    if stored_window and stored_window != current_window:
        save_state(ctx, sender, default_state())
    ctx.storage.set(_WINDOW_KEY.format(sender), current_window)
