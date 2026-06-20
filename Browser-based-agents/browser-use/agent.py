"""
Hackrawl — Hackathon Discovery & Registration Agent
Deployed on Agentverse via mailbox + chat protocol.

Run:
    python agent.py
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

# Load .env then .llm.env (non-override so .env wins)
_root = Path(__file__).parent
load_dotenv(_root / ".env")
load_dotenv(_root / ".llm.env", override=False)

sys.path.insert(0, str(_root / "scripts"))

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
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
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

# ── Config ────────────────────────────────────────────────────────────────────

AGENT_NAME      = os.getenv("AGENT_NAME", "Hackrawl")
AGENT_SEED      = os.getenv("AGENT_SEED", "hackrawl-agent-seed-phrase-change-me")
AGENT_PORT      = int(os.getenv("AGENT_PORT", "8008"))
AGENTVERSE_KEY  = os.getenv("AGENT_MAILBOX_KEY", "")
_readme_path    = str(_root / "agent_README.md")

SHORT_DESCRIPTION = (
    "Find, explore, and register for hackathons across 16,700+ events "
    "from Devpost, MLH, Cerebral Valley, ETHGlobal and more. "
    "Powered by ASI:One."
)

# ── Agent ─────────────────────────────────────────────────────────────────────

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    publish_agent_details=True,
    readme_path=_readme_path if Path(_readme_path).exists() else None,
)

chat_proto = Protocol(spec=chat_protocol_spec)

# ── Startup: register with Agentverse ─────────────────────────────────────────

@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"🚀 {AGENT_NAME} starting — address: {ctx.agent.address}")

    if AGENTVERSE_KEY and AGENT_SEED:
        try:
            readme = Path(_readme_path).read_text() if Path(_readme_path).exists() else SHORT_DESCRIPTION
            register_chat_agent(
                AGENT_NAME,
                agent._endpoints[0].url if agent._endpoints else "",
                active=True,
                credentials=RegistrationRequestCredentials(
                    agentverse_api_key=AGENTVERSE_KEY,
                    agent_seed_phrase=AGENT_SEED,
                ),
                readme=readme,
                description=SHORT_DESCRIPTION,
            )
            ctx.logger.info("✅ Registered with Agentverse")
        except Exception as e:
            ctx.logger.error(f"Agentverse registration failed: {e}")
    else:
        ctx.logger.warning("⚠️  AGENT_MAILBOX_KEY not set — skipping Agentverse registration")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _mid():
    return uuid4()

def text_msg(text: str, end: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=_now(), msg_id=_mid(), content=content)

def card_msg(card: dict, text: str = "") -> ChatMessage:
    content = []
    if text:
        content.append(TextContent(type="text", text=text))
    content.append(MetadataContent(
        type="metadata",
        metadata={"card": json.dumps(card)},
    ))
    return ChatMessage(timestamp=_now(), msg_id=_mid(), content=content)

def ack(msg_id) -> ChatAcknowledgement:
    return ChatAcknowledgement(timestamp=_now(), acknowledged_msg_id=msg_id)

# ── Session state (per sender) ────────────────────────────────────────────────

_sessions: dict[str, dict] = {}

def _sess(sender: str) -> dict:
    if sender not in _sessions:
        _sessions[sender] = {"last_results": [], "last_event": None}
    return _sessions[sender]

# ── Chat protocol ─────────────────────────────────────────────────────────────

@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ack(msg.msg_id))
    sess = _sess(sender)

    for item in msg.content:

        if isinstance(item, StartSessionContent):
            await ctx.send(sender, ChatMessage(
                timestamp=_now(), msg_id=_mid(),
                content=[MetadataContent(type="metadata", metadata={"attachments": "false"})],
            ))
            await ctx.send(sender, card_msg(
                welcome_card(),
                "👋 Hi! I'm **Hackrawl** — I search 16,700+ hackathons and help you register. What are you looking for?",
            ))
            return

        if isinstance(item, TextContent):
            text = item.text.strip()
            if not text:
                continue
            ctx.logger.info(f"[{sender[:10]}] {text[:80]}")
            await _handle_text(ctx, sender, sess, text)
            return

        if isinstance(item, MetadataContent):
            selection = (item.metadata or {}).get("selection") or {}
            if selection:
                await _handle_action(ctx, sender, sess, selection)
            return

@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

# ── Intent handlers ───────────────────────────────────────────────────────────

async def _handle_text(ctx: Context, sender: str, sess: dict, text: str):
    parsed = parse_question(text)
    intent = parsed.get("intent", "search")

    if intent == "general":
        await ctx.send(sender, text_msg(parsed.get("answer") or ask(text)))

    elif intent == "lookup":
        ev = lookup_event(parsed.get("event_name", text))
        if ev:
            sess["last_event"] = ev
            await ctx.send(sender, card_msg(
                event_detail_card(ev),
                f"Here are the details for **{ev.get('title','')}**:",
            ))
        else:
            await ctx.send(sender, text_msg(
                f"Couldn't find an event matching that name. Try a more specific name or ask me to search."
            ))

    elif intent == "stat":
        from agent.stats import answer_stat
        await ctx.send(sender, text_msg(answer_stat(parsed.get("stat_query", text))))

    else:  # search
        prefs = parsed.get("prefs") or {"keywords": text}
        await ctx.send(sender, text_msg("🔍 Searching 16,700+ events..."))
        results = recommend(prefs)
        sess["last_results"] = results

        if not results:
            await ctx.send(sender, text_msg(
                "No events found for those criteria. Try broadening the date range, "
                "removing location filters, or using different keywords."
            ))
            return

        subtitle = _subtitle(prefs, len(results))
        summary  = _summary(results[:3])
        await ctx.send(sender, card_msg(event_list_card(results, subtitle), summary))


async def _handle_action(ctx: Context, sender: str, sess: dict, sel: dict):
    action = sel.get("action", "")
    slug   = sel.get("event_slug", "")

    if sel.get("quick_query"):
        await _handle_text(ctx, sender, sess, sel["quick_query"])
        return

    if action == "view_details":
        ev = _find(sess, slug) or lookup_event(slug)
        if ev:
            sess["last_event"] = ev
            await ctx.send(sender, card_msg(event_detail_card(ev), f"**{ev.get('title','')}**"))
        else:
            await ctx.send(sender, text_msg("Event not found. Try searching again."))

    elif action == "register":
        ev = _find(sess, slug) or lookup_event(slug)
        if not ev:
            await ctx.send(sender, text_msg("Event not found. Can't start registration."))
            return
        sess["last_event"] = ev
        profile   = load_profile()
        questions = _parse_qs(ev.get("questions"))
        answers   = generate_answers(questions, profile, ev.get("title",""), ev.get("description_summary",""))
        await ctx.send(sender, card_msg(
            registration_confirm_card(ev, answers),
            f"Ready to register for **{ev.get('title','')}**. Here's what I'll fill in:",
        ))

    elif action == "confirm_register":
        ev = sess.get("last_event")
        if not ev:
            await ctx.send(sender, text_msg("Session expired. Search for the event again."))
            return
        await ctx.send(sender, text_msg("🚀 Opening browser to complete registration..."))
        try:
            from agent.register import register_for_event
            result = await register_for_event(slug=ev.get("slug"), profile=load_profile(), headless=False)
            if result.get("success"):
                await ctx.send(sender, text_msg(
                    f"✅ **Registration submitted!**\n\n"
                    f"Event: {ev.get('title','')}\n"
                    f"{result.get('message','')}\n\nCheck your email for confirmation.", end=True,
                ))
            else:
                await ctx.send(sender, text_msg(
                    f"⚠️ Registration may need manual completion.\n\n"
                    f"{result.get('message','')}\n\nVisit: {ev.get('external_url','')}"
                ))
        except Exception as e:
            await ctx.send(sender, text_msg(f"❌ Registration failed: {e}"))

    elif action == "refine":
        await ctx.send(sender, text_msg(
            "Tell me more:\n"
            "• Location (e.g. 'in London' or 'online only')\n"
            "• Tech stack (e.g. 'AI', 'Web3', 'mobile')\n"
            "• Prize minimum (e.g. 'prizes over $10k')\n"
            "• Date range (e.g. 'in August')"
        ))

    elif action == "view_all":
        results = sess.get("last_results", [])
        extra = results[5:15]
        if extra:
            lines = [f"{i+6}. {ev.get('title',''):50s}  {(ev.get('city') or '?')[:25]}"
                     for i, ev in enumerate(extra)]
            await ctx.send(sender, text_msg(
                f"**More results ({len(results)} total):**\n\n" + "\n".join(lines) +
                "\n\nAsk me about any of these by name for full details."
            ))
        else:
            await ctx.send(sender, text_msg("No more results. Try a different search."))

    elif action == "back":
        results = sess.get("last_results", [])
        if results:
            await ctx.send(sender, card_msg(event_list_card(results), "Back to results:"))

    elif action == "open_url":
        url = sel.get("url", "")
        await ctx.send(sender, text_msg(f"🔗 {url}"))

# ── Formatting ────────────────────────────────────────────────────────────────

def _summary(events: list[dict]) -> str:
    lines = []
    for i, ev in enumerate(events, 1):
        title  = ev.get("title", "Untitled")
        city   = ev.get("city") or "?"
        start  = (ev.get("start_datetime") or "")[:10]
        reason = ev.get("reason", "")
        lines.append(f"**{i}. {title}** — {city}, {start}")
        if reason:
            lines.append(f"   _{reason[:90]}_")
    return "\n".join(lines)

def _subtitle(prefs: dict, count: int) -> str:
    parts = [p for p in [
        prefs.get("keywords"),
        f"in {prefs['location']}" if prefs.get("location") else None,
        "online" if prefs.get("online") else None,
        "hackathons only" if prefs.get("hackathon_only") else None,
    ] if p]
    base = " · ".join(parts) if parts else "your search"
    return f"{count} results for {base}"

def _find(sess: dict, slug: str) -> dict | None:
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
    try:
        return json.loads(raw)
    except Exception:
        return []

# ── Run ───────────────────────────────────────────────────────────────────────

agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"\n🔍 Hackrawl — Hackathon Discovery & Registration Agent")
    print(f"   Address : {agent.address}")
    print(f"   Port    : {AGENT_PORT}")
    print(f"   Mailbox : {'✅ configured' if AGENTVERSE_KEY else '⚠️  set AGENT_MAILBOX_KEY in .env'}")
    print(f"\n   Press Ctrl+C to stop.\n")
    agent.run()
