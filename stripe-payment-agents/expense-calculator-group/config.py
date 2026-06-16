"""Environment config. Stripe is optional; receipt flow works without it."""

import os

# Stripe (optional – payment step is skipped if not set)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY)

STRIPE_AMOUNT_CENTS = int(os.getenv("STRIPE_AMOUNT_CENTS", "100"))  # $1.00 default
STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").strip().lower()
STRIPE_PRODUCT_NAME = (
    os.getenv("STRIPE_PRODUCT_NAME", "Receipt / expense processing")
    or "Receipt / expense processing"
).strip()
STRIPE_SUCCESS_URL = (
    os.getenv("STRIPE_SUCCESS_URL", "https://agentverse.ai/payment-success") or ""
).strip()
