import asyncio
import os
import time
import traceback

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

_QUERY_KEY = "hackflow:query:{}"
_CHECKOUT_KEY = "hackflow:checkout:{}"
_PAID_KEY = "hackflow:paid:{}"
BRIEF_KEY = "hackflow:brief:{}"
ORIG_QUERY_KEY = "hackflow:original_query:{}"
HISTORY_KEY = "hackflow:history:{}"


# Stripe helpers
def _cfg() -> dict:
    return {
        "secret_key": (os.getenv("STRIPE_SECRET_KEY") or "").strip(),
        "publishable_key": (os.getenv("STRIPE_PUBLISHABLE_KEY") or "").strip(),
        "amount_cents": int(os.getenv("STRIPE_AMOUNT_CENTS", "100")),
        "currency": (os.getenv("STRIPE_CURRENCY", "usd") or "usd").lower(),
        "success_url": (
            os.getenv("STRIPE_SUCCESS_URL", "https://agentverse.ai")
            or "https://agentverse.ai"
        ).rstrip("/"),
    }


def _stripe():
    import stripe as _s  # noqa: PLC0415

    _s.api_key = _cfg()["secret_key"]
    return _s


def _expires_at() -> int:
    sec = int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    return int(time.time()) + max(1800, min(24 * 3600, sec))


def create_checkout_session(sender: str, chat_session_id: str) -> dict:
    c = _cfg()
    s = _stripe()
    return_url = (
        f"{c['success_url']}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={sender}"
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
                        "name": "Hackflow Competitive Intelligence Brief",
                        "description": (
                            "Sponsor analysis, winning patterns, "
                            "3 tailored project ideas with tech stacks."
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
            "service": "hackflow_brief",
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
    try:
        session = _stripe().checkout.Session.retrieve(checkout_session_id)
        return getattr(session, "payment_status", None) == "paid"
    except Exception:
        return False


def resolve_checkout_id(transaction_ref: str) -> str:
    ref = (transaction_ref or "").strip()
    if not ref or ref.startswith("cs_"):
        return ref
    if not ref.startswith("pi_"):
        return ref
    try:
        sessions = _stripe().checkout.Session.list(payment_intent=ref, limit=1)
        if sessions.data:
            return sessions.data[0].id
    except Exception:
        pass
    return ref


async def request_payment_from_user(ctx: Context, sender: str, query: str) -> None:
    """
    Create Stripe session, store state, send RequestPayment.
    ASI:One renders the card form from metadata["stripe"].
    """
    c = _cfg()
    chat_session_id = str(ctx.session)
    checkout = await asyncio.to_thread(create_checkout_session, sender, chat_session_id)

    ctx.storage.set(_QUERY_KEY.format(sender), query)
    ctx.storage.set(_CHECKOUT_KEY.format(sender), checkout["checkout_session_id"])

    amount_str = f"{c['amount_cents'] / 100:.2f}"
    await ctx.send(
        sender,
        RequestPayment(
            accepted_funds=[
                Funds(currency="USD", amount=amount_str, payment_method="stripe")
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=1800,
            reference=chat_session_id,
            description=(
                f"Pay ${amount_str} for your Hackflow competitive intelligence research"
            ),
            metadata={"stripe": checkout, "service": "hackflow_brief"},
        ),
    )
    ctx.logger.info(
        f"[payment] Stripe RequestPayment → {sender} | "
        f"checkout={checkout['checkout_session_id']} | ${amount_str}"
    )


async def retry_paid_brief(ctx: Context, sender: str, combined_query: str) -> None:
    """
    Called from agent.py when user retries in State C (paid, brief not yet delivered).
    Updates the stored query with the combined query and re-runs delivery.
    """
    ctx.storage.set(_QUERY_KEY.format(sender), combined_query)
    await _deliver_brief(ctx, sender, combined_query)


async def deliver_brief_after_stripe_confirm(ctx: Context, sender: str) -> bool:
    """
    Called from agent.py when ASI:One sends a <stripe:payment_id:...:CONFIRM>
    chat message instead of CommitPayment.
    Returns True if delivery was attempted, False if no pending session.
    """
    query = ctx.storage.get(_QUERY_KEY.format(sender))
    checkout_id = ctx.storage.get(_CHECKOUT_KEY.format(sender))
    if not query or not checkout_id:
        return False
    paid = await asyncio.to_thread(verify_paid, checkout_id)
    if not paid:
        return False
    ctx.storage.set(_PAID_KEY.format(sender), "true")
    ctx.storage.remove(_CHECKOUT_KEY.format(sender))
    await _deliver_brief(ctx, sender, query)
    return True


# Payment protocol handlers
@payment_proto.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
    ctx.logger.info(f"[payment] CommitPayment from {sender} | txn={msg.transaction_id}")

    query = ctx.storage.get(_QUERY_KEY.format(sender))
    if not query:
        ctx.logger.warning(f"[payment] No stored query for {sender}")
        await ctx.send(
            sender,
            RejectPayment(
                reason="Session expired. Please send your hackathon query again."
            ),
        )
        return

    checkout_id = resolve_checkout_id(msg.transaction_id)
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

    # Mark as paid, clear checkout (keep query for retry if delivery fails)
    ctx.storage.set(_PAID_KEY.format(sender), "true")
    ctx.storage.remove(_CHECKOUT_KEY.format(sender))

    await _deliver_brief(ctx, sender, query)


@payment_proto.on_message(RejectPayment)
async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"[payment] Rejected by {sender}: {msg.reason}")
    clear_state(ctx, sender)
    await _send_text(
        ctx,
        sender,
        "Payment cancelled. Send your hackathon query again whenever you're ready.",
    )


# Internal helpers
async def _deliver_brief(ctx: Context, sender: str, query: str) -> None:
    """
    Run the Deep Agents workflow and deliver the brief to the user.
    """
    # Single status message to avoid ASI:One batching multiple bubbles together
    await _send_text(
        ctx,
        sender,
        "Hackflow is working on your request...",
    )

    try:
        from workflow import run_query  # noqa: PLC0415

        brief = await asyncio.to_thread(run_query, query)
    except Exception as exc:
        _msg = str(exc).lower()
        is_rate_limit = "rate limit" in _msg or "topup" in _msg or "quota" in _msg
        ctx.logger.error(f"[payment] run_query error: {exc}\n{traceback.format_exc()}")

        if is_rate_limit:
            msg_body = (
                "API limit hit mid-analysis. Your $"
                f"{int(os.getenv('STRIPE_AMOUNT_CENTS', '100')) / 100:.2f} "
                "payment is saved — send any message to retry at no charge."
            )
        else:
            # Keep paid state even for unexpected errors — never charge twice.
            # User can retry (send any message) or cancel with "new search".
            msg_body = (
                "Something went wrong during research. "
                "Your payment is saved — send any message to retry, "
                "or say **new search** to start fresh with a different query."
            )
        await _send_text(ctx, sender, msg_body)
        return

    # Guard: only store if the brief looks complete (has project ideas).
    # run_query can return a partial result (events-only) when the model-call
    # limit fires mid-run without raising an exception. Storing a partial brief
    # would overwrite a good brief from a previous run and break State D memory.
    brief_lower = brief.lower()
    brief_complete = (
        "project idea" in brief_lower
        or "idea 1" in brief_lower
        or "winning idea" in brief_lower
        or "recommended project" in brief_lower
    )
    if not brief_complete:
        ctx.logger.warning(
            "[payment] run_query returned a partial brief (no project ideas). "
            "Keeping paid state so user can retry for free."
        )
        await _send_text(ctx, sender, brief + "\n\n---\n")
        return

    # Success: persist brief for State D (free follow-ups), clear payment state
    ctx.storage.set(BRIEF_KEY.format(sender), brief)
    ctx.storage.set(ORIG_QUERY_KEY.format(sender), query)
    clear_state(ctx, sender)
    await _send_text(ctx, sender, brief)


def clear_state(ctx: Context, sender: str) -> None:
    """Clear payment keys (paid, query, checkout). Keeps brief for State D."""
    ctx.storage.remove(_QUERY_KEY.format(sender))
    ctx.storage.remove(_CHECKOUT_KEY.format(sender))
    ctx.storage.remove(_PAID_KEY.format(sender))


def clear_brief_state(ctx: Context, sender: str) -> None:
    """Clear State D keys (brief, original query, conversation history, session)."""
    ctx.storage.remove(BRIEF_KEY.format(sender))
    ctx.storage.remove(ORIG_QUERY_KEY.format(sender))
    ctx.storage.remove(HISTORY_KEY.format(sender))
    ctx.storage.remove(f"hackflow:session:{sender}")


async def _send_text(ctx: Context, recipient: str, text: str) -> None:
    from datetime import datetime, timezone  # noqa: PLC0415
    from uuid import uuid4  # noqa: PLC0415

    await ctx.send(
        recipient,
        ChatMessage(
            timestamp=datetime.now(tz=timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        ),
    )
