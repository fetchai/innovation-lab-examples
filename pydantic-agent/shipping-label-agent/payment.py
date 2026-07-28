from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from session_state import (
    AWAITING_LABEL_PAYMENT,
    AWAITING_PAYMENT,
    AWAITING_SENDER,
    get_state,
    save_state,
)

STRIPE_TEST_SECRET_PREFIX = "sk_test_"
STRIPE_TEST_PUBLISHABLE_PREFIX = "pk_test_"

# Stripe's documented test cards (https://docs.stripe.com/testing).
TEST_SUCCESS_CARD = "4242424242424242"
TEST_DECLINE_CARD = "4000000000000002"  # generic card_declined

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")


def config() -> dict[str, Any]:
    """Read Stripe config from the environment (test defaults)."""
    return {
        "secret_key": (os.getenv("STRIPE_SECRET_KEY") or "").strip(),
        "publishable_key": (os.getenv("STRIPE_PUBLISHABLE_KEY") or "").strip(),
        "amount_cents": int(os.getenv("STRIPE_AMOUNT_CENTS", "500")),
        "currency": (os.getenv("STRIPE_CURRENCY", "usd") or "usd").lower(),
        "success_url": (
            os.getenv("STRIPE_SUCCESS_URL", "https://agentverse.ai") or "https://agentverse.ai"
        ).rstrip("/"),
    }


def assert_stripe_test_keys() -> None:
    """Fail loudly unless the configured Stripe keys are test keys."""
    c = config()
    secret = c["secret_key"]
    if not secret.startswith(STRIPE_TEST_SECRET_PREFIX):
        raise RuntimeError(
            "STRIPE_SECRET_KEY must be a test key starting with "
            f"'{STRIPE_TEST_SECRET_PREFIX}'. This example is test-mode-only and will "
            "not run with a live key."
        )
    publishable = c["publishable_key"]
    if publishable and not publishable.startswith(STRIPE_TEST_PUBLISHABLE_PREFIX):
        raise RuntimeError(
            "STRIPE_PUBLISHABLE_KEY must be a test key starting with "
            f"'{STRIPE_TEST_PUBLISHABLE_PREFIX}'."
        )


def _stripe() -> Any:
    """Return the configured Stripe SDK module (indirection eases testing)."""
    import stripe as _s

    _s.api_key = config()["secret_key"]
    return _s


def _expires_at() -> int:
    """Checkout expiry, clamped to Stripe's 30 min - 24 h window."""
    sec = int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    return int(time.time()) + max(1800, min(24 * 3600, sec))


def amount_str(amount_cents: int | None = None) -> str:
    """A charge amount as a human string, e.g. ``5.00``."""
    cents = config()["amount_cents"] if amount_cents is None else amount_cents
    return f"{cents / 100:.2f}"


def create_checkout_session(
    sender: str,
    chat_session_id: str,
    amount_cents: int | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Create an **embedded** Stripe Checkout session.

    ``ui_mode="embedded_page"`` is what ASI:One's native payment card renderer
    expects - it uses ``client_secret`` + ``publishable_key`` to mount the
    Stripe form in-place when the user taps "Pay with Stripe", instead of
    bouncing them to a separate hosted checkout page/URL.

    ``amount_cents``/``description`` let a caller charge something other than
    the flat intake fee - e.g. the exact price of the shipping label the user
    picked, once they've chosen a rate.
    """
    c = config()
    s = _stripe()
    amount = c["amount_cents"] if amount_cents is None else amount_cents
    product_name = description or "Shipping Label Agent - service fee"
    return_url = (
        f"{c['success_url']}?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}&user={sender}"
    )
    session = s.checkout.Session.create(
        ui_mode="embedded_page",
        redirect_on_completion="if_required",
        payment_method_types=["card"],
        mode="payment",
        return_url=return_url,
        expires_at=_expires_at(),
        line_items=[
            {
                "price_data": {
                    "currency": c["currency"],
                    "product_data": {"name": product_name},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_address": sender,
            "session_id": chat_session_id,
            "service": "shipping_label",
        },
    )
    return {
        "client_secret": getattr(session, "client_secret", "") or "",
        "id": session.id,
        "checkout_session_id": session.id,
        "publishable_key": c["publishable_key"],
        "currency": c["currency"],
        "amount_cents": str(amount),
        "ui_mode": "embedded_page",
    }


def verify_paid(checkout_session_id: str) -> bool:
    """Return True if the Stripe checkout session is fully paid."""
    if not checkout_session_id:
        return False
    try:
        session = _stripe().checkout.Session.retrieve(checkout_session_id)
        return getattr(session, "payment_status", None) == "paid"
    except Exception:  # noqa: BLE001 - any lookup failure means "not verified as paid"
        return False


async def request_payment(
    ctx: Context,
    sender: str,
    state_data: dict[str, Any],
    *,
    amount_cents: int | None = None,
    description: str | None = None,
    purpose: str = "gate",
) -> None:
    """Create a Stripe checkout, store it, and send a bare ``RequestPayment``.

    Send ONLY ``RequestPayment`` - no text before or after. ASI:One renders the
    native "Pay with Stripe / Reject" card from this message alone; any text
    sent in the same handler call causes ASI:One to swallow the payment card
    and show only the text bubble instead.

    ``purpose`` distinguishes the two charges in this flow: ``"gate"`` is the
    flat intake fee charged on the very first message; ``"label"`` is the
    second, separate charge for the exact price of the label the user picked,
    charged after they approve the purchase and before Shippo is ever called.
    ``on_commit``/``on_reject``/``confirm_payment_via_text`` all branch on
    this stored purpose to resume the right flow.
    """
    checkout = await asyncio.to_thread(
        create_checkout_session, sender, str(ctx.session), amount_cents, description
    )

    state_data["state"] = AWAITING_PAYMENT if purpose == "gate" else AWAITING_LABEL_PAYMENT
    state_data["stripe_session_id"] = checkout["checkout_session_id"]
    state_data["payment_purpose"] = purpose
    save_state(ctx, sender, state_data)

    amount = amount_str(amount_cents)
    default_description = f"Pay ${amount} for one shipping label"
    await ctx.send(
        sender,
        RequestPayment(
            accepted_funds=[Funds(currency="USD", amount=amount, payment_method="stripe")],
            recipient=str(ctx.agent.address),
            deadline_seconds=int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800")),
            reference=str(ctx.session),
            description=description or default_description,
            metadata={"stripe": checkout, "service": "shipping_label", "purpose": purpose},
        ),
    )
    ctx.logger.info(
        f"[payment] RequestPayment({purpose}) -> {sender} | "
        f"checkout={checkout['checkout_session_id']} | ${amount}"
    )


async def confirm_payment_via_text(ctx: Context, sender: str) -> bool:
    """Re-verify the stored checkout when the user types 'paid'/'done'.

    Returns True if payment was confirmed and the matching purpose's success
    path (gate access or label purchase) has run.
    """
    state_data = get_state(ctx, sender)
    checkout_id = state_data.get("stripe_session_id")
    if not checkout_id:
        return False
    paid = await asyncio.to_thread(verify_paid, checkout_id)
    if not paid:
        return False
    await _handle_paid(ctx, sender, state_data)
    return True


async def _handle_paid(ctx: Context, sender: str, state_data: dict[str, Any]) -> None:
    """Dispatch a confirmed payment to the right success path by purpose."""
    if state_data.get("payment_purpose") == "label":
        from chat_proto import handle_label_payment_success

        await handle_label_payment_success(ctx, sender, state_data)
    else:
        await _grant_access(ctx, sender, state_data)


async def _grant_access(ctx: Context, sender: str, state_data: dict[str, Any]) -> None:
    """Mark the session paid and move it into the sender-profile intake."""
    from chat_proto import send_card, sender_profile_form_card

    state_data["stripe_paid"] = True
    state_data["state"] = AWAITING_SENDER
    save_state(ctx, sender, state_data)
    await send_card(
        ctx,
        sender,
        "Payment confirmed! First, where are you shipping from?",
        sender_profile_form_card(),
    )


@payment_proto.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment) -> None:
    """Verify the Stripe payment, complete it, and continue the right flow."""
    ctx.logger.info(f"[payment] CommitPayment from {sender} | txn={msg.transaction_id}")
    state_data = get_state(ctx, sender)
    checkout_id = str(state_data.get("stripe_session_id") or "")
    purpose = state_data.get("payment_purpose", "gate")

    paid = await asyncio.to_thread(verify_paid, checkout_id) if checkout_id else False
    if not paid:
        ctx.logger.error(f"[payment] Stripe verification FAILED: {checkout_id}")
        await ctx.send(
            sender,
            RejectPayment(reason="Stripe payment not confirmed yet. Please finish checkout."),
        )
        if purpose == "label":
            from chat_proto import handle_label_payment_failed

            await handle_label_payment_failed(ctx, sender, state_data)
        return

    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
    ctx.logger.info(f"[payment] Verified | sender={sender} | checkout={checkout_id}")
    await _handle_paid(ctx, sender, state_data)


@payment_proto.on_message(RejectPayment)
async def on_reject(ctx: Context, sender: str, msg: RejectPayment) -> None:
    """The buyer cancelled payment - reset the gate, or cancel the label purchase."""
    ctx.logger.info(f"[payment] Rejected by {sender}: {msg.reason}")
    state_data = get_state(ctx, sender)

    if state_data.get("payment_purpose") == "label":
        from chat_proto import handle_label_payment_failed

        await handle_label_payment_failed(ctx, sender, state_data)
        return

    state_data["state"] = AWAITING_PAYMENT
    state_data["stripe_paid"] = False
    save_state(ctx, sender, state_data)

    from chat_proto import send_text

    await send_text(
        ctx,
        sender,
        "Payment cancelled. Send any message when you're ready to try again.",
    )
