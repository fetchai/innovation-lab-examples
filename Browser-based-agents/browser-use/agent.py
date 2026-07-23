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

_root = Path(__file__).parent
load_dotenv(_root / ".env")

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
from uagents_core.contrib.protocols.chat.cards import (
    create_card_content,
    FormCardPayload,
    FormField,
    FormFieldOption,
    CtaAction,
)

from agent.qa import ask
from agent.parse import parse_question
from agent.answer_gen import generate_answers
from agent.profile import load_profile, save_profile
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

def card_msg(card: dict, label: str = "") -> ChatMessage:
    return ChatMessage(timestamp=_now(), msg_id=_mid(), content=[
        TextContent(type="text", text=label),
        MetadataContent(
            type="metadata",
            metadata={
                "card_protocol_version": "1",
                "requires_card_interaction": "true",
                "card_kind": "custom",
                "card_payload": json.dumps(card),
            },
        ),
    ])

def form_card_msg(payload: FormCardPayload, label: str = "") -> ChatMessage:
    """Official uagents_core FormCardPayload — a real multi-field form with a submit action."""
    return ChatMessage(timestamp=_now(), msg_id=_mid(), content=[
        TextContent(type="text", text=label),
        create_card_content(payload, card_id=uuid4()),
    ])

def missing_fields_form(missing_fields: list[dict], ev: dict) -> FormCardPayload:
    """
    Build a single form asking for every field the registration form needs
    that the profile doesn't cover (e.g. T-shirt size, dietary restrictions),
    so the human answers all of them in one submission instead of one at a
    time. Field values come back keyed by `field_name` merged into the submit
    button's `selection` dict — see _handle_action's "submit_missing_fields".
    """
    fields = []
    for f in missing_fields:
        name = f.get("field_name") or "field"
        options = f.get("options") or []
        note = f.get("note") or ""
        fields.append(FormField(
            name=name,
            kind="select" if options else "text",
            label=name.replace("_", " ").title(),
            required=True,
            options=[FormFieldOption(value=o, label=o) for o in options] if options else None,
            placeholder=(note[:80] or None) if not options else None,
        ))
    return FormCardPayload(
        title=f"A few details for {ev.get('title', 'this event')}",
        fields=fields,
        submit_cta=CtaAction(
            label="Submit and continue registration",
            selection={"action": "submit_missing_fields", "event_slug": ev.get("slug", "")},
            primary=True,
        ),
    )

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
            await ctx.send(sender, card_msg(welcome_card(), "👋 Hi! I'm Hackrawl — your hackathon search assistant."))
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

def _parse_selection(text: str) -> dict | None:
    """Try to extract a card selection from text sent by ASI:One on button click."""
    stripped = text.strip()
    # Strip leading @agent_address prefix (ASI:One prepends it on button clicks)
    if stripped.startswith("@"):
        parts = stripped.split(None, 1)
        stripped = parts[1].strip() if len(parts) > 1 else stripped
    # Direct JSON object
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "action" in data:
                return data
            # Wrapped: {"selection": {...}}
            if isinstance(data, dict) and isinstance(data.get("selection"), dict):
                return data["selection"]
        except json.JSONDecodeError:
            pass
    return None


async def _handle_text(ctx: Context, sender: str, sess: dict, text: str):
    # Card button clicks arrive as TextContent containing the selection JSON
    selection = _parse_selection(text)
    if selection:
        await _handle_action(ctx, sender, sess, selection)
        return

    if text.lower().strip() in {"hi", "hello", "hey", "start", "help"}:
        await ctx.send(sender, card_msg(welcome_card(), "Hi! I'm Hackrawl — your hackathon search assistant."))
        return

    parsed = parse_question(text)
    intent = parsed.get("intent", "search")

    if intent == "general":
        await ctx.send(sender, text_msg(parsed.get("answer") or ask(text)))

    elif intent == "lookup":
        ev = lookup_event(parsed.get("event_name", text))
        if ev:
            sess["last_event"] = ev
            await ctx.send(sender, card_msg(event_detail_card(ev), ev.get("title", "Event details")))
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
        sess["results_shown"] = 10
        await ctx.send(sender, card_msg(event_list_card(results, subtitle, limit=10), "Here are your top matches:"))


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
            await ctx.send(sender, card_msg(event_detail_card(ev), ev.get("title", "Event details")))
        else:
            await ctx.send(sender, text_msg("Event not found. Try searching again."))

    elif action == "register":
        ev = _find(sess, slug) or lookup_event(slug)
        if not ev:
            await ctx.send(sender, text_msg("Event not found. Can't start registration."))
            return
        sess["last_event"] = ev
        profile   = load_profile(agent_address=sender)
        questions = _parse_qs(ev.get("questions"))
        answers   = generate_answers(questions, profile, ev.get("title",""), ev.get("description_summary",""))
        await ctx.send(sender, card_msg(registration_confirm_card(ev, answers), "Ready to register:"))

    elif action == "confirm_register":
        ev = sess.get("last_event")
        if not ev:
            await ctx.send(sender, text_msg("Session expired. Search for the event again."))
            return
        profile = load_profile(agent_address=sender)
        await ctx.send(sender, text_msg("🚀 Opening browser to complete registration..."))
        try:
            from agent.register import register_for_event
            result = await register_for_event(slug=ev.get("slug"), profile=profile, agent_address=sender, headless=False, interactive=False)
        except Exception as e:
            result = {"success": False, "message": str(e)}
        await _handle_registration_result(ctx, sender, sess, ev, profile, result)

    elif action == "submit_missing_fields":
        pending = sess.get("pending_field_request")
        if not pending:
            await ctx.send(sender, text_msg("Nothing pending to submit — try registering again."))
            return
        answers = {
            k: (v if isinstance(v, str) else str(v))
            for k, v in sel.items()
            if k not in ("action", "event_slug") and v not in (None, "")
        }
        ev, profile = pending["event"], pending["profile"]
        await ctx.send(sender, text_msg("Got it — thanks! 🚀 Continuing registration..."))
        try:
            from agent.register import resume_registration
            result = await resume_registration(pending["resume_state"], answers, profile, agent_address=sender)
        except Exception as e:
            result = {"success": False, "message": str(e)}
        sess.pop("pending_field_request", None)
        await _handle_registration_result(ctx, sender, sess, ev, profile, result)

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
        offset = sess.get("results_shown", 10)
        page = results[offset:offset + 10]
        if page:
            sess["results_shown"] = offset + 10
            subtitle = f"Showing {offset + 1}-{min(offset + len(page), len(results))} of {len(results)} events"
            await ctx.send(sender, card_msg(
                event_list_card(results, subtitle, offset=offset, limit=10),
                "More matches:",
            ))
        else:
            await ctx.send(sender, text_msg("No more results. Try a different search."))


async def _handle_registration_result(ctx: Context, sender: str, sess: dict, ev: dict, profile, result: dict) -> None:
    """
    Report a register_for_event()/resume_registration() outcome, or — if the
    form needs info the profile doesn't have — send a form asking for all of
    it at once and stash the live browser session (kept alive by
    interactive=False) so submit_missing_fields can resume it later. The
    browser only ever gets this far without submitting anything (see
    platforms/generic.py's FIELD_INPUT_REQUIRED protocol), so no partial/
    guessed registration is at risk of going through in the meantime.
    """
    if result.get("needs_field_input"):
        missing = result.get("missing_fields") or []
        sess["pending_field_request"] = {
            "resume_state": result["_resume_state"],
            "event": ev,
            "profile": profile,
        }
        await ctx.send(sender, form_card_msg(
            missing_fields_form(missing, ev),
            f"Just need a few things {ev.get('title', 'this event')} asks for that aren't in your profile yet:",
        ))
        return

    title = ev.get("title") or "this event"

    if result.get("success") and result.get("already_registered"):
        await ctx.send(sender, text_msg(
            f"ℹ️ Looks like you're already registered for **{title}** — no action needed!",
            end=True,
        ))
    elif result.get("success"):
        await ctx.send(sender, text_msg(
            f"✅ You're all set — registration for **{title}** went through. "
            f"Keep an eye on your inbox for a confirmation email.",
            end=True,
        ))
    else:
        await ctx.send(sender, text_msg(
            f"⚠️ I wasn't able to finish registering you for **{title}** automatically.\n\n"
            f"{result.get('message','')}\n\n"
            f"You can finish it yourself here: {ev.get('external_url','')}"
        ))


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
