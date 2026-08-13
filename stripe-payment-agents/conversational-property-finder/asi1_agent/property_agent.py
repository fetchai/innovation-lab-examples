"""
ASI1 Property Finder agent: receives ChatMessage, parses intent, updates state,
calls Repliers, formats response, sends ChatMessage reply.
Optional: Payment Protocol (Stripe) to charge a small amount for full listing details.
"""

import asyncio
import os
import re
from datetime import datetime, timezone
from html import escape
from uuid import uuid4
from typing import Any

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CompletePayment,
    Funds,
    RequestPayment,
    RejectPayment,
    CommitPayment,
)

from .nl_parser import parse_filters
from .llm_parser import llm_interpret
from .state_manager import get_state, merge_parsed_into_state, next_page, update_state

# repliers_client is a sibling package of asi1_agent, so the example directory
# has to be importable. It cannot be a package itself: its name has a hyphen.
import sys
from pathlib import Path

_agent_dir = Path(__file__).resolve().parent
_example_root = _agent_dir.parent
if str(_example_root) not in sys.path:
    sys.path.insert(0, str(_example_root))

from repliers_client.client import search_listings, fetch_listing_by_mls  # noqa: E402
from repliers_client.formatter import (  # noqa: E402
    format_listings as format_listings_text,
    format_listing_details,
    format_listing_full,
)

from . import stripe_payments as stripe_payments_mod  # noqa: E402
from .payment_proto import build_payment_proto  # noqa: E402

# ASI:One helper is kept for optional non-search chat features
try:
    import resend  # type: ignore[import]
except ImportError:  # pragma: no cover - optional email export
    resend = None  # type: ignore[assignment]

# Load .env from asi1_agent directory so it works when run from project root
load_dotenv(_agent_dir / ".env")

# --- Agent setup (ASI1 compatible) ---
agent_seed = os.getenv("AGENT_SECRET_KEY_1")
if not agent_seed:
    raise ValueError("AGENT_SECRET_KEY_1 not set in .env")

agent_port = int(os.getenv("AGENT_PORT", "8000"))
use_mailbox = os.getenv("USE_MAILBOX", "true").lower() == "true"
agent_endpoint = os.getenv("AGENT_ENDPOINT_URL")

agent_kwargs = {
    "name": "Property Finder",
    "seed": agent_seed,
    "port": agent_port,
}
if use_mailbox:
    agent_kwargs["mailbox"] = True
elif agent_endpoint:
    agent_kwargs["endpoint"] = [f"{agent_endpoint}/submit"]

agent = Agent(**agent_kwargs)

# --- Chat protocol ---
chat_proto = Protocol(spec=chat_protocol_spec)

# Keep last page of listings per session so the user can say
# "the second one" and get more details.

_LAST_RESULTS: dict[str, list[dict[str, Any]]] = {}
# Simple in-memory wishlist per session (no persistence across restarts)
_WISHLISTS: dict[str, list[dict[str, Any]]] = {}
# Track the last listing index the user explicitly referenced (e.g. via 'details 2')
_LAST_SELECTED_INDEX: dict[str, int] = {}
# Pending Stripe payments for "details": keyed by Stripe Checkout Session id (cs_...).
# ASI1 embedded checkout passes that same id as CommitPayment.transaction_id; verify uses Session.retrieve(cs_).
_PENDING_DETAILS_PAYMENTS: dict[str, dict[str, Any]] = {}
# Also keep most recent pending payment per chat session so we can handle ASI1's
# "<stripe:payment_id:...:CONFIRM>" chat messages (sender can change per message).
_PENDING_DETAILS_BY_SESSION: dict[str, dict[str, Any]] = {}
# Fallback "conversation" key when ASI1 does not provide a stable chat id and sender changes per message.
_FALLBACK_SESSION_KEY = "asi1_chat_session"
_WARNED_NO_CHAT_ID = False


def _send_wishlist_email(listings: list[dict[str, Any]], to_email: str) -> bool:
    """
    Send a detailed email summary of wishlist listings via Resend.
    Uses EMAIL_API_KEY from the environment. Returns True on best-effort success.
    """
    api_key = (os.getenv("EMAIL_API_KEY") or "").strip()
    if not api_key or not resend:
        return False
    resend.api_key = api_key

    # Build a detailed HTML body reusing the same formatting as the chat "details" view.
    sections: list[str] = []
    for idx, lst in enumerate(listings, start=1):
        mls = lst.get("mls")
        raw = fetch_listing_by_mls(mls) if mls else None
        if raw:
            text_block = format_listing_full(lst, raw, idx)
        else:
            text_block = format_listing_details(lst, idx)
        # Escape for HTML and preserve newlines
        html_block = f"<h3>Listing #{idx}</h3><pre>{escape(text_block)}</pre>"
        sections.append(html_block)

    body = (
        "<p>Here are the listings currently in your Property Finder wishlist:</p>"
        + "".join(sections)
        + "<p>You can continue refining your search or request more listings inside the chat agent.</p>"
    )

    try:
        resend.Emails.send(  # type: ignore[union-attr]
            {
                "from": "Property Finder <onboarding@resend.dev>",
                "to": to_email,
                "subject": "Your Property Finder wishlist",
                "html": body,
            }
        )
        return True
    except Exception:
        return False


def _get_user_text(msg: ChatMessage) -> str | None:
    """Extract user text from ChatMessage content (TextContent)."""
    for item in msg.content or []:
        if hasattr(item, "text"):
            return getattr(item, "text", None) or None
    return None


def _strip_agent_mention(text: str) -> str:
    """
    Remove a leading @agent... mention that ASI1 often prepends, e.g.:
    '@agent1abc... more' -> 'more'
    """
    if not text:
        return ""
    return re.sub(r"^@\S+\s+", "", text).strip()


def _normalize_text(text: str) -> str:
    """Strip, lower, collapse spaces, remove trailing punctuation."""
    if not text:
        return ""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t).strip()
    t = t.rstrip(".")
    return t


def _parse_create_sheet_fallback(text: str) -> dict | None:
    # Google Sheets integration removed for production demo.
    return None


# Pagination-only continuations after "more" (must not match real searches like
# "more spacious apartments in austin", which should go through the LLM).
_MORE_PAGINATION_TAIL = re.compile(
    r"^more\s+("
    r"please"
    r"|results?"
    r"|listings?"
    r"|options?"
    r"|properties?"
    r"|homes?"
    r"|houses?"
    r"|places?"
    r"|units?"
    r")(\s+please)?$"
)


def _is_more_request(text: str) -> bool:
    t = _normalize_text(text)
    if t in ("more", "more listings", "next", "next page"):
        return True
    if t in (
        "more please",
        "show more",
        "see more",
        "any more",
        "give me more",
    ):
        return True
    if _MORE_PAGINATION_TAIL.match(t):
        return True
    return False


def _is_refinement_only(text: str) -> bool:
    """True if message looks like a refinement (e.g. 'under 550k', 'only condos') not a full new search."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # Refinement-like: short, no "find" / "search" / "looking for"
    refinement_starters = (
        "refine",
        "under",
        "only",
        "change to",
        "make it",
        "filter",
        "just",
        "max ",
    )
    if any(t.startswith(p) or p in t for p in refinement_starters):
        return True
    if t.isdigit() or re.match(r"^\d+\s*bed", t):
        return True
    if re.search(r"under\s*\$\d|under\s*\d+k", t):
        return True
    return False


def _parse_wishlist_command(text: str) -> tuple[str, int | None] | None:
    """
    Detect simple wishlist commands.
    Returns (action, index) where action is one of:
    - 'wishlist_add' with index (1-based) to save a listing
    - 'wishlist_show' with index=None
    - 'wishlist_clear' with index=None
    or None if not a wishlist-related message.
    """
    if not text:
        return None
    t = _normalize_text(text)
    # Normalize a few common typos so commands like "show my wishlit" still work.
    t = (
        t.replace("wishlit", "wishlist")
        .replace("wihslist", "wishlist")
        .replace("wishlst", "wishlist")
    )
    if (
        "wishlist" not in t
        and "favorite" not in t
        and "favourite" not in t
        and "saved" not in t
    ):
        return None

    # If the user mentions both "export" and "wishlist" in any order,
    # treat it as an export request (e.g. "export my wishlist to you@example.com").
    if "export" in t and "wishlist" in t:
        return ("wishlist_export", None)

    # Clear wishlist
    if any(
        word in t
        for word in ("clear wishlist", "empty wishlist", "reset wishlist", "remove all")
    ):
        return ("wishlist_clear", None)

    # Export wishlist to a Google Sheet
    if any(
        phrase in t
        for phrase in (
            "export wishlist",
            "wishlist sheet",
            "wishlist excel",
            "export my saved",
            "export saved listings",
        )
    ):
        return ("wishlist_export", None)

    # Add the last referenced listing if user says "add this/it to my wishlist"
    if any(
        phrase in t
        for phrase in (
            "add this to my wishlist",
            "add it to my wishlist",
            "save this to my wishlist",
            "save it to my wishlist",
            "add to my wishlist",
            "save to my wishlist",
        )
    ):
        return ("wishlist_add", None)

    # Add a specific listing to wishlist (look for a number or ordinal)
    idx: int | None = None
    m = re.search(r"\b(\d+)\b", t)
    if m:
        try:
            idx = int(m.group(1))
        except ValueError:
            idx = None
    else:
        ordinals = {
            "first": 1,
            "1st": 1,
            "second": 2,
            "2nd": 2,
            "third": 3,
            "3rd": 3,
            "fourth": 4,
            "4th": 4,
            "fifth": 5,
            "5th": 5,
        }
        for word, val in ordinals.items():
            if word in t:
                idx = val
                break

    if idx is not None:
        return ("wishlist_add", idx)

    # Show wishlist (no clear add intent but mentions wishlist/favorites)
    if any(
        word in t
        for word in (
            "show wishlist",
            "my wishlist",
            "view wishlist",
            "see wishlist",
            "saved listings",
            "my saved",
        )
    ):
        return ("wishlist_show", None)

    # Fallback: treat as show wishlist
    return ("wishlist_show", None)


def _detect_intent(text: str, has_existing_state: bool) -> str:
    """Returns: 'new_search' | 'refinement' | 'more'."""
    if _is_more_request(text):
        return "more"
    if has_existing_state and _is_refinement_only(text):
        return "refinement"
    return "new_search"


def _search_summary(state: dict) -> str:
    """Short label for the search (used as sheet title)."""
    parts = []
    if state.get("location"):
        parts.append(str(state["location"]))
    if state.get("bedrooms"):
        parts.append(f"{state['bedrooms']}br")
    if state.get("max_price"):
        parts.append(f"under ${state['max_price']:,}")
    if state.get("deal_type") == "rent":
        parts.append("rental")
    return " ".join(parts) or "Property search"


async def _handle_search(
    ctx: Context, sender: str, session_id: str, state: dict
) -> str:
    """Call Repliers, format listings, optionally export to Google Sheet, return reply text."""
    try:
        listings, meta = search_listings(state, export_page_size=None)
        # If the user paged ("more") past the end, roll back to the previous page and show a clearer message.
        if not listings and int(state.get("page", 1)) > 1:
            prev_page = max(1, int(state.get("page", 1)) - 1)
            update_state(session_id, page=prev_page)
            return (
                "No more listings on the next page for your current filters.\n\n"
                "Try:\n"
                '- "more" (after broadening filters)\n'
                '- "under $X" (higher)\n'
                '- "2 bedrooms" (or fewer)\n'
                '- "only condos"'
            )
        # Save results for follow-up "details" questions, but only if we actually got some
        if listings:
            _LAST_RESULTS[session_id] = listings
        has_more = meta.get("has_more", False)
        reply = format_listings_text(
            listings,
            location=state.get("location"),
            max_price=state.get("max_price"),
            page=state.get("page", 1),
            has_more=has_more,
        )
        return reply
    except ValueError as e:
        return f"Configuration error: {e}. Please set REPLIERS_API_KEY."
    except Exception as e:
        return f"Sorry, I couldn't fetch listings right now: {e}. Please try again or rephrase."


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat: parse intent, update state, call API, reply."""
    # Key state by a stable conversation identifier if available.
    # In ASI1 mailbox mode, `sender` can change between messages for the same human user.
    session_id = None
    try:
        # ChatMessage is a pydantic model in uagents-core
        dump = msg.model_dump() if hasattr(msg, "model_dump") else {}
        session_id = (
            dump.get("session_id")
            or dump.get("session")
            or dump.get("chat_id")
            or dump.get("conversation_id")
            or dump.get("thread_id")
        )
        if not session_id:
            # Some deployments place identifiers in metadata
            md = dump.get("metadata") if isinstance(dump, dict) else None
            if isinstance(md, dict):
                session_id = (
                    md.get("session_id")
                    or md.get("chat_id")
                    or md.get("conversation_id")
                    or md.get("thread_id")
                )
        if not session_id:
            # If the message model only has (content, msg_id, timestamp), ASI1 is not giving us a stable chat id.
            # In that case, use a single rolling session key so "more"/refine works in a live demo even if sender changes.
            global _WARNED_NO_CHAT_ID
            if isinstance(dump, dict) and sorted(list(dump.keys())) == [
                "content",
                "msg_id",
                "timestamp",
            ]:
                session_id = _FALLBACK_SESSION_KEY
                if not _WARNED_NO_CHAT_ID:
                    _WARNED_NO_CHAT_ID = True
                    ctx.logger.warning(
                        "No stable chat id found in ChatMessage; using fallback session key %r (sender may change per message).",
                        _FALLBACK_SESSION_KEY,
                    )
            else:
                session_id = str(sender)
        # Emit one compact log line that helps confirm which ID is stable
        ctx.logger.info(
            "chat_ids sender=%s session_id=%s dump_keys=%s",
            sender,
            session_id,
            sorted(list(dump.keys()))[:25],
        )
    except Exception:
        session_id = str(sender)
    user_text = _get_user_text(msg)
    # ASI1 messages often start with an @agent... mention; strip it so intent detection works
    user_text = _strip_agent_mention(user_text or "")
    if not user_text:
        reply = ChatMessage(
            content=[
                TextContent(
                    type="text",
                    text='Send me a property search, e.g. "Find 2 bedroom homes under $600k in Austin."',
                )
            ],
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.send(sender, reply)
        return

    # ASI1 Stripe embedded checkout can send a chat confirmation message like:
    # "<stripe:payment_id:UUID:CONFIRM>". This is not a user search message.
    # Handle it by verifying the most recent pending checkout for this chat session.
    if (
        isinstance(user_text, str)
        and user_text.strip().startswith("<stripe:payment_id:")
        and user_text.strip().endswith(":CONFIRM>")
    ):
        pending = _PENDING_DETAILS_BY_SESSION.get(session_id)
        if not pending:
            # Nothing pending; ignore quietly
            return
        checkout_session_id = pending.get("checkout_session_id")
        idx = pending.get("listing_index")
        listings = _LAST_RESULTS.get(session_id) or []
        if not checkout_session_id or not idx or not (1 <= int(idx) <= len(listings)):
            _PENDING_DETAILS_BY_SESSION.pop(session_id, None)
            return
        paid = await asyncio.to_thread(
            stripe_payments_mod.verify_checkout_session_paid, checkout_session_id
        )
        if not paid:
            # Payment may still be processing; don't clear pending yet.
            await ctx.send(
                sender,
                ChatMessage(
                    content=[
                        TextContent(
                            type="text",
                            text="Payment received signal detected, but Stripe still shows it as unpaid. Please wait a moment and try again.",
                        )
                    ],
                    msg_id=uuid4(),
                    timestamp=datetime.now(timezone.utc),
                ),
            )
            return
        # Deliver details
        _PENDING_DETAILS_BY_SESSION.pop(session_id, None)
        _LAST_SELECTED_INDEX[session_id] = int(idx)
        listing = listings[int(idx) - 1]
        mls = listing.get("mls")
        raw = await asyncio.to_thread(fetch_listing_by_mls, mls) if mls else None
        card = (
            format_listing_full(listing, raw, int(idx))
            if raw
            else format_listing_details(listing, int(idx))
        )
        reply_text = f"Here are the full details for listing #{idx}:\n\n{card}"
        await ctx.send(
            sender,
            ChatMessage(
                content=[TextContent(type="text", text=reply_text)],
                msg_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        return

    # Optional: send ack for long-running work
    try:
        ack = ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id,
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.send(sender, ack)
    except Exception:
        pass

    current_state = get_state(session_id)
    has_state = any(
        current_state.get(k) is not None
        for k in ("location", "max_price", "bedrooms", "property_type", "deal_type")
    )
    try:
        ctx.logger.info(
            "chat_in sender=%s session_id=%s has_state=%s text=%r state=%s",
            sender,
            session_id,
            has_state,
            user_text,
            {
                k: current_state.get(k)
                for k in (
                    "location",
                    "deal_type",
                    "bedrooms",
                    "max_price",
                    "property_type",
                    "page",
                )
            },
        )
    except Exception:
        pass
    # First, handle wishlist commands (save/show/clear) before normal intent flow
    wishlist_cmd = _parse_wishlist_command(user_text)
    if wishlist_cmd:
        action, idx = wishlist_cmd
        listings = _LAST_RESULTS.get(session_id) or []
        if action == "wishlist_add":
            # If no explicit index was provided (e.g. "add this to my wishlist"),
            # fall back to the last listing the user referenced (via 'details N').
            if (
                idx is None or not isinstance(idx, int)
            ) and session_id in _LAST_SELECTED_INDEX:
                idx = _LAST_SELECTED_INDEX.get(session_id)

            if not listings:
                reply_text = (
                    "Do a property search first, then say something like "
                    '"save 2 to my wishlist" or "add the first one to my favorites."'
                )
            elif not idx or not (1 <= int(idx) <= len(listings)):
                reply_text = (
                    "I couldn't match that to a listing. After a search you can say "
                    '"save 1 to my wishlist" or "add the second one to favorites."'
                )
            else:
                listing = listings[int(idx) - 1]
                wl = _WISHLISTS.setdefault(session_id, [])
                # Avoid duplicate entries for the same MLS in this session's wishlist
                mls_new = listing.get("mls")
                if any(
                    (item.get("mls") == mls_new and mls_new is not None) for item in wl
                ):
                    reply_text = (
                        f"Listing #{idx} is already in your wishlist.\n\n"
                        'Say "show my wishlist" to see everything you\'ve saved in this chat.'
                    )
                else:
                    wl.append(listing)
                    reply_text = (
                        f"I've added listing #{idx} to your wishlist.\n\n"
                        'Say "show my wishlist" to see everything you\'ve saved in this chat.'
                    )
        elif action == "wishlist_export":
            saved = _WISHLISTS.get(session_id) or []
            if not saved:
                reply_text = (
                    "Your wishlist is empty, so there is nothing to export.\n\n"
                    'After a search you can save a result with "save 1 to my wishlist", '
                    'then say "export wishlist" or "email my wishlist to you@example.com".'
                )
            else:
                # Allow user to specify email in the message text, e.g. "export wishlist to you@example.com".
                email_from_text = None
                m = re.search(
                    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
                    user_text or "",
                    re.IGNORECASE,
                )
                if m:
                    email_from_text = m.group(1).strip()

                to_email = email_from_text or (os.getenv("EMAIL_TO") or "").strip()
                if not to_email:
                    reply_text = (
                        "I can email your wishlist, but I don't know where to send it.\n\n"
                        "Either add your email to the message (e.g. `export wishlist to you@example.com`) "
                    )
                else:
                    sent = await asyncio.to_thread(
                        _send_wishlist_email, saved, to_email
                    )
                    if sent:
                        reply_text = (
                            f"I've emailed your wishlist to {to_email}.\n\n"
                            'You can also view your saved listings here with "show my wishlist".'
                        )
                    else:
                        reply_text = (
                            "I tried to email your wishlist but something went wrong.\n\n"
                            "Check that EMAIL_API_KEY is set with a valid Resend API key and that the "
                            "`resend` Python package is installed in the agent environment."
                        )
        elif action == "wishlist_show":
            saved = _WISHLISTS.get(session_id) or []
            if not saved:
                reply_text = (
                    "Your wishlist is empty.\n\n"
                    "After a search you can save a result by saying "
                    '"save 1 to my wishlist" or "add the second one to favorites."'
                )
            else:
                # Reuse listing formatter for consistency
                body = format_listings_text(
                    saved,
                    location=None,
                    max_price=None,
                    page=1,
                    has_more=False,
                )
                # Tweak the header text slightly
                if body.startswith("Here are the listings:"):
                    body = body.replace(
                        "Here are the listings:", "Here are your saved listings:", 1
                    )
                reply_text = body
        else:  # wishlist_clear
            if session_id in _WISHLISTS:
                _WISHLISTS.pop(session_id, None)
                reply_text = "Your wishlist has been cleared for this chat."
            else:
                reply_text = "Your wishlist is already empty."

        reply = ChatMessage(
            content=[TextContent(type="text", text=reply_text)],
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.send(sender, reply)
        return

    # Otherwise, let local logic handle explicit "more"
    intent = _detect_intent(user_text, has_state)
    local_intent = intent

    # Optionally use OpenAI to interpret complex natural language into filters/intent
    llm_result = None
    if intent != "more":  # no need to call LLM for simple 'more'
        try:
            llm_result = llm_interpret(user_text, current_state)
        except Exception:
            llm_result = None
        if llm_result and isinstance(llm_result, dict):
            llm_intent = llm_result.get("intent")
            # Let the LLM refine searches and pick details intents,
            # but do not let it override our local 'more' detection.
            if llm_intent in ("new_search", "refinement", "details"):
                # Guardrail: if our local heuristic says this message is a refinement-only
                # (e.g. "under $2300") and we have existing state, do NOT let the LLM
                # reclassify it as a brand new search that would clear location/type.
                if local_intent == "refinement" and llm_intent == "new_search":
                    llm_filters = (
                        llm_result.get("filters")
                        if isinstance(llm_result.get("filters"), dict)
                        else {}
                    )
                    # Only allow switching to new_search if the user actually provided a new location.
                    if llm_filters and llm_filters.get("location"):
                        intent = "new_search"
                    else:
                        intent = "refinement"
                else:
                    intent = llm_intent

    if intent == "more":
        if not has_state:
            reply_text = (
                'Do a search first (e.g. "Find 2 bedroom homes under $600k in Austin"), '
                'then say "more" to see the next page of results.'
            )
        else:
            state = next_page(session_id)
            reply_text = await _handle_search(ctx, sender, session_id, state)
    elif intent == "details":
        listings = _LAST_RESULTS.get(session_id) or []
        idx = None
        if llm_result and isinstance(llm_result, dict):
            idx = llm_result.get("listing_index")
        if not listings or not idx or not (1 <= int(idx) <= len(listings)):
            reply_text = (
                "I can show more details for a specific result, e.g. "
                '"details 2" or "the second one", but I couldn\'t match that '
                "to a listing. Try again after a search."
            )
        elif stripe_payments_mod.is_configured():
            # Request a small Stripe payment to unlock full details
            description = f"Full details for listing #{idx}"
            checkout = await asyncio.to_thread(
                stripe_payments_mod.create_embedded_checkout_session,
                user_address=sender,
                chat_session_id=session_id,
                description=description,
            )
            if not checkout:
                reply_text = (
                    "Payment setup failed. Please try again or ask for details later."
                )
            else:
                sid_raw = checkout.get("checkout_session_id") or checkout.get("id")
                sid = sid_raw if isinstance(sid_raw, str) and sid_raw else None
                if not sid:
                    reply_text = "Payment setup failed. Please try again or ask for details later."
                else:
                    _PENDING_DETAILS_PAYMENTS[sid] = {
                        "sender": sender,
                        "session_id": session_id,
                        "listing_index": int(idx),
                    }
                    _PENDING_DETAILS_BY_SESSION[session_id] = {
                        "checkout_session_id": sid,
                        "listing_index": int(idx),
                    }
                    amount_str = f"{stripe_payments_mod.get_amount_cents() / 100:.2f}"
                    req = RequestPayment(
                        accepted_funds=[
                            Funds(
                                currency="USD",
                                amount=amount_str,
                                payment_method="stripe",
                            )
                        ],
                        recipient=str(ctx.agent.address),
                        deadline_seconds=300,
                        reference=session_id,
                        description=f"Pay ${amount_str} to unlock full details for listing #{idx}.",
                        metadata={"stripe": checkout, "service": "listing_details"},
                    )
                    await ctx.send(sender, req)
                    # Same as free details: remember listing for "add this to my wishlist"
                    _LAST_SELECTED_INDEX[session_id] = int(idx)
                    reply_text = (
                        f"Pay ${amount_str} to unlock full details for listing #{idx}. "
                        "Complete the checkout above, then I'll send the full listing details here."
                    )
        else:
            # No Stripe configured: show details for free
            listing = listings[int(idx) - 1]
            _LAST_SELECTED_INDEX[session_id] = int(idx)
            mls = listing.get("mls")
            raw = await asyncio.to_thread(fetch_listing_by_mls, mls) if mls else None
            if raw:
                card = format_listing_full(listing, raw, int(idx))
            else:
                card = format_listing_details(listing, int(idx))
            reply_text = f"Here are more details for listing #{idx}:\n\n{card}"
    elif intent == "refinement":
        if llm_result and isinstance(llm_result, dict):
            parsed = llm_result.get("filters") or {}
        else:
            parsed = parse_filters(user_text)
        state = merge_parsed_into_state(session_id, parsed, is_refinement=True)
        try:
            ctx.logger.info(
                "chat_refinement parsed=%s -> state=%s",
                parsed,
                {
                    k: state.get(k)
                    for k in (
                        "location",
                        "deal_type",
                        "bedrooms",
                        "max_price",
                        "property_type",
                        "page",
                    )
                },
            )
        except Exception:
            pass
        reply_text = await _handle_search(ctx, sender, session_id, state)
    else:
        if llm_result and isinstance(llm_result, dict):
            parsed = llm_result.get("filters") or {}
        else:
            parsed = parse_filters(user_text)
        state = merge_parsed_into_state(session_id, parsed, is_refinement=False)
        try:
            ctx.logger.info(
                "chat_new_search intent=%s local_intent=%s llm_intent=%s parsed=%s -> state=%s",
                intent,
                local_intent,
                (llm_result or {}).get("intent")
                if isinstance(llm_result, dict)
                else None,
                parsed,
                {
                    k: state.get(k)
                    for k in (
                        "location",
                        "deal_type",
                        "bedrooms",
                        "max_price",
                        "property_type",
                        "page",
                    )
                },
            )
        except Exception:
            pass
        if (
            not state.get("location")
            and not state.get("max_price")
            and not state.get("bedrooms")
        ):
            reply_text = (
                "I couldn't understand the search. Try something like: "
                '"Find 2 bedroom homes under $600k in Austin."'
            )
        else:
            reply_text = await _handle_search(ctx, sender, session_id, state)

    reply = ChatMessage(
        content=[TextContent(type="text", text=reply_text)],
        msg_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
    )
    await ctx.send(sender, reply)


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


async def on_payment_commit(ctx: Context, sender: str, msg: CommitPayment):
    """Verify Stripe payment and deliver full listing details."""
    if getattr(msg.funds, "payment_method", None) != "stripe" or not getattr(
        msg, "transaction_id", None
    ):
        await ctx.send(
            sender,
            RejectPayment(reason="Unsupported payment method (expected stripe)."),
        )
        return
    tid = msg.transaction_id
    checkout_id = await asyncio.to_thread(
        stripe_payments_mod.resolve_checkout_session_id, tid
    )
    paid = await asyncio.to_thread(
        stripe_payments_mod.verify_checkout_session_paid, checkout_id
    )
    if not paid:
        await ctx.send(
            sender,
            RejectPayment(
                reason="Stripe payment not completed yet. Please finish checkout."
            ),
        )
        return
    await ctx.send(sender, CompletePayment(transaction_id=tid))
    pending = _PENDING_DETAILS_PAYMENTS.pop(checkout_id, None)
    if not pending:
        await ctx.send(
            sender,
            ChatMessage(
                content=[
                    TextContent(
                        type="text",
                        text="Payment received, but this session expired. Run a search and request details again.",
                    )
                ],
                msg_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        return
    paid_session_id = pending.get("session_id")
    idx = pending.get("listing_index")
    if not isinstance(paid_session_id, str):
        await ctx.send(
            sender,
            ChatMessage(
                content=[
                    TextContent(
                        type="text",
                        text="Payment received. Your search session changed; run a search and request details again if needed.",
                    )
                ],
                msg_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        return
    listings = _LAST_RESULTS.get(paid_session_id) or []
    if not isinstance(idx, int) or not (1 <= idx <= len(listings)):
        await ctx.send(
            sender,
            ChatMessage(
                content=[
                    TextContent(
                        type="text",
                        text="Payment received. Your search session changed; run a search and request details again if needed.",
                    )
                ],
                msg_id=uuid4(),
                timestamp=datetime.now(timezone.utc),
            ),
        )
        return
    listing = listings[idx - 1]
    _LAST_SELECTED_INDEX[paid_session_id] = idx
    mls = listing.get("mls")
    raw = await asyncio.to_thread(fetch_listing_by_mls, mls) if mls else None
    if raw:
        card = format_listing_full(listing, raw, idx)
    else:
        card = format_listing_details(listing, idx)
    reply_text = f"Here are the full details for listing #{idx}:\n\n{card}"
    await ctx.send(
        sender,
        ChatMessage(
            content=[TextContent(type="text", text=reply_text)],
            msg_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        ),
    )


async def on_payment_reject(ctx: Context, sender: str, msg: RejectPayment):
    """Clear any pending payment for this sender (best-effort)."""
    to_remove = [
        tid for tid, p in _PENDING_DETAILS_PAYMENTS.items() if p.get("sender") == sender
    ]
    for tid in to_remove:
        _PENDING_DETAILS_PAYMENTS.pop(tid, None)


agent.include(chat_proto, publish_manifest=True)
agent.include(
    build_payment_proto(on_payment_commit, on_payment_reject), publish_manifest=True
)

if __name__ == "__main__":
    print("Property Finder agent address:", agent.address)
    agent.run()
