#!/usr/bin/env python3
"""
Stripe Checkout for Agent Payment Protocol (Stripe rail).

Reads STRIPE_* from the environment. Optionally merges values from the project
`.env` file (same pattern as innovation-lab-examples) so keys work when the
process is started without a shell that sourced `.env`.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import dotenv_values

try:
    import stripe
except ImportError:
    stripe = None

REPO_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = REPO_ROOT / ".env"


def _env_or_dotenv(key: str, default: str = "") -> str:
    v = os.getenv(key)
    if v is not None and str(v).strip() != "":
        return str(v).strip()
    if DOTENV_PATH.exists():
        dot = dotenv_values(DOTENV_PATH)
        dv = dot.get(key)
        if dv is not None and str(dv).strip() != "":
            return str(dv).strip()
    return default


def _cfg() -> dict:
    secret_key = _env_or_dotenv("STRIPE_SECRET_KEY", "")
    publishable_key = _env_or_dotenv("STRIPE_PUBLISHABLE_KEY", "")
    try:
        amount_cents = int(_env_or_dotenv("STRIPE_AMOUNT_CENTS", "50"))
    except ValueError:
        amount_cents = 50
    currency = (_env_or_dotenv("STRIPE_CURRENCY", "usd") or "usd").lower().strip() or "usd"
    product_name = (
        _env_or_dotenv("STRIPE_PRODUCT_NAME", "Restaurant discovery") or "Restaurant discovery"
    ).strip()
    success_url = (
        _env_or_dotenv("STRIPE_SUCCESS_URL", "https://agentverse.ai") or "https://agentverse.ai"
    ).rstrip("/")
    return {
        "secret_key": secret_key,
        "publishable_key": publishable_key,
        "amount_cents": amount_cents,
        "currency": currency,
        "product_name": product_name,
        "success_url": success_url,
    }


def get_amount_cents() -> int:
    return int(_cfg()["amount_cents"])


def is_configured() -> bool:
    c = _cfg()
    return bool(stripe and c["secret_key"] and c["publishable_key"])


def _get_stripe():
    if not stripe:
        return None
    stripe.api_key = _cfg()["secret_key"]
    return stripe


def _expires_at() -> int:
    try:
        sec = int(_env_or_dotenv("STRIPE_CHECKOUT_EXPIRES_SECONDS", "1800"))
    except ValueError:
        sec = 1800
    sec = max(1800, min(24 * 3600, sec))
    return int(time.time()) + sec


def create_hosted_checkout_session(
    *,
    user_address: str,
    chat_session_id: str,
    description: str,
) -> dict | None:
    """
    Hosted Checkout — returns a normal https://checkout.stripe.com/... link
    users can open from chat (Agent Payment Protocol UIs may still show a card).
    """
    if not is_configured():
        return None
    s = _get_stripe()
    if not s:
        return None
    c = _cfg()
    success_url = (
        f"{c['success_url']}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={user_address}"
    )
    try:
        session = s.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            success_url=success_url,
            cancel_url=c["success_url"],
            expires_at=_expires_at(),
            line_items=[
                {
                    "price_data": {
                        "currency": c["currency"],
                        "product_data": {
                            "name": c["product_name"],
                            "description": description,
                        },
                        "unit_amount": int(c["amount_cents"]),
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "user_address": user_address,
                "session_id": chat_session_id,
                "service": "restaurant_discovery",
            },
        )
        url = getattr(session, "url", None)
        if not url:
            return None
        return {
            "checkout_url": url,
            "checkout_session_id": session.id,
            "publishable_key": c["publishable_key"],
            "currency": c["currency"],
            "amount_cents": int(c["amount_cents"]),
            "ui_mode": "hosted",
        }
    except Exception:
        return None


def create_embedded_checkout_session(
    *,
    user_address: str,
    chat_session_id: str,
    description: str,
) -> dict | None:
    """
    Create a Stripe Checkout Session for embedded UI (Agentverse).

    Stripe's API may require ui_mode embedded_page; Agent Payment Protocol
    examples still expose ui_mode \"embedded\" in metadata for the client UI.
    """
    if not is_configured():
        return None
    s = _get_stripe()
    if not s:
        return None
    c = _cfg()
    # Stripe API: newer accounts use embedded_page; keep overridable.
    api_ui_mode = _env_or_dotenv("STRIPE_API_UI_MODE", "embedded_page")
    return_url = (
        f"{c['success_url']}"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
        f"&chat_session_id={chat_session_id}"
        f"&user={user_address}"
    )
    try:
        session = s.checkout.Session.create(
            ui_mode=api_ui_mode,
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
                            "name": c["product_name"],
                            "description": description,
                        },
                        "unit_amount": int(c["amount_cents"]),
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "user_address": user_address,
                "session_id": chat_session_id,
                "service": "restaurant_discovery",
            },
        )
        client_secret = getattr(session, "client_secret", None)
        checkout_id = session.id
        return {
            "client_secret": client_secret,
            "checkout_session_id": checkout_id,
            "publishable_key": c["publishable_key"],
            "currency": c["currency"],
            "amount_cents": int(c["amount_cents"]),
            # Convention from Stripe Horoscope / Payment Protocol docs for UIs.
            "ui_mode": "embedded",
        }
    except Exception:
        return None


def verify_checkout_session_paid(checkout_session_id: str) -> bool:
    if not is_configured():
        return False
    s = _get_stripe()
    if not s:
        return False
    try:
        session = s.checkout.Session.retrieve(checkout_session_id)
        return getattr(session, "payment_status", None) == "paid"
    except Exception:
        return False
