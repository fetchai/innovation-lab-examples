import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Context
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

ZODIAC = {
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
}


def wants_horoscope(text_l: str) -> bool:
    return "horoscope" in (text_l or "")


def extract_text(msg: ChatMessage) -> str:
    parts: list[str] = []
    for c in msg.content:
        if isinstance(c, TextContent) and c.text:
            parts.append(c.text)
    return " ".join(parts).strip()


def make_chat(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


def extract_sign(text_l: str) -> str | None:
    if not isinstance(text_l, str) or not text_l:
        return None
    t = text_l.strip().lower()
    for sign in ZODIAC:
        if re.search(rf"\b{re.escape(sign)}\b", t):
            return sign
    return None


def state_key(sender: str) -> str:
    return f"horoscope_state:{sender}"


def load_state(ctx: Context, sender: str) -> dict:
    raw = ctx.storage.get(state_key(sender))
    if isinstance(raw, dict):
        state = raw
    elif isinstance(raw, str) and raw:
        try:
            import json

            v = json.loads(raw)
            state = v if isinstance(v, dict) else {}
        except Exception:
            state = {}
    else:
        state = {}

    # Keep state only for the short sign → payment → horoscope flow.
    # If there's no `expires_at` (legacy/stale state), ignore it.
    try:
        if "expires_at" not in state:
            return {}
        exp = float(state.get("expires_at") or 0)
        if not exp or time.time() > exp:
            return {}
    except Exception:
        return {}

    allowed_keys = {"awaiting_sign", "awaiting_payment", "pending_stripe", "sign", "expires_at"}
    return {k: state.get(k) for k in allowed_keys if k in state}


def save_state(ctx: Context, sender: str, state: dict) -> None:
    import json

    ctx.storage.set(state_key(sender), json.dumps(state))


def clear_state(ctx: Context, sender: str) -> None:
    ctx.storage.set(state_key(sender), "{}")

