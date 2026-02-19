import os

ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
if not ASI_ONE_API_KEY:
    raise RuntimeError("Missing ASI_ONE_API_KEY")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
if not (STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY):
    raise RuntimeError("Missing STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY")

STRIPE_AMOUNT_CENTS = int(os.getenv("STRIPE_AMOUNT_CENTS", "100"))  # $1.00
STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").strip().lower()
STRIPE_PRODUCT_NAME = (os.getenv("STRIPE_PRODUCT_NAME", "Daily horoscope") or "Daily horoscope").strip()
STRIPE_SUCCESS_URL = (os.getenv("STRIPE_SUCCESS_URL", "https://agentverse.ai/payment-success") or "").strip()

