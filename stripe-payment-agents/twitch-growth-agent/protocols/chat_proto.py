"""Chat protocol: all message handlers, card builders, and helper functions.

The chat_proto Protocol object is included into the Agent in agent.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import uuid4

import stripe
from dotenv import load_dotenv
from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    Resource,
    ResourceContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import Funds, RequestPayment
from uagents_core.types import DeliveryStatus

from growth_pipeline import (
    GrowthState,
    app as growth_graph,
    channel_analyzer,
    content_researcher,
    llm,
)
from twitch.oauth import (
    NEEDS_CONNECT,
    build_authorize_url,
    create_clip,
    find_raid_candidates,
    get_chat_settings,
    get_clip_thumbnail,
    is_connected,
    send_announcement,
    setup_channel,
    start_raid,
    update_chat_settings,
)
from twitch.recap import generate_recap

from app_state import listener_manager, _user_sessions

load_dotenv()
logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
# Required by Embedded Checkout even though Agentverse completes in-chat.
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://example.com/success")

STRIPE_CURRENCY = "usd"
STRIPE_PRODUCT_NAME = "Twitch Assistant Full Access (one-time unlock)"
STRIPE_AMOUNT_CENTS = int(os.getenv("STRIPE_AMOUNT_CENTS", "499"))
PRICE_LABEL = f"${STRIPE_AMOUNT_CENTS / 100:.2f} {STRIPE_CURRENCY.upper()}"

# Decoupled on purpose: the Stripe API call needs "embedded_page", but the
# Agentverse renderer expects the literal "embedded" in the metadata.
STRIPE_API_UI_MODE = "embedded_page"
CHAT_UI_MODE = "embedded"


def create_embedded_checkout_session(
    *, user_address: str, chat_session_id: str, description: str
) -> dict:
    """Create an embedded Stripe Checkout session and return its client payload."""
    session = stripe.checkout.Session.create(
        ui_mode=STRIPE_API_UI_MODE,  # type: ignore[arg-type]
        redirect_on_completion="if_required",
        mode="payment",
        payment_method_types=["card"],
        return_url=STRIPE_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
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
        metadata={"user_address": user_address, "chat_session_id": chat_session_id},
    )
    return {
        "client_secret": session.client_secret,
        "checkout_session_id": session.id,
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "currency": STRIPE_CURRENCY,
        "amount_cents": STRIPE_AMOUNT_CENTS,
        # Not session.ui_mode — the renderer keys off "embedded". Don't "fix" this.
        "ui_mode": CHAT_UI_MODE,
    }


def verify_checkout_session_paid(checkout_session_id: str) -> bool:
    """Retrieve the Checkout session and check that it has been paid."""
    session = stripe.checkout.Session.retrieve(checkout_session_id)
    return getattr(session, "payment_status", None) == "paid"


def run_growth_pipeline(channel_name: str) -> Tuple[str, str]:
    """Invoke the full LangGraph graph; return (niche, final_report). Blocking."""
    result = growth_graph.invoke(
        {
            "channel_name": channel_name,
            "channel_stats": None,
            "niche": None,
            "competitors": None,
            "gaps": None,
            "final_report": None,
        }
    )
    return (
        result.get("niche") or "unknown",
        result.get("final_report") or "No report generated.",
    )


# Sentinel values an LLM commonly returns to mean "no channel here".
_NO_CHANNEL_TOKENS = {"no", "none", "n/a", "na", "null", "nil", "unknown", "channel"}


def _clean_channel(candidate: Optional[str]) -> Optional[str]:
    """Validate a candidate channel string; None if it's not a real handle."""
    if not candidate:
        return None
    token = candidate.strip().strip("@\"'`.,!?").strip()
    if not token or token.lower() in _NO_CHANNEL_TOKENS:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]{3,25}", token):
        return None
    return token


def extract_channel_name(message: str) -> Optional[str]:
    """Pull a Twitch username out of a message via ASI:One, or None if the
    message doesn't reference a real channel. A bare username skips the LLM call.
    """
    text = message.strip()
    if re.fullmatch(r"[A-Za-z0-9_]{3,25}", text):
        return text

    prompt = (
        "Extract the Twitch channel username the user wants analyzed from the "
        "message below. Respond with ONLY the username — letters, numbers and "
        "underscores, no '@', no quotes, no punctuation, no extra words. If the "
        "message does not mention a specific Twitch channel to analyze, respond "
        "with exactly the word NONE.\n\n"
        f"Message: {message}"
    )
    try:
        raw = str(llm.invoke(prompt).content).strip()
    except Exception:  # noqa: BLE001 - LLM/network failure => treat as no channel
        return None
    token = (raw.split() or [""])[0]
    return _clean_channel(token)


def run_preview(channel_name: str) -> Tuple[str, str]:
    """Run only the cheap first nodes for the free preview: (display_name, niche).
    Stops before the paid work. Blocking.
    """
    state: GrowthState = {
        "channel_name": channel_name,
        "channel_stats": None,
        "niche": None,
        "competitors": None,
        "gaps": None,
        "final_report": None,
    }
    state = channel_analyzer(state)
    state = content_researcher(state)
    stats: dict = state.get("channel_stats") or {}
    return (stats.get("display_name") or channel_name, state.get("niche") or "unknown")


_VALID_INTENTS = {
    "growth_report",
    "channel_setup",
    "announcement",
    "chat_settings",
    "clip",
    "raid",
    "recap",
    "connector_redirect",
    "unknown",
}

# Only these keys are forwarded to twitch_oauth.update_chat_settings (and only
# when the classifier actually included them).
_CHAT_SETTING_KEYS = {
    "slow_mode",
    "slow_mode_wait_seconds",
    "follower_mode",
    "follower_mode_duration",
    "subscriber_mode",
    "emote_mode",
    "unique_chat_mode",
}

_INTENT_SYSTEM_PROMPT = """You are an intent classifier for a Twitch channel assistant.
Classify the user's message into EXACTLY ONE intent and extract its parameters.
Return ONLY valid JSON (no markdown, no code fences, no commentary) in the form:
{"intent": "<intent>", "params": { ... }}

Valid intents and their params:
- "growth_report": {"channel_name": "<twitch login>"} — user wants an analysis / growth report / strategy for a channel. If the user names a specific channel, include channel_name. If it's a generic request without a channel (e.g. "growth report", "analyze a channel", "give me a strategy", "channel analysis"), return empty params {}.
- "channel_setup": {"title": "<stream title>", "game_name": "<category>", "tags": ["..."]} — set/update the channel's title, game/category, or tags. tags is optional.
- "announcement": {"message": "<text>", "color": "<blue|green|orange|purple|primary>"} — post a chat announcement. color is optional (default "primary"). If the user provides the announcement text, include message (and color if specified). If it's a generic request to post an announcement without message text (e.g. "post an announcement", "make an announcement"), return empty params {}.
- "chat_settings": {"slow_mode": <bool>, "slow_mode_wait_seconds": <int>, "follower_mode": <bool>, "follower_mode_duration": <int>, "subscriber_mode": <bool>, "emote_mode": <bool>, "unique_chat_mode": <bool>} — view, manage, or change chat room modes. This covers BOTH specific toggles (e.g. "turn on slow mode") AND generic requests to manage chat settings (e.g. "manage my chat settings", "open chat settings", "configure my chat", "chat settings"). If the user names specific modes, include ONLY those fields; if it's a generic request without any specific mode, return empty params {}.
- "clip": {} — create/capture a clip of the current stream.
- "raid": {"game_name": "<category>", "max_viewers": <int>} — find and start a raid on a channel in a category. max_viewers is optional (default 100).
- "recap": {} — the user wants a recap / summary of what happened in their live stream while they were away or busy (e.g. "what did I miss?", "recap my stream", "catch me up", "summarize chat", "who do I need to thank?").
- "connector_redirect": {} — the user wants a task that ASI:One's BUILT-IN Twitch connector handles, not one of twitchy's own features. This covers: changing the stream title or category ("set my title", "change my category"); reading channel/user/stream info ("how many followers do I have", "is ninja live", "what's my viewer count"); searching channels or games; getting videos, clips, or top games; blocking or unblocking a user; deleting a video; and checking subscription status. Always return empty params {}.
- "unknown": {} — the message does not match any capability above.

Rules:
- Output strictly ONE JSON object and nothing else.
- Only include params that the user actually specified; do not invent values.
- For chat_settings, if specific modes are mentioned include only those modes; if it's a generic chat-settings request with no specific mode named, return chat_settings with params {} (do NOT return unknown).
- For growth_report, if a channel is named include channel_name; if it's a generic growth-report request with no channel named, return growth_report with params {} (do NOT return unknown).
- A request to CHANGE the stream title or category is connector_redirect (the built-in connector handles those), NOT channel_setup.
- Read-only info questions (follower/viewer counts, who is live, video/clip lookups), channel/game search, block/unblock, delete video, and subscription checks are connector_redirect, NOT unknown."""


def _parse_intent_json(raw: str) -> dict:
    """Defensively parse the classifier output into a dict (handles code fences)."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def classify_intent(message: str) -> dict:
    """Classify ``message`` via ASI:One into {"intent", "params"}.

    Any LLM/parse failure (or an unrecognized intent) degrades to "unknown".
    """
    prompt = f"{_INTENT_SYSTEM_PROMPT}\n\nUser message: {message}\n\nJSON:"
    try:
        raw = str(llm.invoke(prompt).content).strip()
        data = _parse_intent_json(raw)
        intent = data.get("intent")
        params = data.get("params")
        if intent in _VALID_INTENTS and isinstance(params, dict):
            return {"intent": intent, "params": params}
    except Exception:  # noqa: BLE001 - any failure => unknown
        pass
    return {"intent": "unknown", "params": {}}


def describe_action(intent: str, params: dict) -> str:
    """Short human-readable summary of an action (for the pre-payment message)."""
    if intent == "channel_setup":
        bits = []
        if params.get("title"):
            bits.append(f"title to '{params['title']}'")
        if params.get("game_name"):
            bits.append(f"category to '{params['game_name']}'")
        if params.get("tags"):
            bits.append(f"tags {params['tags']}")
        return "update your channel (" + ", ".join(bits or ["settings"]) + ")"
    if intent == "announcement":
        return f"post a {params.get('color', 'primary')} chat announcement"
    if intent == "chat_settings":
        return "update your chat settings"
    if intent == "clip":
        return "create a clip of your current stream"
    if intent == "raid":
        return f"find and start a raid in '{params.get('game_name', 'a category')}'"
    if intent == "recap":
        return "recap what happened in your stream while you were away"
    return "run that action"


def execute_job(job: dict) -> str:
    """Run a paid job and return the result text. Blocking, call via to_thread.
    Dispatches on job["intent"], passing job["user_id"] to the twitch_oauth actions.
    """
    intent = job.get("intent")
    params = job.get("params") or {}
    user_id = job.get("user_id")

    if intent == "growth_report":
        channel = params.get("channel_name") or ""
        niche, report = run_growth_pipeline(channel)
        return f"Full growth strategy report for {channel} (niche: {niche})\n\n{report}"

    if intent == "channel_setup":
        return setup_channel(
            title=params.get("title", ""),
            game_name=params.get("game_name", ""),
            tags=params.get("tags"),
            user_id=user_id,
        )

    if intent == "announcement":
        ann_message = params.get("message", "")
        ann_color = params.get("color", "primary")
        logger.info(
            "execute_job -> send_announcement: user_id=%s message=%r color=%r params=%s",
            user_id,
            ann_message,
            ann_color,
            params,
        )
        return send_announcement(
            message=ann_message,
            color=ann_color,
            user_id=user_id,
        )

    if intent == "chat_settings":
        kwargs = {k: params[k] for k in _CHAT_SETTING_KEYS if params.get(k) is not None}
        return update_chat_settings(user_id=user_id, **kwargs)

    if intent == "clip":
        return create_clip(user_id=user_id)

    if intent == "recap":
        return generate_recap(user_id or "", llm=llm)

    return "Sorry, I couldn't run that request."


async def _deliver_job(ctx: "Context", sender: str, job: dict):
    """Run a job (post-payment or already-unlocked) and reply. NEEDS_CONNECT
    becomes the connect prompt instead. Raid uses its own review-card flow.
    """
    if job.get("intent") == "raid":
        await _handle_raid_intent(
            ctx,
            sender,
            job.get("user_id") or resolve_user_key(sender),
            job.get("params") or {},
        )
        return

    try:
        result_text = await asyncio.to_thread(execute_job, job)
    except Exception as exc:  # noqa: BLE001 - surface job failure to user
        ctx.logger.error(f"Job failed: {exc}")
        await _send(
            ctx, sender, _chat(f"Sorry, that request failed: {exc}", end_session=True)
        )
        return

    if result_text == NEEDS_CONNECT:
        await _send_connect_prompt(ctx, sender, job)
        return

    if job.get("intent") in ("growth_report", "recap"):
        await _send(ctx, sender, _chat(result_text))
        await _send_menu_followup(ctx, sender)
    else:
        await _send(ctx, sender, _chat(result_text, end_session=True))


async def _send_connect_prompt(ctx: "Context", sender: str, job: "dict | None" = None):
    """Send the Twitch connect prompt and stash the pending action.

    Card buttons can't open external URLs in the ASI:One renderer, so the OAuth
    URL goes out as plain (auto-linkified) text. job is stashed under
    pending_connect:{user} so the OAuth callback can auto-resume it after approval.
    """
    user_key = (job or {}).get("user_id") or resolve_user_key(sender)
    if job:
        ctx.storage.set(f"pending_connect:{user_key}", job)
    try:
        authorize_url, _state = await asyncio.to_thread(
            build_authorize_url, user_key, job
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Failed to build authorize URL: {exc}")
        await _send(
            ctx,
            sender,
            _chat(f"Couldn't start the Twitch connect flow: {exc}", end_session=True),
        )
        return
    await _send(
        ctx,
        sender,
        _chat(CONNECT_PROMPT.format(authorize_url=authorize_url), end_session=True),
    )


async def _send(ctx: Context, destination: str, message, **kwargs):
    """ctx.send wrapper with one immediate retry on dispense failure.

    The uagents dispenser intermittently fails/times out talking to
    Agentverse (returns DeliveryStatus.FAILED rather than raising) — seen
    directly in dispatch_timing.py logs as "Timeout waiting for dispense
    response". A single retry recovers most of these without the user ever
    seeing a dropped reply.
    """
    status = await ctx.send(destination, message, **kwargs)
    if status.status != DeliveryStatus.DELIVERED:
        ctx.logger.warning(
            f"send to {destination} failed ({status.detail!r}); retrying once"
        )
        status = await ctx.send(destination, message, **kwargs)
        if status.status != DeliveryStatus.DELIVERED:
            ctx.logger.error(
                f"send to {destination} failed again ({status.detail!r}); giving up"
            )
    return status


def _chat(text: str, end_session: bool = False) -> ChatMessage:
    """Build a Chat Protocol text message. Only set end_session=True on the
    final message — ending it early would close the conversation before a
    payment card or follow-up can render.
    """
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content
    )


async def send_card(
    ctx: "Context",
    sender: str,
    card_kind: str,
    card_payload,
    text: str = "Here are your chat settings:",
):
    """Send an ASI:One card via MetadataContent. card_payload is JSON-stringified
    here (ASI:One falls back to plain text if it gets a raw object); a value
    that's already a JSON string is passed through unchanged.
    """
    payload_str = (
        card_payload if isinstance(card_payload, str) else json.dumps(card_payload)
    )
    metadata = {
        "card_protocol_version": "1",
        "requires_card_interaction": "true",
        "card_kind": card_kind,
        "card_payload": payload_str,
    }
    msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=text),
            MetadataContent(metadata=metadata),
        ],
    )
    return await _send(ctx, sender, msg)  # status lets proactive callers check delivery


def build_chat_settings_card() -> dict:
    """Custom card: one button per toggleable chat setting."""
    return {
        "root": {
            "type": "section",
            "title": "Chat Settings",
            "subtitle": "Tap a setting to toggle it on or off",
            "children": [
                {
                    "type": "button",
                    "label": "Toggle Slow Mode",
                    "primary": True,
                    "action": {"selection": {"chat_setting": "slow"}},
                },
                {
                    "type": "button",
                    "label": "Toggle Followers-Only",
                    "action": {"selection": {"chat_setting": "followers"}},
                },
                {
                    "type": "button",
                    "label": "Toggle Subscribers-Only",
                    "action": {"selection": {"chat_setting": "subs"}},
                },
                {
                    "type": "button",
                    "label": "Toggle Emote-Only",
                    "action": {"selection": {"chat_setting": "emote"}},
                },
            ],
        }
    }


def build_announcement_card() -> dict:
    """Form card collecting message + color; submit sends action=announce_submit."""
    return {
        "title": "Post an announcement",
        "fields": [
            {
                "name": "message",
                "kind": "text",
                "label": "Announcement message",
                "required": True,
            },
            {
                "name": "color",
                "kind": "select",
                "label": "Color",
                "options": [
                    {"value": "primary", "label": "Default"},
                    {"value": "blue", "label": "Blue"},
                    {"value": "green", "label": "Green"},
                    {"value": "orange", "label": "Orange"},
                    {"value": "purple", "label": "Purple"},
                ],
            },
        ],
        "submit_cta": {
            "label": "Post it",
            "selection": {"action": "announce_submit"},
        },
    }


def build_growth_report_card() -> dict:
    """Form card collecting the channel name; submit sends growth_report_submit."""
    return {
        "title": "Channel Growth Report",
        "fields": [
            {
                "name": "channel_name",
                "kind": "text",
                "label": "Twitch channel name",
                "required": True,
            }
        ],
        "submit_cta": {
            "label": "Generate report",
            "selection": {"action": "growth_report_submit"},
        },
    }


def build_menu_card() -> dict:
    """Custom card: main menu with one button per service."""

    def _menu_button(label: str, menu: str, *, primary: bool = False) -> dict:
        btn: dict = {
            "type": "button",
            "label": label,
            "action": {"selection": {"menu": menu}},
        }
        if primary:
            btn["primary"] = True
        return btn

    return {
        "root": {
            "type": "section",
            "title": "twitchy",
            "subtitle": "Pick a service to get started",
            "children": [
                _menu_button("What Did I Miss?", "recap", primary=True),
                _menu_button("Growth Report", "growth_report"),
                _menu_button("Chat Settings", "chat_settings"),
                _menu_button("Post Announcement", "announcement"),
                _menu_button("Find a Raid", "raid"),
                _menu_button("Create Clip", "clip"),
            ],
        }
    }


def build_raid_category_card() -> dict:
    """Form card collecting the raid category before the find + review flow."""
    return {
        "title": "Find a Raid",
        "fields": [
            {
                "name": "category",
                "kind": "text",
                "label": "Category",
                "required": True,
            }
        ],
        "submit_cta": {
            "label": "Find target",
            "selection": {"action": "raid_menu_category"},
        },
    }


def _parse_growth_report_submit(text: str) -> "str | None":
    """Parse a growth-report Form submit, or None if not growth_report_submit.
    ASI:One may send the action/fields flat or nested under "selection" — these
    parsers all check both shapes.
    """
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    action = data.get("action")
    selection = (
        data.get("selection") if isinstance(data.get("selection"), dict) else None
    )
    if not action and selection:
        action = selection.get("action")

    if action != "growth_report_submit":
        return None

    channel_name = data.get("channel_name")
    if channel_name is None and selection:
        channel_name = selection.get("channel_name")
    if isinstance(channel_name, str):
        return channel_name.strip()
    return str(channel_name or "").strip()


def _parse_announcement_submit(text: str) -> "dict | None":
    """Parse an announcement Form submit, or None if not announce_submit."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    action = data.get("action")
    if not action:
        selection = data.get("selection")
        if isinstance(selection, dict):
            action = selection.get("action")

    if action != "announce_submit":
        return None

    message = data.get("message")
    if message is None:
        selection = data.get("selection")
        if isinstance(selection, dict):
            message = selection.get("message")
    message = (
        (message or "").strip()
        if isinstance(message, str)
        else str(message or "").strip()
    )

    color = data.get("color")
    if not color:
        selection = data.get("selection")
        if isinstance(selection, dict):
            color = selection.get("color")
    color = (
        (color or "primary").strip().lower() if isinstance(color, str) else "primary"
    )

    return {"message": message, "color": color}


def _parse_menu_selection(text: str) -> "str | None":
    """Parse a main-menu button tap, or None if not a menu selection."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    menu = data.get("menu")
    selection = (
        data.get("selection") if isinstance(data.get("selection"), dict) else None
    )
    if not menu and selection:
        menu = selection.get("menu")

    if menu in (
        "recap",
        "growth_report",
        "chat_settings",
        "announcement",
        "raid",
        "clip",
    ):
        return menu
    return None


def _parse_raid_menu_category_submit(text: str) -> "str | None":
    """Parse raid category Form submit, or None if not raid_menu_category."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    action = data.get("action")
    selection = (
        data.get("selection") if isinstance(data.get("selection"), dict) else None
    )
    if not action and selection:
        action = selection.get("action")

    if action != "raid_menu_category":
        return None

    category = data.get("category")
    if category is None and selection:
        category = selection.get("category")
    if isinstance(category, str):
        return category.strip()
    return str(category or "").strip()


def _is_greeting_or_help(text: str) -> bool:
    """True for short greetings / help prompts that should show the menu card."""
    normalized = " ".join(text.strip().lower().split())
    normalized = normalized.rstrip("!.?")
    return normalized in {
        "hi",
        "hello",
        "hey",
        "help",
        "what can you do",
    }


def _is_recap_request(text: str) -> bool:
    """True for common 'what did I miss' phrasings — a fast path before the
    LLM classifier so the headline feature responds instantly.
    """
    normalized = " ".join(text.strip().lower().split()).rstrip("!.?")
    if normalized in {
        "recap",
        "what did i miss",
        "what did i miss?",
        "catch me up",
        "summarize chat",
        "summarise chat",
        "who do i need to thank",
    }:
        return True
    return "what did i miss" in normalized or "recap my stream" in normalized


async def _handle_announcement_submit(
    ctx: "Context", sender: str, user_id: str, form_data: dict
):
    """Post an announcement from Form submit fields (deterministic — no LLM)."""
    message = (form_data.get("message") or "").strip()
    color = form_data.get("color") or "primary"

    if not message:
        await _send(
            ctx,
            sender,
            _chat("Please enter an announcement message.", end_session=True),
        )
        return

    result = await asyncio.to_thread(
        send_announcement,
        message=message,
        color=color,
        user_id=user_id,
    )

    if result == NEEDS_CONNECT:
        job = {
            "intent": "announcement",
            "params": {"message": message, "color": color},
            "user_id": user_id,
        }
        await _send_connect_prompt(ctx, sender, job)
        return
    if result.startswith("Error"):
        await _send(ctx, sender, _chat(result, end_session=True))
        return
    await _send(ctx, sender, _chat(result))
    await _send_menu_followup(ctx, sender)


def build_raid_review_card(candidate: dict, game_name: str) -> dict:
    """Review card for the raid confirm step: top candidate + approve/reject."""
    name = candidate.get("user_name") or candidate.get("user_login", "Unknown")
    login = candidate.get("user_login", "")
    channel_display = f"{name} (@{login})" if login else name
    return {
        "title": "Raid this channel?",
        "summary_rows": [
            {"label": "Channel", "value": channel_display},
            {"label": "Category", "value": game_name},
            {"label": "Viewers", "value": str(candidate.get("viewer_count", 0))},
        ],
        "approve_cta": {
            "label": "Raid them",
            "selection": {"action": "raid_approve"},
            "primary": True,
        },
        "reject_cta": {
            "label": "Cancel",
            "selection": {"action": "raid_cancel"},
        },
    }


# What each recommendable chat setting does, shown as context on the reactive
# offer card. Keys are update_chat_settings kwargs (the bool modes).
_REACTIVE_SETTING_BLURB = {
    "slow_mode": "Limits how often each viewer can post a message.",
    "follower_mode": "Only followers can chat.",
    "subscriber_mode": "Only subscribers can chat.",
    "emote_mode": "Only Twitch emotes are allowed in chat.",
}


def build_reactive_offer_card(kind: str, setting: str, label: str) -> dict:
    """Review card recommending one specific chat setting (not the full toggle
    list), in response to a live trouble signal.
    """
    blurb = _REACTIVE_SETTING_BLURB.get(setting, f"Enable {label.lower()}.")
    return {
        "title": f"Enable {label}?",
        "summary_rows": [
            {"label": "What it does", "value": blurb},
        ],
        "approve_cta": {
            "label": f"Yes, enable {label.lower()}",
            "selection": {
                "action": "reactive_apply",
                "setting": setting,
                "label": label,
            },
            "primary": True,
        },
        "reject_cta": {
            "label": "No thanks",
            "selection": {"action": "reactive_dismiss"},
        },
    }


def build_smart_announce_card(message: str) -> dict:
    """Review card offering a drafted announcement. The text + color are
    stashed in ctx.storage under pending_announcement:{user_id}; the CTAs only
    carry the action.
    """
    return {
        "title": "Post this announcement?",
        "summary_rows": [
            {"label": "Announcement", "value": message},
        ],
        "approve_cta": {
            "label": "Post it",
            "selection": {"action": "smart_announce_approve"},
            "primary": True,
        },
        "reject_cta": {
            "label": "No thanks",
            "selection": {"action": "smart_announce_reject"},
        },
    }


async def _handle_raid_intent(ctx: "Context", sender: str, user_id: str, params: dict):
    """Step 1 of the raid flow: find the top candidate and show a review card.
    Stores the candidate under pending_raid:{user_id}; doesn't fire the raid yet.
    """
    game_name = (params.get("game_name") or "").strip()
    if not game_name:
        await _send(
            ctx,
            sender,
            _chat(
                "Which category should I find a raid target in? "
                "Try something like: raid someone in Just Chatting.",
                end_session=True,
            ),
        )
        return

    max_viewers = int(params.get("max_viewers", 100) or 100)
    result = await asyncio.to_thread(
        find_raid_candidates,
        game_name,
        max_viewers=max_viewers,
        limit=1,
        user_id=user_id,
    )

    if result == NEEDS_CONNECT:
        job = {"intent": "raid", "params": params, "user_id": user_id}
        await _send_connect_prompt(ctx, sender, job)
        return

    if isinstance(result, str):
        await _send(ctx, sender, _chat(result, end_session=True))
        return

    top = result[0]
    pending = {
        "broadcaster_id": top["broadcaster_id"],
        "user_login": top["user_login"],
        "user_name": top["user_name"],
        "viewer_count": top["viewer_count"],
        "game_name": game_name,
    }
    ctx.storage.set(f"pending_raid:{user_id}", pending)
    ctx.logger.info(f"Pending raid stored for {user_id}: {pending}")

    await send_card(
        ctx,
        sender,
        "review",
        build_raid_review_card(top, game_name),
        text="I found a raid target — confirm below:",
    )


def _parse_raid_card_action(text: str) -> "str | None":
    """Parse a raid review card approve/cancel tap, or None if not one."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    action = data.get("action")
    if not action:
        selection = data.get("selection")
        if isinstance(selection, dict):
            action = selection.get("action")

    if action in ("raid_approve", "raid_cancel"):
        return action
    return None


async def _handle_raid_card_action(
    ctx: "Context", sender: str, user_id: str, action: str
):
    """Step 2 of the raid flow: approve or cancel the pending raid target."""
    storage_key = f"pending_raid:{user_id}"

    if action == "raid_cancel":
        ctx.storage.remove(storage_key)
        await _send(ctx, sender, _chat("Raid cancelled."))
        await _send_menu_followup(ctx, sender)
        return

    pending = ctx.storage.get(storage_key)
    if not pending:
        await _send(ctx, sender, _chat("No pending raid to confirm.", end_session=True))
        return

    broadcaster_id = pending.get("broadcaster_id")
    name = pending.get("user_name") or pending.get("user_login", "the target")
    login = pending.get("user_login", "")
    channel_display = f"{name} (@{login})" if login else name

    result = await asyncio.to_thread(
        start_raid,
        target_broadcaster_id=broadcaster_id,
        user_id=user_id,
    )

    if result == NEEDS_CONNECT:
        job = {"intent": "raid", "params": pending, "user_id": user_id}
        await _send_connect_prompt(ctx, sender, job)
        return
    if result.startswith("Error"):
        await _send(ctx, sender, _chat(result, end_session=True))
        return

    ctx.storage.remove(storage_key)
    await _send(
        ctx,
        sender,
        _chat(f"Raid started to {channel_display}!\n{result}"),
    )
    await _send_menu_followup(ctx, sender)


# The chat settings the reactive offer is allowed to enable (bool modes only).
_REACTIVE_APPLY_SETTINGS = set(_REACTIVE_SETTING_BLURB)


def _parse_reactive_offer_action(text: str) -> "dict | None":
    """Parse a reactive-offer review card tap, or None if it isn't one."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    selection = (
        data.get("selection") if isinstance(data.get("selection"), dict) else None
    )
    action = data.get("action") or (selection.get("action") if selection else None)
    if action not in ("reactive_apply", "reactive_dismiss"):
        return None
    if action == "reactive_dismiss":
        return {"action": action}

    setting = data.get("setting") or (selection.get("setting") if selection else None)
    label = data.get("label") or (selection.get("label") if selection else None)
    return {"action": action, "setting": setting, "label": label}


async def _handle_reactive_offer_action(
    ctx: "Context", sender: str, user_id: str, parsed: dict
) -> None:
    """Apply or dismiss a reactive chat-settings recommendation."""
    if parsed.get("action") == "reactive_dismiss":
        await _send(
            ctx,
            sender,
            _chat("No problem — I'll leave your chat settings as they are."),
        )
        return

    setting = parsed.get("setting")
    label = parsed.get("label") or (setting or "that setting")
    if setting not in _REACTIVE_APPLY_SETTINGS:
        await _send(
            ctx, sender, _chat(f"Unknown chat setting: {setting!r}.", end_session=True)
        )
        return

    kwargs = {setting: True, "user_id": user_id}
    if setting == "slow_mode":
        kwargs["slow_mode_wait_seconds"] = 30

    result = await asyncio.to_thread(lambda: update_chat_settings(**kwargs))  # type: ignore[arg-type]

    if result == NEEDS_CONNECT:
        job = {"intent": "chat_settings", "params": {setting: True}, "user_id": user_id}
        await _send_connect_prompt(ctx, sender, job)
        return
    if result.startswith("Error"):
        await _send(ctx, sender, _chat(result, end_session=True))
        return

    await _send(ctx, sender, _chat(f"Done — {label} is now on. 👍"))


def _parse_smart_announce_action(text: str) -> "str | None":
    """Parse a smart-announcement review card tap, or None if not one."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    selection = (
        data.get("selection") if isinstance(data.get("selection"), dict) else None
    )
    action = data.get("action") or (selection.get("action") if selection else None)
    if action in ("smart_announce_approve", "smart_announce_reject"):
        return action
    return None


async def _handle_smart_announce_action(
    ctx: "Context", sender: str, user_id: str, action: str
) -> None:
    """Approve or reject a proactively-drafted announcement stashed under
    pending_announcement:{user_id}.
    """
    storage_key = f"pending_announcement:{user_id}"

    if action == "smart_announce_reject":
        ctx.storage.remove(storage_key)
        await _send(ctx, sender, _chat("No problem — I won't post that announcement."))
        return

    pending = ctx.storage.get(storage_key)
    if not pending:
        await _send(
            ctx, sender, _chat("That announcement already expired — nothing to post.")
        )
        return

    message = (pending.get("message") or "").strip()
    color = pending.get("color") or "primary"
    if not message:
        ctx.storage.remove(storage_key)
        await _send(
            ctx, sender, _chat("That announcement was empty — nothing to post.")
        )
        return

    result = await asyncio.to_thread(
        send_announcement, message=message, color=color, user_id=user_id
    )

    if result == NEEDS_CONNECT:
        job = {
            "intent": "announcement",
            "params": {"message": message, "color": color},
            "user_id": user_id,
        }
        await _send_connect_prompt(ctx, sender, job)
        return
    if result.startswith("Error"):
        await _send(ctx, sender, _chat(result, end_session=True))
        return

    ctx.storage.remove(storage_key)
    await _send(ctx, sender, _chat(f"Posted! 📣\n{result}"))


async def _send_menu_card(ctx: "Context", sender: str) -> None:
    await send_card(
        ctx,
        sender,
        "custom",
        build_menu_card(),
        text="Hi, I'm twitchy. What would you like to do?",
    )


async def _send_menu_followup(ctx: "Context", sender: str) -> None:
    await send_card(
        ctx,
        sender,
        "custom",
        build_menu_card(),
        text="Anything else I can help with?",
    )


async def _handle_menu_selection(
    ctx: "Context", sender: str, user_id: str, menu: str
) -> None:
    """Route a main-menu tap to the feature card builders, checking the
    connect gate first for features that need a Twitch token.
    """
    if menu in _CONNECT_REQUIRED_INTENTS:
        job = {"intent": menu, "params": {}, "user_id": user_id}
        if not await _ensure_connected(ctx, sender, user_id, job):
            return

    if menu == "recap":
        await _handle_recap(ctx, sender, user_id)
        return

    if menu == "clip":
        await _handle_create_clip(ctx, sender, user_id)
        return

    if menu == "growth_report":
        await send_card(
            ctx,
            sender,
            "form",
            build_growth_report_card(),
            text="Which channel should I analyze?",
        )
        return

    if menu == "chat_settings":
        await send_card(
            ctx,
            sender,
            "custom",
            build_chat_settings_card(),
            text="Manage your chat settings:",
        )
        return

    if menu == "announcement":
        await send_card(
            ctx,
            sender,
            "form",
            build_announcement_card(),
            text="Set up your announcement:",
        )
        return

    if menu == "raid":
        await send_card(
            ctx,
            sender,
            "form",
            build_raid_category_card(),
            text="Which category should I raid in?",
        )
        return


async def _handle_raid_menu_category_submit(
    ctx: "Context", sender: str, user_id: str, category: str
) -> None:
    """Raid from menu: category form submit -> existing find + review flow."""
    if not category:
        await _send(
            ctx,
            sender,
            _chat("Please enter a category (e.g. Just Chatting).", end_session=True),
        )
        return

    params = {"game_name": category}
    unlocked = bool(ctx.storage.get(f"unlocked:{user_id}"))

    if unlocked:
        await _handle_raid_intent(ctx, sender, user_id, params)
    else:
        await _handle_action(ctx, sender, user_id, "raid", params)


# Maps a chat-settings card button's chat_setting value to the update_chat_settings
# kwarg and a friendly label used in the confirmation reply.
_CHAT_SETTING_CLICK = {
    "slow": ("slow_mode", "Slow mode"),
    "followers": ("follower_mode", "Followers-only mode"),
    "subs": ("subscriber_mode", "Subscribers-only mode"),
    "emote": ("emote_mode", "Emote-only mode"),
}


def _parse_card_selection(text: str) -> "dict | None":
    """Parse an incoming card-click payload into a normalized
    {"selection": {"chat_setting": <value>}}, or None if it isn't one.
    """
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    chat_setting = data.get("chat_setting")
    if not chat_setting:
        selection = data.get("selection")
        if isinstance(selection, dict):
            chat_setting = selection.get("chat_setting")

    if not chat_setting:
        return None

    normalized = {"selection": {"chat_setting": chat_setting}}
    return normalized


async def _handle_chat_setting_click(
    ctx: "Context", sender: str, user_id: str, selection_data: dict
):
    """Route a chat-settings card click: read current state, flip, then PATCH."""
    setting = selection_data.get("selection", {}).get("chat_setting")
    if not setting:
        return

    mapping = _CHAT_SETTING_CLICK.get(setting)
    if not mapping:
        await _send(
            ctx, sender, _chat(f"Unknown chat setting: {setting!r}.", end_session=True)
        )
        return

    kwarg, label = mapping

    current = await asyncio.to_thread(get_chat_settings, user_id=user_id)
    if current == NEEDS_CONNECT:
        job = {"intent": "chat_settings", "params": {}, "user_id": user_id}
        await _send_connect_prompt(ctx, sender, job)
        return
    if isinstance(current, str):
        await _send(ctx, sender, _chat(current, end_session=True))
        return

    now_on = bool(current.get(kwarg, False))
    new_value = not now_on
    kw = {kwarg: new_value, "user_id": user_id}
    result = await asyncio.to_thread(lambda: update_chat_settings(**kw))  # type: ignore[arg-type]

    if result == NEEDS_CONNECT:
        job = {
            "intent": "chat_settings",
            "params": {kwarg: new_value},
            "user_id": user_id,
        }
        await _send_connect_prompt(ctx, sender, job)
        return
    if result.startswith("Error"):
        await _send(ctx, sender, _chat(result, end_session=True))
        return
    state = "on" if new_value else "off"
    await _send(ctx, sender, _chat(f"{label} turned {state}."))
    await _send_menu_followup(ctx, sender)


chat_proto = Protocol(spec=chat_protocol_spec)


# Plain auto-linkified text — card buttons can't open external URLs in the
# ASI:One renderer (see _send_connect_prompt).
CONNECT_PROMPT = (
    "🔗 **Connect your Twitch** to continue — it's a single approval screen:\n\n"
    "{authorize_url}\n\n"
    "Once you're done, head back here. You don't need to re-type anything — I'll "
    "automatically pick up right where you left off."
)

# Tasks ASI:One's built-in Twitch connector already handles, so we don't reimplement them.
CONNECTOR_REDIRECT_MESSAGE = (
    "That's something ASI:One's built-in Twitch tools can handle! Here's how: go to "
    "the sidebar, press 'Connected Services', search for Twitch, and toggle it on. Then "
    "you can ask ASI:One directly (without @twitch-growth-agent) and it'll handle it."
)


def _is_connect_command(text: str) -> bool:
    """True if the message is an explicit 'connect my twitch' request."""
    t = text.strip().lower()
    if t in {"connect", "connect twitch", "connect my twitch", "connect my channel"}:
        return True
    return "connect" in t and "twitch" in t


def resolve_user_key(sender: str) -> str:
    """Per-user key for Twitch token storage/lookup. Centralized here so it
    changes in exactly one place if it ever differs from the sender id.
    """
    return sender


async def _request_payment_for_job(
    ctx: Context, sender: str, job: dict, *, description: str
):
    """Create the embedded Stripe checkout, persist job under
    order:{session_id}, and send the RequestPayment.
    """
    if not stripe.api_key:
        ctx.logger.warning("STRIPE_SECRET_KEY not set; cannot gate payment.")
        await _send(
            ctx,
            sender,
            _chat("Payments aren't configured right now, sorry.", end_session=True),
        )
        return
    try:
        checkout = await asyncio.to_thread(
            create_embedded_checkout_session,
            user_address=sender,
            chat_session_id=uuid4().hex,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Stripe session creation failed: {exc}")
        await _send(
            ctx,
            sender,
            _chat(f"Couldn't start checkout right now: {exc}", end_session=True),
        )
        return

    session_id = checkout["checkout_session_id"]
    ctx.storage.set(f"order:{session_id}", job)

    # metadata values must be str or dict[str, str].
    stripe_meta = {
        "client_secret": checkout["client_secret"],
        "checkout_session_id": session_id,
        "publishable_key": checkout["publishable_key"],
        "currency": checkout["currency"],
        "amount_cents": str(checkout["amount_cents"]),
        "ui_mode": checkout["ui_mode"],  # "embedded" (renderer expectation)
    }
    await _send(
        ctx,
        sender,
        RequestPayment(
            accepted_funds=[
                Funds(
                    currency=STRIPE_CURRENCY.upper(),
                    amount=f"{STRIPE_AMOUNT_CENTS / 100:.2f}",
                    payment_method="stripe",
                )
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=3600,
            reference=job.get("intent", "order"),
            description=description,
            metadata={"stripe": stripe_meta},
        ),
    )


async def _handle_growth_report(
    ctx: Context, sender: str, message_text: str, params: dict, unlocked: bool
):
    """Growth report flow: unlocked users get the full report directly;
    everyone else gets a free preview, then a one-time payment.
    """
    channel = (
        _clean_channel(params.get("channel_name"))
        if params.get("channel_name")
        else None
    )
    if not channel:
        try:
            channel = await asyncio.to_thread(extract_channel_name, message_text)
        except Exception as exc:  # noqa: BLE001
            ctx.logger.error(f"Channel extraction failed: {exc}")
            channel = None

    if not channel:
        ctx.logger.info("No Twitch channel found in message; asking the user.")
        await _send(
            ctx,
            sender,
            _chat(
                "Hey! I analyze Twitch channels and write growth strategy reports. "
                "Which channel would you like me to look at? Just send me the "
                "channel name.",
                end_session=True,
            ),
        )
        return

    job = {
        "intent": "growth_report",
        "params": {"channel_name": channel},
        "user_id": resolve_user_key(sender),
    }

    if unlocked:
        ctx.logger.info(
            f"User {sender} already unlocked -> full report for '{channel}'"
        )
        await _deliver_job(ctx, sender, job)
        return

    ctx.logger.info(f"Extracted channel '{channel}' -> running free preview")
    try:
        display_name, niche = await asyncio.to_thread(run_preview, channel)
    except Exception as exc:  # noqa: BLE001 - surface lookup errors to the user
        ctx.logger.error(f"Preview failed for '{channel}': {exc}")
        await _send(
            ctx,
            sender,
            _chat(
                f"I couldn't find a Twitch channel named '{channel}'. Double-check "
                "the spelling — I just need the channel handle, not the URL.",
                end_session=True,
            ),
        )
        return

    await _send(
        ctx,
        sender,
        _chat(
            f"Free preview for **{display_name}**\n"
            f"• Detected niche: {niche}\n\n"
            f"A one-time {PRICE_LABEL} payment unlocks the full growth strategy "
            f"report (competitor benchmarking, gap analysis, a prioritized action "
            f"plan) PLUS all channel actions — setup, announcements, chat settings, "
            f"raids, and clips. Pay below to unlock."
        ),
    )

    await _request_payment_for_job(
        ctx, sender, job, description=f"Twitch growth report for {display_name}"
    )


async def _handle_action(
    ctx: Context, sender: str, user_id: str, intent: str, params: dict
):
    """Gate a Twitch action behind the one-time unlock payment. Only called
    when the user isn't already unlocked.
    """
    summary = describe_action(intent, params)
    await _send(
        ctx,
        sender,
        _chat(
            f"Got it — I'll {summary}.\n\nThis needs a one-time {PRICE_LABEL} unlock "
            "(covers the growth report and all channel actions). Pay below to unlock "
            "and run it."
        ),
    )
    job = {"intent": intent, "params": params, "user_id": user_id}
    await _request_payment_for_job(
        ctx, sender, job, description=f"Twitch action: {summary}"
    )


async def _handle_recap(ctx: "Context", sender: str, user_id: str) -> None:
    """Deliver a recap of the live-event buffer, gated by the one-time unlock."""
    unlocked = bool(ctx.storage.get(f"unlocked:{user_id}"))
    job = {"intent": "recap", "params": {}, "user_id": user_id}
    if unlocked:
        await _deliver_job(ctx, sender, job)
    else:
        await _handle_action(ctx, sender, user_id, "recap", {})


def _extract_clip_slug(create_clip_result: str) -> "str | None":
    """Pull the clip slug out of create_clip's 'Public URL: .../<slug>' text."""
    match = re.search(r"clips\.twitch\.tv/([A-Za-z0-9_-]+)", create_clip_result)
    return match.group(1) if match else None


# Twitch processes clips async, so the thumbnail isn't ready immediately;
# poll a few times (~5s, ~10s, ~15s after creation) before giving up.
_CLIP_THUMBNAIL_RETRIES = 3
_CLIP_THUMBNAIL_RETRY_GAP_SECONDS = 5


async def _send_clip_preview(ctx: "Context", sender: str, thumb_url: str) -> None:
    """Send the clip's thumbnail with a caption — pairing it with TextContent
    so it isn't dropped by the renderer (same lesson as cards).
    """
    resource = Resource(
        uri=thumb_url, metadata={"mime_type": "image/jpeg", "role": "thumbnail"}
    )
    msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text="Here's the preview:"),
            ResourceContent(resource_id=uuid4(), resource=resource),
        ],
    )
    await _send(ctx, sender, msg)


async def _handle_create_clip(ctx: "Context", sender: str, user_id: str) -> None:
    """Menu 'Create Clip': capture a clip, then show its real thumbnail inline.

    On success, sends the link immediately, then polls Get Clips for the real
    thumbnail_url and sends it as an image; falls back to the link alone if
    that lookup comes up empty.
    """
    unlocked = bool(ctx.storage.get(f"unlocked:{user_id}"))
    if not unlocked:
        await _handle_action(ctx, sender, user_id, "clip", {})
        return

    result = await asyncio.to_thread(create_clip, user_id=user_id)

    if result == NEEDS_CONNECT:
        job = {"intent": "clip", "params": {}, "user_id": user_id}
        await _send_connect_prompt(ctx, sender, job)
        return
    if result.startswith("Error"):
        await _send(ctx, sender, _chat(result))
        await _send_menu_followup(ctx, sender)
        return

    clip_id = _extract_clip_slug(result)
    if not clip_id:
        # Couldn't parse the id -> just relay create_clip's text (it has the URLs).
        await _send(ctx, sender, _chat(result))
        await _send_menu_followup(ctx, sender)
        return

    clip_url = f"https://clips.twitch.tv/{clip_id}"
    await _send(
        ctx, sender, _chat(f"Clip created! 🎬\n{clip_url}\n(grabbing a preview…)")
    )

    # Let Twitch finish processing, then poll Get Clips for the authoritative
    # thumbnail_url — clips can take 10s+ to produce one. Stop on the first hit.
    thumb_url = None
    for attempt in range(1, _CLIP_THUMBNAIL_RETRIES + 1):
        await asyncio.sleep(_CLIP_THUMBNAIL_RETRY_GAP_SECONDS)
        thumb_url = await asyncio.to_thread(get_clip_thumbnail, clip_id, user_id)
        ctx.logger.info(
            f"clip {clip_id} thumbnail attempt {attempt}/{_CLIP_THUMBNAIL_RETRIES} "
            f"(~{attempt * _CLIP_THUMBNAIL_RETRY_GAP_SECONDS}s) -> {thumb_url or 'None'}"
        )
        if thumb_url:
            break

    if thumb_url:
        await _send_clip_preview(ctx, sender, thumb_url)
    else:
        ctx.logger.info(
            f"No thumbnail for clip {clip_id} after {_CLIP_THUMBNAIL_RETRIES} tries — sent link only."
        )

    await _send_menu_followup(ctx, sender)


async def _handle_connector_redirect(ctx: "Context", sender: str) -> None:
    """Point the user at ASI:One's built-in Twitch connector, then re-show the
    menu. Purely informational — no Twitch call, no token, no payment.
    """
    await _send(ctx, sender, _chat(CONNECTOR_REDIRECT_MESSAGE))
    await _send_menu_card(ctx, sender)


# Features that act on the user's own channel and need a connected token.
# growth_report is excluded — it only reads public data with the app token.
_CONNECT_REQUIRED_INTENTS = {"chat_settings", "announcement", "raid", "clip"}


async def _ensure_connected(
    ctx: "Context", sender: str, user_id: str, job: dict
) -> bool:
    """Upfront connect gate, called before showing a token-using feature's
    card. If not connected, sends the connect prompt and stashes job for the
    OAuth callback to auto-resume after approval.
    """
    if await asyncio.to_thread(is_connected, user_id):
        return True
    ctx.logger.info(
        f"Upfront connect gate: {user_id} not connected -> connect prompt ({job!r})."
    )
    await _send_connect_prompt(ctx, sender, job)
    return False


async def _open_feature(
    ctx: "Context", sender: str, user_id: str, intent: str, params: dict
) -> None:
    """Open a feature for an already-connected user: show its card, or run it
    directly if params were already supplied. Used by the connect-resume path
    to land the user back where the connect gate interrupted them.
    """
    if intent == "chat_settings":
        await send_card(
            ctx,
            sender,
            "custom",
            build_chat_settings_card(),
            text="Manage your chat settings:",
        )
    elif intent == "announcement":
        if (params.get("message") or "").strip():
            await _handle_announcement_submit(ctx, sender, user_id, params)
        else:
            await send_card(
                ctx,
                sender,
                "form",
                build_announcement_card(),
                text="Set up your announcement:",
            )
    elif intent == "raid":
        game_name = (params.get("game_name") or "").strip()
        if game_name:
            await _handle_raid_menu_category_submit(ctx, sender, user_id, game_name)
        else:
            await send_card(
                ctx,
                sender,
                "form",
                build_raid_category_card(),
                text="Which category should I raid in?",
            )
    elif intent == "clip":
        await _handle_create_clip(ctx, sender, user_id)
    else:
        await _send_menu_followup(ctx, sender)


async def _resume_after_connect(
    ctx: "Context", sender: str, user_id: str, job: "dict | None"
) -> None:
    """Deliver the user's pending action after they connect Twitch, or just
    re-show the menu if there wasn't one.
    """
    session = _user_sessions.get(user_id)
    if session is not None:
        ctx._session = session  # routes into the user's real ASI:One thread

    if not job:
        await _send(
            ctx, sender, _chat("✅ Twitch connected! What would you like to do?")
        )
        await _send_menu_card(ctx, sender)
        return

    ctx.logger.info(f"Resuming pending action for {user_id} after connect: {job!r}")
    await _send(
        ctx, sender, _chat("✅ Twitch connected — picking up where you left off…")
    )
    await _open_feature(
        ctx, sender, user_id, job.get("intent") or "", job.get("params") or {}
    )


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    """Free preview (channel + niche) + a Stripe RequestPayment for the report."""
    ctx.logger.info(f"on_chat from sender: {sender}")
    await _send(
        ctx,
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
        ),
    )

    message_text = ""
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Chat session started with {sender}")
        elif isinstance(item, TextContent):
            message_text += item.text

    message_text = message_text.strip()
    if not message_text:
        return

    ctx.logger.info(f"Chat message from {sender}: {message_text!r}")

    user_id = resolve_user_key(sender)

    # So proactive cards can be sent into this user's open ASI:One thread later.
    _user_sessions[user_id] = ctx.session

    # Idempotent and non-fatal — no token just skips quietly.
    try:
        listener_manager.ensure_started(user_id)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Could not start EventSub listener for {user_id}: {exc}")

    if message_text.lower() == "reset access":
        ctx.storage.set(f"unlocked:{user_id}", False)
        ctx.logger.info(f"Access reset for {user_id}.")
        await _send(
            ctx,
            sender,
            _chat(
                "Your access has been reset. You'll need to pay the one-time "
                f"{PRICE_LABEL} unlock again to use the assistant.",
                end_session=True,
            ),
        )
        return

    if _is_connect_command(message_text):
        try:
            authorize_url, _state = await asyncio.to_thread(
                build_authorize_url, user_id
            )
        except Exception as exc:  # noqa: BLE001
            ctx.logger.error(f"Failed to build authorize URL: {exc}")
            await _send(
                ctx,
                sender,
                _chat(
                    f"Couldn't start the Twitch connect flow: {exc}", end_session=True
                ),
            )
            return
        await _send(
            ctx,
            sender,
            _chat(CONNECT_PROMPT.format(authorize_url=authorize_url), end_session=True),
        )
        return

    # Each of these is checked before classify_intent's LLM call.
    menu = _parse_menu_selection(message_text)
    if menu is not None:
        ctx.logger.info(f"Menu selection from {user_id}: {menu}")
        await _handle_menu_selection(ctx, sender, user_id, menu)
        return

    raid_category = _parse_raid_menu_category_submit(message_text)
    if raid_category is not None:
        ctx.logger.info(f"Raid category form submit from {user_id}: {raid_category!r}")
        await _handle_raid_menu_category_submit(ctx, sender, user_id, raid_category)
        return

    selection_data = _parse_card_selection(message_text)
    if selection_data is not None:
        ctx.logger.info(f"Chat-settings card click from {user_id}: {selection_data}")
        await _handle_chat_setting_click(ctx, sender, user_id, selection_data)
        return

    raid_action = _parse_raid_card_action(message_text)
    if raid_action is not None:
        ctx.logger.info(f"Raid card action from {user_id}: {raid_action}")
        await _handle_raid_card_action(ctx, sender, user_id, raid_action)
        return

    reactive_action = _parse_reactive_offer_action(message_text)
    if reactive_action is not None:
        ctx.logger.info(f"Reactive offer action from {user_id}: {reactive_action}")
        await _handle_reactive_offer_action(ctx, sender, user_id, reactive_action)
        return

    smart_announce_action = _parse_smart_announce_action(message_text)
    if smart_announce_action is not None:
        ctx.logger.info(
            f"Smart announce action from {user_id}: {smart_announce_action}"
        )
        await _handle_smart_announce_action(ctx, sender, user_id, smart_announce_action)
        return

    announcement_submit = _parse_announcement_submit(message_text)
    if announcement_submit is not None:
        ctx.logger.info(
            f"Announcement form submit from {user_id}: {announcement_submit}"
        )
        await _handle_announcement_submit(ctx, sender, user_id, announcement_submit)
        return

    # Growth-report Form submit — channel comes directly from JSON, not the LLM.
    growth_report_channel = _parse_growth_report_submit(message_text)
    if growth_report_channel is not None:
        channel = (
            _clean_channel(growth_report_channel) if growth_report_channel else None
        )
        if not channel:
            await _send(
                ctx,
                sender,
                _chat("Please enter a Twitch channel name.", end_session=True),
            )
            return
        unlocked = bool(ctx.storage.get(f"unlocked:{user_id}"))
        ctx.logger.info(
            f"Growth report form submit from {user_id}: channel={channel!r}"
        )
        await _handle_growth_report(
            ctx, sender, message_text, {"channel_name": channel}, unlocked
        )
        return

    if _is_recap_request(message_text):
        ctx.logger.info(f"Recap request from {user_id} (deterministic match).")
        await _handle_recap(ctx, sender, user_id)
        return

    classification = await asyncio.to_thread(classify_intent, message_text)
    intent = classification["intent"]
    params = classification["params"]
    ctx.logger.info(f"Intent '{intent}' params={params}")

    if intent == "recap":
        ctx.logger.info(f"Recap intent from {user_id}.")
        await _handle_recap(ctx, sender, user_id)
        return

    if intent == "unknown" or _is_greeting_or_help(message_text):
        ctx.logger.info(
            f"Menu card for {user_id} (intent={intent!r}, "
            f"greeting={_is_greeting_or_help(message_text)})"
        )
        await _send_menu_card(ctx, sender)
        return

    if intent == "connector_redirect":
        ctx.logger.info(f"Connector redirect for {user_id}.")
        await _handle_connector_redirect(ctx, sender)
        return

    if intent == "chat_settings":
        job = {"intent": "chat_settings", "params": params, "user_id": user_id}
        if not await _ensure_connected(ctx, sender, user_id, job):
            return
        ctx.logger.info(f"Chat-settings card requested by {user_id}.")
        await send_card(ctx, sender, "custom", build_chat_settings_card())
        return

    if intent == "announcement" and not (params.get("message") or "").strip():
        job = {"intent": "announcement", "params": params, "user_id": user_id}
        if not await _ensure_connected(ctx, sender, user_id, job):
            return
        ctx.logger.info(f"Announcement form requested by {user_id}.")
        await send_card(
            ctx,
            sender,
            "form",
            build_announcement_card(),
            text="Set up your announcement:",
        )
        return

    unlocked = bool(ctx.storage.get(f"unlocked:{user_id}"))

    if intent == "growth_report":
        channel = (
            _clean_channel(params.get("channel_name"))
            if params.get("channel_name")
            else None
        )
        if not channel:
            ctx.logger.info(f"Growth report form requested by {user_id}.")
            await send_card(
                ctx,
                sender,
                "form",
                build_growth_report_card(),
                text="Which channel should I analyze?",
            )
            return
        await _handle_growth_report(ctx, sender, message_text, params, unlocked)
        return

    if intent == "raid":
        job = {"intent": "raid", "params": params, "user_id": user_id}
        if not await _ensure_connected(ctx, sender, user_id, job):
            return
        if unlocked:
            ctx.logger.info(f"Raid intent from {user_id} -> review card flow.")
            await _handle_raid_intent(ctx, sender, user_id, params)
        else:
            await _handle_action(ctx, sender, user_id, intent, params)
        return

    if intent in _CONNECT_REQUIRED_INTENTS:
        job = {"intent": intent, "params": params, "user_id": user_id}
        if not await _ensure_connected(ctx, sender, user_id, job):
            return

    if unlocked:
        ctx.logger.info(f"User {user_id} already unlocked -> running '{intent}' now.")
        job = {"intent": intent, "params": params, "user_id": user_id}
        await _deliver_job(ctx, sender, job)
        return

    await _handle_action(ctx, sender, user_id, intent, params)


@chat_proto.on_message(ChatAcknowledgement)
async def on_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"on_chat_ack from sender: {sender}")
    ctx.logger.info(f"Chat message {msg.acknowledged_msg_id} acknowledged by {sender}")


# Announcement highlight color per 5d moment kind (a send_announcement color).
_ANNOUNCE_COLOR = {
    "big_cheer": "purple",
    "sub_milestone": "green",
    "new_follow": "blue",
}


def _announce_noticed(moment: dict) -> str:
    """Companion text above the 5d announcement card explaining the moment."""
    if moment["kind"] == "big_cheer":
        return (
            f"💜 {moment['user']} just cheered {moment['bits']} bits — "
            "want to thank them on stream?"
        )
    if moment["kind"] == "new_follow":
        return f"👋 {moment['user']} just followed — want to welcome them on stream?"
    return (
        f"🎉 You just passed {moment['count']} subs this stream — want to celebrate it?"
    )


async def _proactive_send_card(
    ctx, user_id, card_payload, text, label
) -> "object | None":
    """Send an agent-initiated review card into the user's existing ASI:One
    thread (an interval ctx's own session is unseen by the client and gets
    dropped). Returns the MsgStatus so the caller can gate its cooldown.
    """
    session = _user_sessions.get(user_id)
    if session is not None:
        ctx._session = session
    ctx.logger.info(f"Proactive {label} offer -> {user_id} (session={session})")
    status = await send_card(ctx, user_id, "review", card_payload, text=text)
    ctx.logger.info(
        f"  {user_id}: card send status={getattr(status, 'status', None)} "
        f"detail={getattr(status, 'detail', '')}"
    )
    return status


def _send_succeeded(status) -> bool:
    """True unless the send explicitly FAILED (so we can retry next tick)."""
    return getattr(status, "status", None) != DeliveryStatus.FAILED
