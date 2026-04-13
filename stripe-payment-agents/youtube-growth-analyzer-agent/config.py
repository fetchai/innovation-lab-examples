"""Environment-driven configuration for the YouTube Growth Analyzer agent."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _optional(name: str, default: str) -> str:
    return os.getenv(name, default)


@lru_cache
def get_youtube_api_key() -> str:
    """YouTube Data API v3 key."""
    return _require("YOUTUBE_API_KEY")


@lru_cache
def get_stripe_secret_key() -> str:
    """Stripe secret API key (sk_test_... or sk_live_...). See https://docs.stripe.com/keys"""
    return _require("STRIPE_SECRET_KEY")


@lru_cache
def get_stripe_publishable_key() -> str:
    """Stripe publishable key (pk_test_... or pk_live_...)."""
    return _require("STRIPE_PUBLISHABLE_KEY")


@lru_cache
def get_stripe_success_url() -> str:
    """Return URL base for embedded Checkout (session_id appended by Stripe)."""
    return _require("STRIPE_SUCCESS_URL")


@lru_cache
def get_stripe_currency() -> str:
    """Lowercase ISO currency for Stripe (e.g. usd)."""
    return _optional("STRIPE_CURRENCY", "usd").lower()


# Fixed product price: exactly $5.00 USD (Stripe unit_amount is in cents).
STRIPE_AMOUNT_CENTS: int = 500
STRIPE_PRODUCT_NAME: str = "YouTube Full Growth Report"
STRIPE_SERVICE_TAG: str = "youtube_growth_analyzer"

# Payment request validity window (seconds).
PAYMENT_DEADLINE_SECONDS: int = int(os.getenv("PAYMENT_DEADLINE_SECONDS", "1800"))

# State TTL for channel → payment flow (seconds). Keep long enough for user to finish Stripe checkout.
STATE_TTL_SECONDS: int = int(os.getenv("STATE_TTL_SECONDS", str(2 * 60 * 60)))

# Max characters per ChatMessage for premium report (ASI:One / UIs often truncate long bubbles).
PREMIUM_REPORT_CHUNK_CHARS: int = int(os.getenv("PREMIUM_REPORT_CHUNK_CHARS", "4000"))

# Recent videos to analyze (uploads playlist).
RECENT_VIDEO_MAX_RESULTS: int = int(os.getenv("RECENT_VIDEO_MAX_RESULTS", "25"))

# Agentverse / local endpoint port.
AGENT_PORT: int = int(os.getenv("AGENT_PORT", "8012"))
