from __future__ import annotations
import asyncio
import os
import time

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from quiz_cards import QuizCards, send_card, send_text
from session_manager import (
    AWAITING_PAYMENT,
    AWAITING_SOURCES,
    CHOOSING_SOURCE_TYPE,
    SessionManager,
)

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

_session = SessionManager()
_cards = QuizCards()


# Stripe helpers 
def _cfg() -> dict:
    """Read Stripe config from the environment."""
    return {
        "secret_key": (os.getenv("STRIPE_SECRET_KEY") or "").strip(),
        "publishable_key": (os.getenv("STRIPE_PUBLISHABLE_KEY") or "").strip(),
        "amount_cents": int(os.getenv("STRIPE_AMOUNT_CENTS", "200")),
        "currency": (os.getenv("STRIPE_CURRENCY", "usd") or "usd").lower(),
        "success_url": (
            os.getenv("STRIPE_SUCCESS_URL", "https://agentverse.ai")
            or "https://agentverse.ai"
        ).rstrip("/"),
    }


def _stripe():
    """Return the configured Stripe SDK module."""
    import stripe as _s  # noqa: PLC0415

    _s.api_key = _cfg()["secret_key"]
    return _s


def _expires_at() -> int:
    """Checkout expiry, clamped to Stripe's 30 min – 24 h window."""
    sec = int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    return int(time.time()) + max(1800, min(24 * 3600, sec))


def create_checkout_session(sender: str, chat_session_id: str) -> dict:
    """Create an embedded Stripe Checkout session.

    ``ui_mode="embedded_page"`` is what ASI:One's payment card renderer
    expects — it uses ``client_secret`` + ``publishable_key`` to mount the
    Stripe form when the user clicks "Pay with Stripe".
    """
    c = _cfg()
    s = _stripe()
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
                    "product_data": {
                        "name": "Haystack Quiz Agent — Quiz Generation",
                        "description": (
                            "One quiz session: multi-source interactive quiz with "
                            "grounded feedback. Unlimited students join free."
                        ),
                    },
                    "unit_amount": c["amount_cents"],
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_address": sender,
            "session_id": chat_session_id,
            "service": "quiz",
        },
    )
    return {
        "client_secret": session.client_secret,
        "id": session.id,
        "checkout_session_id": session.id,
        "publishable_key": c["publishable_key"],
        "currency": c["currency"],
        "amount_cents": c["amount_cents"],
        "ui_mode": "embedded_page",
    }


def verify_paid(checkout_session_id: str) -> bool:
    """Return True if the Stripe checkout session is fully paid."""
    try:
        session = _stripe().checkout.Session.retrieve(checkout_session_id)
        return getattr(session, "payment_status", None) == "paid"
    except Exception:
        return False


def resolve_checkout_id(transaction_ref: str) -> str:
    """Map a payment_intent (pi_) back to its checkout session (cs_) if needed."""
    ref = (transaction_ref or "").strip()
    if not ref or ref.startswith("cs_") or not ref.startswith("pi_"):
        return ref
    try:
        sessions = _stripe().checkout.Session.list(payment_intent=ref, limit=1)
        if sessions.data:
            return sessions.data[0].id
    except Exception:
        pass
    return ref


# Flow entrypoints 
async def request_payment(ctx: Context, sender: str, state_data: dict) -> None:
    """Create a hosted checkout, store it, send RequestPayment + direct URL."""
    c = _cfg()
    chat_session_id = str(ctx.session)
    checkout = await asyncio.to_thread(create_checkout_session, sender, chat_session_id)

    state_data["state"] = AWAITING_PAYMENT
    state_data["stripe_session_id"] = checkout["checkout_session_id"]
    _session.save(ctx, sender, state_data)

    amount_str = f"{c['amount_cents'] / 100:.2f}"

    # Send ONLY RequestPayment — no text before or after.
    # ASI:One renders the native "Pay with Stripe / Reject" card from this
    # message. Any text sent in the same handler call before this message
    # causes ASI:One to swallow the payment card and show only the text bubble.
    await ctx.send(
        sender,
        RequestPayment(
            accepted_funds=[
                Funds(currency="USD", amount=amount_str, payment_method="stripe")
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=1800,
            reference=chat_session_id,
            description=f"Pay ${amount_str} to generate your interactive quiz",
            metadata={"stripe": checkout, "service": "quiz"},
        ),
    )
    ctx.logger.info(
        f"[payment] RequestPayment → {sender} | checkout={checkout['checkout_session_id']} "
        f"| ${amount_str}"
    )


async def _grant_access(ctx: Context, sender: str) -> None:
    """Mark the session paid.

    If a PDF was already attached to the user's very first message (before
    payment), skip the router entirely and go straight to the form — we
    already know they have a valid source. Otherwise show the source-type
    router card so the user tells us whether they have a URL, a PDF, or both.
    """
    state_data = _session.get(ctx, sender)
    state_data["stripe_paid"] = True

    pending_pdfs = state_data.get("pending_pdf_uris", [])
    if pending_pdfs:
        state_data["state"] = AWAITING_SOURCES
        _session.save(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            text_narration=(
                f"Payment confirmed! I detected {len(pending_pdfs)} PDF(s) you "
                "attached, they'll be included automatically. Add a URL too if "
                "you'd like, or leave it blank to quiz from the PDF only."
            ),
            card=_cards.source_intake_form(url_required=False),
        )
    else:
        state_data["state"] = CHOOSING_SOURCE_TYPE
        _session.save(ctx, sender, state_data)
        await send_card(
            ctx,
            sender,
            text_narration="Payment confirmed! How will you provide your source material?",
            card=_cards.source_type_router_card(),
        )


async def confirm_payment_via_text(ctx: Context, sender: str) -> bool:
    """Re-verify the stored checkout when the user types 'paid'/'done'.

    Returns True if payment was confirmed and access granted.
    """
    state_data = _session.get(ctx, sender)
    checkout_id = state_data.get("stripe_session_id")
    if not checkout_id:
        return False
    paid = await asyncio.to_thread(verify_paid, checkout_id)
    if not paid:
        return False
    await _grant_access(ctx, sender)
    return True


# Payment protocol handlers 
@payment_proto.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
    """Verify the Stripe payment, complete it, and unlock the quiz setup."""
    ctx.logger.info(f"[payment] CommitPayment from {sender} | txn={msg.transaction_id}")
    state_data = _session.get(ctx, sender)
    stored = state_data.get("stripe_session_id")

    checkout_id = resolve_checkout_id(msg.transaction_id) or stored
    paid = await asyncio.to_thread(verify_paid, checkout_id)
    if not paid and stored:
        checkout_id = stored
        paid = await asyncio.to_thread(verify_paid, checkout_id)

    if not paid:
        ctx.logger.error(f"[payment] Stripe verification FAILED: {checkout_id}")
        await ctx.send(
            sender,
            RejectPayment(
                reason="Stripe payment not confirmed yet. Please finish checkout."
            ),
        )
        return

    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
    ctx.logger.info(f"[payment] Verified | sender={sender} | checkout={checkout_id}")
    await _grant_access(ctx, sender)


@payment_proto.on_message(RejectPayment)
async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
    """Reset the session when the buyer cancels payment."""
    ctx.logger.info(f"[payment] Rejected by {sender}: {msg.reason}")
    state_data = _session.get(ctx, sender)
    state_data["state"] = AWAITING_PAYMENT
    state_data["stripe_paid"] = False
    _session.save(ctx, sender, state_data)
    await send_text(
        ctx,
        sender,
        "Payment cancelled. Send any message when you're ready to try again.",
    )
