"""stripe_payments.py — Stripe Checkout integration for the real estate agent.

Uses embedded checkout so the ASI:One wallet can render the payment UI inline.
The checkout session ID is passed as RequestPayment metadata; the client sends
CommitPayment with that ID as transaction_id after the user pays.
"""

import os
import time

import stripe as _stripe

# ─────────────────────────────────────────────────────────────────────────────
# Config from environment
# ─────────────────────────────────────────────────────────────────────────────

STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")
STRIPE_PRODUCT_NAME = os.getenv("STRIPE_PRODUCT_NAME", "Real Estate Listings Sheet")
# Amount in cents — default $1.99
STRIPE_AMOUNT_CENTS = int(os.getenv("STRIPE_AMOUNT_CENTS", "199"))
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
# Redirect target shown after payment completes in embedded checkout
STRIPE_RETURN_URL = os.getenv("STRIPE_RETURN_URL", "https://agentverse.ai/")


def is_configured() -> bool:
    """Return True if Stripe secret key is present in the environment."""
    return bool(os.getenv("STRIPE_SECRET_KEY", "").strip())


def _init() -> None:
    """Set stripe.api_key from env; raise if missing."""
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY is not set. Add it to your .env to enable payments."
        )
    _stripe.api_key = key


def _expires_at() -> int:
    """Stripe session expiry: 30 min default, clamped to [30m, 24h]."""
    secs = int(os.getenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    secs = max(1800, min(86400, secs))
    return int(time.time()) + secs


def create_checkout_session(
    user_address: str, chat_session_id: str, description: str
) -> dict:
    """Create a Stripe embedded checkout session.

    Returns a dict with:
        client_secret       — used by Agentverse/ASI:One to render the payment form inline
        checkout_session_id — sent back by the wallet as CommitPayment.transaction_id
        publishable_key     — Stripe publishable key for the frontend
        currency / amount_cents / ui_mode — echoed for the wallet metadata
    """
    _init()
    return_url = (
        f"{STRIPE_RETURN_URL}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={user_address}"
    )
    session = _stripe.checkout.Session.create(
        ui_mode="embedded",
        redirect_on_completion="if_required",
        mode="payment",
        payment_method_types=["card"],
        return_url=return_url,
        expires_at=_expires_at(),
        line_items=[
            {
                "price_data": {
                    "currency": STRIPE_CURRENCY,
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
        },
    )
    return {
        "client_secret": session.client_secret,
        "id": session.id,
        "checkout_session_id": session.id,
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "currency": STRIPE_CURRENCY,
        "amount_cents": STRIPE_AMOUNT_CENTS,
        "ui_mode": "embedded",
    }


def verify_payment(transaction_id: str) -> bool:
    """Return True if the payment has been completed.

    Accepts:
      - Stripe checkout session IDs (cs_...) — checks payment_status == 'paid'
      - Stripe PaymentIntent IDs (pi_...)    — checks status == 'succeeded'
    """
    _init()
    if transaction_id.startswith("pi_"):
        pi = _stripe.PaymentIntent.retrieve(transaction_id)
        return getattr(pi, "status", None) in ("succeeded", "processing")
    session = _stripe.checkout.Session.retrieve(transaction_id)
    return getattr(session, "payment_status", None) == "paid"
