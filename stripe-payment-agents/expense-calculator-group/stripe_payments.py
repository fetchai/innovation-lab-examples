"""Stripe embedded Checkout: create session and verify payment. Mirrors stripe-horoscope-agent."""

import os
import time

from config import (
    STRIPE_AMOUNT_CENTS,
    STRIPE_CURRENCY,
    STRIPE_PRODUCT_NAME,
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_SECRET_KEY,
    STRIPE_SUCCESS_URL,
)


def _get_stripe_sdk():
    import stripe  # type: ignore

    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def _stripe_expires_at() -> int:
    expires_in_s = int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    expires_in_s = max(1800, min(24 * 60 * 60, expires_in_s))
    return int(time.time()) + expires_in_s


def create_embedded_checkout_session(
    *,
    user_address: str,
    chat_session_id: str,
    description: str,
    amount_cents: int | None = None,
) -> dict:
    """Create Stripe Checkout session. amount_cents overrides config if provided."""
    stripe = _get_stripe_sdk()
    cents = amount_cents if amount_cents is not None else STRIPE_AMOUNT_CENTS

    return_url = (
        f"{STRIPE_SUCCESS_URL}"
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
                    "currency": STRIPE_CURRENCY,
                    "product_data": {
                        "name": STRIPE_PRODUCT_NAME,
                        "description": description,
                    },
                    "unit_amount": cents,
                },
                "quantity": 1,
            }
        ],
        metadata={
            "user_address": user_address,
            "session_id": chat_session_id,
            "service": "expense_calculator",
        },
    )

    return {
        "client_secret": session.client_secret,
        "id": session.id,
        "checkout_session_id": session.id,
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "currency": STRIPE_CURRENCY,
        "amount_cents": cents,
        "ui_mode": "embedded",
    }


def verify_checkout_session_paid(checkout_session_id: str) -> bool:
    stripe = _get_stripe_sdk()
    session = stripe.checkout.Session.retrieve(checkout_session_id)
    return getattr(session, "payment_status", None) == "paid"
