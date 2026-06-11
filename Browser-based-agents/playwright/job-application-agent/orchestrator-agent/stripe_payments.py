"""Stripe checkout helpers for the job-application payment gate.

Adapted from stripe-horoscope-agent/stripe_payments.py.
"""

import os
import time


def _stripe():
    import stripe  # type: ignore
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    return stripe


def _expires_at() -> int:
    expires_in_s = int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    expires_in_s = max(1800, min(24 * 60 * 60, expires_in_s))
    return int(time.time()) + expires_in_s


def create_checkout_session(*, user_address: str, chat_session_id: str) -> dict:
    """Create an embedded Stripe checkout session. Returns the session metadata
    dict that is embedded in RequestPayment.metadata["stripe"]."""
    stripe = _stripe()
    amount_cents = int(os.getenv("STRIPE_AMOUNT_CENTS", "100"))
    currency = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").strip().lower()
    product_name = (os.getenv("STRIPE_PRODUCT_NAME", "Job Application Service") or "").strip()
    success_url = (os.getenv("STRIPE_SUCCESS_URL", "https://agentverse.ai/payment-success") or "").strip()

    return_url = (
        f"{success_url}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={user_address}"
    )

    session = stripe.checkout.Session.create(
        ui_mode="embedded_page",
        redirect_on_completion="if_required",
        payment_method_types=["card"],
        mode="payment",
        return_url=return_url,
        expires_at=_expires_at(),
        line_items=[{
            "price_data": {
                "currency": currency,
                "product_data": {
                    "name": product_name,
                    "description": "Automated Greenhouse job application",
                },
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        metadata={
            "user_address": user_address,
            "session_id": chat_session_id,
            "service": "job_application",
        },
    )

    return {
        "client_secret": session.client_secret,
        "id": session.id,
        "checkout_session_id": session.id,
        "publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
        "currency": currency,
        "amount_cents": amount_cents,
        "ui_mode": "embedded_page",
    }


def verify_paid(checkout_session_id: str) -> bool:
    """Return True if the Stripe checkout session has been paid."""
    stripe = _stripe()
    session = stripe.checkout.Session.retrieve(checkout_session_id)
    return getattr(session, "payment_status", None) == "paid"
