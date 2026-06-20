"""
Hackathon Discovery & Registration Agent — Agentverse deployment.

Handles chat messages via the ASI-One chat protocol:
  • Search queries  → recommend engine + event list card
  • Lookup requests → event detail card
  • Stat questions  → aggregate answer
  • Register action → answer gen + registration confirmation card
  • General Q&A     → direct ASI:One answer

Run:
    python agent.py

Deploy to Agentverse by setting AGENT_MAILBOX_KEY in .env
"""

from __future__ import annotations

import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(Path(__file__).parent / ".env")
# Also load .llm.env for API keys set during development
load_dotenv(Path(__file__).parent / ".llm.env", override=False)

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    MetadataContent,
    StartSessionContent,
    EndSessionContent,
)

from agent.qa import ask
from agent.parse import parse_question
from agent.answer_gen import generate_answers
from agent.profile import load_profile
from agent.cards import (
    welcome_card,
    event_list_card,
    event_detail_card,
    registration_confirm_card,
)
from recommend.engine import recommend
from agent.lookup import lookup_event

# ── Agent setup ──────────────────────────────────────────────────────────────

_readme_path = str(Path(__file__).parent / "agent_README.md")

agent = Agent(
    name=os.getenv("AGENT_NAME", "HackathonAgent"),
    seed=os.getenv("AGENT_SEED", "hackathon-discovery-agent-seed"),
    mailbox=True,
    port=int(os.getenv("AGENT_PORT", "8008")),
    publish_agent_details=True,
    readme_path=_readme_path if Path(_readme_path).exists() else None,
)

chat_proto = Protocol(spec=chat_protocol_spec)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _msg_id():
    return uuid4()


def text_msg(text: str, end: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=_now(), msg_id=_msg_id(), content=content)


def card_msg(card: dict, text: str = "") -> ChatMessage:
    """Send a card UI alongside optional text."""
    content = []
    if text:
        content.append(TextContent(type="text", text=text))
    content.append(MetadataContent(
        type="metadata",
        metadata={"card": json.dumps(card)},
    ))
    return ChatMessage(timestamp=_now(), msg_id=_msg_id(), content=content)


def ack(msg_id) -> ChatAcknowledgement:
    return ChatAcknowledgement(timestamp=_now(), acknowledged_msg_id=msg_id)


# ── Session state (per-sender) ────────────────────────────────────────────────

_sessions: dict[str, dict] = {}

def _session(sender: str) -> dict:
    if sender not in _sessions:
        _sessions[sender] = {"last_results": [], "last_event": None}
    return _sessions[sender]


# ── Chat handler ──────────────────────────────────────────────────────────────

@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ack(msg.msg_id))
    sess = _session(sender)

    for item in msg.content:

        # ── Session start ─────────────────────────────────────────────────
        if isinstance(item, StartSessionContent):
            await ctx.send(sender, ChatMessage(
                timestamp=_now(), msg_id=_msg_id(),
                content=[MetadataContent(type="metadata", metadata={"attachments": "false"})],
            ))
            await ctx.send(sender, card_msg(
                welcome_card(),
                "👋 Welcome! I can find hackathons, give you event details, and help you register. What are you looking for?",
            ))
            return

        # ── Text / action message ─────────────────────────────────────────
        if isinstance(item, TextContent):
            user_text = item.text.strip()
            if not user_text:
                continue

            ctx.logger.info(f"Message from {sender[:12]}: {user_text[:80]}")
            await _handle_text(ctx, sender, sess, user_text)
            return

        # ── Metadata (button actions) ─────────────────────────────────────
        if isinstance(item, MetadataContent):
            meta = item.metadata or {}
            selection = meta.get("selection") or {}
            if selection:
                await _handle_action(ctx, sender, sess, selection)
            return


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ACK from {sender[:12]}")


# ── Intent handlers ───────────────────────────────────────────────────────────

async def _handle_text(ctx: Context, sender: str, sess: dict, text: str):
    parsed = parse_question(text)
    intent = parsed.get("intent", "search")

    # Quick queries from welcome card buttons
    if "quick_query" in text:
        intent = "search"

    if intent == "general":
        answer = parsed.get("answer", "")
        await ctx.send(sender, text_msg(answer or await _llm_answer(text)))

    elif intent == "lookup":
        event_name = parsed.get("event_name", text)
        ev = lookup_event(event_name)
        if ev:
            sess["last_event"] = ev
            await ctx.send(sender, card_msg(
                event_detail_card(ev),
                f"Here are the details for **{ev.get('title','')}**:",
            ))
        else:
            await ctx.send(sender, text_msg(
                f"I couldn't find an event matching '{event_name}'. "
                "Try a more specific name or ask me to search for it."
            ))

    elif intent == "stat":
        from agent.stats import answer_stat
        answer = answer_stat(parsed.get("stat_query", text))
        await ctx.send(sender, text_msg(answer))

    else:  # search
        prefs = parsed.get("prefs") or {"keywords": text}
        await ctx.send(sender, text_msg("🔍 Searching 16,700+ events..."))

        results = recommend(prefs)
        sess["last_results"] = results

        if not results:
            await ctx.send(sender, text_msg(
                "No events found for those criteria. Try broadening the date range, "
                "removing the location filter, or using different keywords."
            ))
            return

        # Build text summary + card UI
        top = results[:5]
        summary = _build_summary(top, prefs)
        await ctx.send(sender, card_msg(
            event_list_card(results, subtitle=_search_subtitle(prefs, len(results))),
            summary,
        ))


async def _handle_action(ctx: Context, sender: str, sess: dict, selection: dict):
    action = selection.get("action", "")
    slug   = selection.get("event_slug", "")
    url    = selection.get("event_url", "")

    if action == "view_details":
        ev = _find_event(sess, slug) or lookup_event(slug)
        if ev:
            sess["last_event"] = ev
            await ctx.send(sender, card_msg(
                event_detail_card(ev),
                f"**{ev.get('title','')}**",
            ))
        else:
            await ctx.send(sender, text_msg("Event not found. Try searching again."))

    elif action == "register":
        ev = _find_event(sess, slug) or lookup_event(slug)
        if not ev:
            await ctx.send(sender, text_msg("Event not found. Can't start registration."))
            return

        sess["last_event"] = ev
        profile = load_profile()
        questions = _parse_qs(ev.get("questions"))
        answers = generate_answers(
            questions, profile,
            ev.get("title", ""),
            ev.get("description_summary", ""),
        )

        await ctx.send(sender, card_msg(
            registration_confirm_card(ev, answers),
            f"Ready to register for **{ev.get('title','')}**. Here's what I'll fill in:",
        ))

    elif action == "confirm_register":
        ev = sess.get("last_event")
        if not ev:
            await ctx.send(sender, text_msg("Session expired. Please search for the event again."))
            return

        await ctx.send(sender, text_msg("🚀 Opening browser to complete registration..."))

        try:
            from agent.register import register_for_event
            profile = load_profile()
            result = await register_for_event(
                slug=ev.get("slug"),
                profile=profile,
                headless=False,
            )
            if result.get("success"):
                await ctx.send(sender, text_msg(
                    f"✅ **Registration submitted!**\n\n"
                    f"Event: {ev.get('title','')}\n"
                    f"{result.get('message','')}\n\n"
                    f"Check your email for confirmation.",
                    end=True,
                ))
            else:
                await ctx.send(sender, text_msg(
                    f"⚠️ Registration may need manual completion.\n\n"
                    f"{result.get('message','')}\n\n"
                    f"Visit: {ev.get('external_url','')}"
                ))
        except Exception as e:
            await ctx.send(sender, text_msg(f"❌ Registration failed: {e}"))

    elif action == "refine":
        await ctx.send(sender, text_msg(
            "Tell me more about what you're looking for:\n"
            "• Location (e.g. 'in London' or 'online only')\n"
            "• Tech stack (e.g. 'AI', 'Web3', 'mobile')\n"
            "• Prize minimum (e.g. 'prizes over $10k')\n"
            "• Date range (e.g. 'in August')"
        ))

    elif action == "view_all":
        results = sess.get("last_results", [])
        if len(results) > 5:
            lines = [f"{i+1}. {ev.get('title','')} — {(ev.get('city') or '?')[:25]}"
                     for i, ev in enumerate(results[5:15])]
            await ctx.send(sender, text_msg(
                f"**More results ({len(results)} total):**\n\n" + "\n".join(lines) +
                "\n\nAsk me about any of these by name for full details."
            ))
        else:
            await ctx.send(sender, text_msg("No more results. Try a different search."))

    elif action == "back":
        results = sess.get("last_results", [])
        if results:
            await ctx.send(sender, card_msg(
                event_list_card(results),
                "Back to results:",
            ))

    elif selection.get("quick_query"):
        await _handle_text(ctx, sender, sess, selection["quick_query"])


# ── Formatting helpers ────────────────────────────────────────────────────────

def _build_summary(events: list[dict], prefs: dict) -> str:
    if not events:
        return "No events found."
    lines = [f"Found **{len(events)}** events. Top picks:\n"]
    for i, ev in enumerate(events[:3], 1):
        title = ev.get("title", "Untitled")
        city  = ev.get("city") or "?"
        start = ev.get("start_datetime", "")[:10]
        reason = ev.get("reason", "")
        lines.append(f"**{i}. {title}** — {city}, {start}")
        if reason:
            lines.append(f"   _{reason[:80]}_")
    return "\n".join(lines)


def _search_subtitle(prefs: dict, count: int) -> str:
    parts = []
    if prefs.get("keywords"):
        parts.append(prefs["keywords"])
    if prefs.get("location"):
        parts.append(f"in {prefs['location']}")
    if prefs.get("online"):
        parts.append("online")
    if prefs.get("hackathon_only"):
        parts.append("hackathons only")
    base = " · ".join(parts) if parts else "your search"
    return f"{count} results for {base}"


def _find_event(sess: dict, slug: str) -> dict | None:
    """Find event in session results by slug."""
    for ev in sess.get("last_results", []):
        if ev.get("slug") == slug:
            return ev
    if sess.get("last_event", {}).get("slug") == slug:
        return sess["last_event"]
    return None


def _parse_qs(raw) -> list[dict]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


async def _llm_answer(text: str) -> str:
    """Fallback: route to Q&A agent."""
    return ask(text)


# ── Run ───────────────────────────────────────────────────────────────────────

agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"\n🏆 Hackathon Discovery Agent")
    print(f"   Address: {agent.address}")
    print(f"   Mailbox: {'configured' if os.getenv('AGENT_MAILBOX_KEY') else 'NOT SET — add AGENT_MAILBOX_KEY to .env'}")
    print(f"   Port:    {os.getenv('AGENT_PORT', '8008')}")
    print(f"\n   Ready. Press Ctrl+C to stop.\n")
    agent.run()
