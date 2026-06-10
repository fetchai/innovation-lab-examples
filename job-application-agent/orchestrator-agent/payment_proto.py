"""Seller-side payment protocol — Stripe.

Charges a fixed USD amount per Greenhouse application via Stripe Checkout.
ASI:One renders the embedded Stripe checkout widget inline; on completion
it sends a CommitPayment with the Stripe checkout session id, which we
verify against Stripe before starting the application.

Flow:

    seller (us)  ──RequestPayment──►  buyer (ASI:One renders Stripe widget)
                                       │
                                  user pays via card
                                       │
    seller       ◄──CommitPayment──   buyer (with stripe checkout_session_id)
       │
       │  verify_paid(checkout_session_id)  via Stripe API
       │
       ▼
    seller ──CompletePayment──► buyer    (triggers on_complete callback)
                 or
    seller ──RejectPayment──►   buyer    (triggers on_failed callback)

Configuration (env):

- `PAYMENT_ENABLED`          — "true" turns the gate on. Default false.
- `STRIPE_SECRET_KEY`        — Stripe secret key (sk_...).
- `STRIPE_PUBLISHABLE_KEY`   — Stripe publishable key (pk_...).
- `STRIPE_AMOUNT_CENTS`      — amount in cents per application (default 100 = $1.00).
- `STRIPE_CURRENCY`          — ISO currency code (default "usd").
- `STRIPE_PRODUCT_NAME`      — displayed on the checkout page.
- `STRIPE_SUCCESS_URL`       — redirect URL after successful payment.
"""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, Callable, Optional

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from stripe_payments import create_checkout_session, verify_paid

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAYMENT_ENABLED = os.getenv("PAYMENT_ENABLED", "false").lower() in {"1", "true", "yes"}
STRIPE_AMOUNT_CENTS = int(os.getenv("STRIPE_AMOUNT_CENTS", "100"))
STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").strip().upper()


def gate_active() -> bool:
    return PAYMENT_ENABLED and bool(os.getenv("STRIPE_SECRET_KEY"))


def is_enabled() -> bool:
    return PAYMENT_ENABLED


def amount_usd() -> str:
    return f"${STRIPE_AMOUNT_CENTS / 100:.2f}"


# ---------------------------------------------------------------------------
# Callbacks (wired by agent.py after agent startup)
# ---------------------------------------------------------------------------

_on_complete_cb: Optional[Callable] = None
_on_failed_cb: Optional[Callable] = None


def set_callbacks(
    on_complete: Callable[[Context, str], Awaitable[None]],
    on_failed: Callable[[Context, str, str], Awaitable[None]],
) -> None:
    global _on_complete_cb, _on_failed_cb
    _on_complete_cb = on_complete
    _on_failed_cb = on_failed


def set_agent_wallet(wallet) -> None:
    pass  # Not needed for Stripe — kept for API compatibility.


# ---------------------------------------------------------------------------
# Payment request helper
# ---------------------------------------------------------------------------

async def send_payment_request(ctx: Context, sender: str) -> None:
    """Create a Stripe checkout session and send RequestPayment to the buyer."""
    checkout = await asyncio.to_thread(
        create_checkout_session,
        user_address=sender,
        chat_session_id=str(ctx.session),
    )
    amount_str = f"{STRIPE_AMOUNT_CENTS / 100:.2f}"
    req = RequestPayment(
        accepted_funds=[Funds(
            currency=STRIPE_CURRENCY,
            amount=amount_str,
            payment_method="stripe",
        )],
        recipient=str(ctx.agent.address),
        deadline_seconds=1800,
        reference=str(ctx.session),
        description=f"Job application — {amount_str} {STRIPE_CURRENCY}",
        metadata={"stripe": checkout, "service": "job_application"},
    )
    await ctx.send(sender, req)


# ---------------------------------------------------------------------------
# Protocol handlers
# ---------------------------------------------------------------------------

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")


@payment_proto.on_message(CommitPayment)
async def _on_commit(ctx: Context, sender: str, msg: CommitPayment):
    ctx.logger.info(
        f"[payment] CommitPayment from {sender} "
        f"method={msg.funds.payment_method} tx={msg.transaction_id}"
    )
    if msg.funds.payment_method != "stripe" or not msg.transaction_id:
        await ctx.send(sender, RejectPayment(
            reason="Unsupported payment method (expected stripe)."
        ))
        if _on_failed_cb:
            await _on_failed_cb(ctx, sender, "unsupported_payment_method")
        return

    paid = await asyncio.to_thread(verify_paid, msg.transaction_id)
    if not paid:
        await ctx.send(sender, RejectPayment(
            reason="Stripe payment not completed yet. Please finish checkout."
        ))
        if _on_failed_cb:
            await _on_failed_cb(ctx, sender, "stripe_not_paid")
        return

    ctx.logger.info(f"[payment] Stripe payment verified: {msg.transaction_id}")
    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
    if _on_complete_cb:
        await _on_complete_cb(ctx, sender)


@payment_proto.on_message(RejectPayment)
async def _on_reject(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"[payment] RejectPayment from {sender}: {msg.reason}")
    if _on_failed_cb:
        await _on_failed_cb(ctx, sender, f"buyer_rejected:{msg.reason or ''}")
