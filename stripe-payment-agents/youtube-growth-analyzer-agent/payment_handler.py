"""
Stripe embedded Checkout + Fetch Agent Payment Protocol helpers.

Follows the Innovation Lab “Stripe Horoscope Payment Protocol” pattern:
- `Funds(payment_method="stripe")`
- `RequestPayment.metadata["stripe"]` embeds publishable key, client secret, session id
- `CommitPayment.transaction_id` is the Stripe Checkout Session ID
- Verify with Stripe before delivering premium content, then `CompletePayment`

Stripe API keys: https://docs.stripe.com/keys
"""

from __future__ import annotations

import logging
import time
from typing import Any

import stripe

from config import (
    PAYMENT_DEADLINE_SECONDS,
    STRIPE_AMOUNT_CENTS,
    STRIPE_PRODUCT_NAME,
    STRIPE_SERVICE_TAG,
    get_stripe_currency,
    get_stripe_publishable_key,
    get_stripe_secret_key,
    get_stripe_success_url,
)
from uagents_core.contrib.protocols.payment import Funds, RequestPayment

logger = logging.getLogger(__name__)


def _stripe_expires_at() -> int:
    """Stripe requires expires_at in the future; clamp to [30m, 24h]."""
    now = int(time.time())
    clamped_ttl = min(24 * 60 * 60, max(PAYMENT_DEADLINE_SECONDS, 30 * 60))
    return now + clamped_ttl


def create_embedded_checkout_session(
    *,
    user_address: str,
    chat_session_id: str,
    description: str,
) -> dict[str, Any]:
    """
    Create an embedded Stripe Checkout Session (ui_mode=embedded).

    Returns a dict suitable for `RequestPayment.metadata["stripe"]`, including
    `client_secret`, `publishable_key`, `checkout_session_id`, and `ui_mode`.
    """
    stripe.api_key = get_stripe_secret_key()
    currency = get_stripe_currency()

    return_url = (
        f"{get_stripe_success_url()}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={user_address}"
    )

    session = stripe.checkout.Session.create(
        ui_mode="embedded",
        redirect_on_completion="if_required",
        payment_method_types=["card"],
        mode="payment",
        return_url=return_url,
        expires_at=_stripe_expires_at(),
        line_items=[
            {
                "price_data": {
                    "currency": currency,
                    "product_data": {
                        "name": STRIPE_PRODUCT_NAME,
                        "description": description,
                    },
                    "unit_amount": STRIPE_AMOUNT_CENTS,
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_address": user_address,
            "session_id": chat_session_id,
            "service": STRIPE_SERVICE_TAG,
        },
    )

    # All values as strings keeps `RequestPayment.metadata` compatible with strict clients
    # (some stacks expect `dict[str, str]` inside `metadata["stripe"]`).
    checkout: dict[str, Any] = {
        "client_secret": str(session.client_secret or ""),
        "id": str(session.id),
        "checkout_session_id": str(session.id),
        "publishable_key": get_stripe_publishable_key(),
        "currency": str(currency),
        "amount_cents": str(STRIPE_AMOUNT_CENTS),
        "ui_mode": "embedded",
    }
    logger.info("Created Stripe embedded Checkout session %s", session.id)
    return checkout


def verify_checkout_session_paid(checkout_session_id: str) -> bool:
    """Return True if the Checkout Session exists and is paid."""
    stripe.api_key = get_stripe_secret_key()
    try:
        session = stripe.checkout.Session.retrieve(checkout_session_id)
    except stripe.error.StripeError as e:
        logger.warning(
            "Stripe session verification failed for %s: %s", checkout_session_id, e
        )
        return False
    return getattr(session, "payment_status", None) == "paid"


def verify_checkout_session_amount_usd(
    checkout_session_id: str, expected_cents: int = STRIPE_AMOUNT_CENTS
) -> bool:
    """
    Extra safety: ensure the paid session total matches the expected USD cents.
    """
    stripe.api_key = get_stripe_secret_key()
    try:
        session = stripe.checkout.Session.retrieve(checkout_session_id)
    except stripe.error.StripeError as e:
        logger.warning(
            "Stripe amount verification failed for %s: %s", checkout_session_id, e
        )
        return False
    if getattr(session, "payment_status", None) != "paid":
        return False
    total = getattr(session, "amount_total", None)
    if total is None:
        return False
    return int(total) == int(expected_cents)


def build_request_payment(
    *,
    agent_address: str,
    reference: str,
    checkout: dict[str, Any],
    description: str,
) -> RequestPayment:
    """Construct seller-side `RequestPayment` with Stripe metadata for embedded Checkout."""
    amount_str = f"{STRIPE_AMOUNT_CENTS / 100:.2f}"
    return RequestPayment(
        accepted_funds=[
            Funds(currency="USD", amount=amount_str, payment_method="stripe")
        ],
        recipient=str(agent_address),
        deadline_seconds=PAYMENT_DEADLINE_SECONDS,
        reference=reference,
        description=description,
        metadata={
            "stripe": checkout,
            "service": STRIPE_SERVICE_TAG,
        },
    )
