"""
Host B – The Expert  (Post-Show Q&A Agent)
==========================================
Run in its own terminal BEFORE the Orchestrator starts:

    python host_b_agent.py

This agent does two things:
  1. Receives a ContextInjection from the Orchestrator after each podcast is
     generated and stores the paper context in persistent local storage.
  2. Responds to ChatMessages from users in ASI:One, answering in-character as
     "The Expert" — the host who defends findings with exact numbers.

Users interact by tagging @pdf_podcast_host_b in ASI:One chat:
    "@pdf_podcast_host_b  Can you explain the union-based execution result?"
"""

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from openai import AsyncOpenAI
from uagents import Agent, Context, Protocol

from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from schemas import ContextInjection, DebateTurn, DebateResponse

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────

_MODEL = os.getenv("ASI1_MODEL", "asi1-mini")
_client = AsyncOpenAI(
    api_key=os.getenv("ASI1_API_KEY", ""),
    base_url="https://api.asi1.ai/v1",
)

_DEFAULT_PERSONALITY = (
    "You cite exact data points from the study. You defend findings with measured "
    "confidence, acknowledge limitations honestly, and never over-claim. You often "
    "say 'the data shows' and back it up with a specific number."
)

_LATEST_SESSION_KEY = "__latest_session__"
_PERSONALITY_KEY = "__personality__"

# ── Agent ──────────────────────────────────────────────────────────────────────

_agentverse_key = os.getenv("AGENTVERSE_API_KEY", "")

if _agentverse_key:
    host_b = Agent(
        name="pdf_podcast_host_b",
        seed=os.getenv("HOST_B_SEED", "pdf_podcast_host_b_seed_v1"),
        port=8005,
        mailbox=True,
        agentverse="https://agentverse.ai",
        handle_messages_concurrently=True,
        network="testnet",
    )
else:
    host_b = Agent(
        name="pdf_podcast_host_b",
        seed=os.getenv("HOST_B_SEED", "pdf_podcast_host_b_seed_v1"),
        port=8005,
        endpoint=["http://localhost:8005/submit"],
        handle_messages_concurrently=True,
        network="testnet",
    )

chat_proto = Protocol(spec=chat_protocol_spec)

# ── Context injection (from Orchestrator) ──────────────────────────────────────


@host_b.on_message(ContextInjection)
async def receive_context(ctx: Context, sender: str, msg: ContextInjection) -> None:
    """Store paper context keyed by session_id and track the latest session."""
    payload = {
        "topic_title": msg.topic_title,
        "core_thesis": msg.core_thesis,
        "key_metrics": msg.key_metrics,
        "controversial_point": msg.controversial_point,
        "document_snippet": msg.document_snippet,
    }
    ctx.storage.set(msg.session_id, json.dumps(payload))
    ctx.storage.set(_LATEST_SESSION_KEY, msg.session_id)
    if msg.host_b_personality:
        ctx.storage.set(_PERSONALITY_KEY, msg.host_b_personality)
    ctx.logger.info(
        f"[HostB] Context stored for session {msg.session_id[:8]} — '{msg.topic_title}'"
    )


# ── Debate turn (Orchestrator → HostB → Orchestrator) ────────────────────────


@host_b.on_message(DebateTurn)
async def handle_debate_turn(ctx: Context, sender: str, msg: DebateTurn) -> None:
    ctx.logger.info(
        f"[HostB] Debate turn {msg.turn}/{msg.max_turns} — session {msg.session_id[:8]}"
    )

    history_block = ""
    if msg.debate_history:
        history_block = f"--- DEBATE SO FAR ---\n{msg.debate_history}\n--- END OF DEBATE HISTORY ---\n\n"

    user_content = (
        f"Topic: {msg.topic_title}\n"
        f"Core thesis: {msg.core_thesis}\n"
        f"Key metrics: {', '.join(msg.key_metrics)}\n"
        f"Controversy: {msg.controversial_point}\n"
        f"Paper excerpt: {msg.document_snippet[:1500]}\n\n"
        f"{history_block}"
        f'The Skeptic just said:\n"{msg.previous_statement}"\n\n'
        f"This is turn {msg.turn + 1} of {msg.max_turns}.\n"
        "IMPORTANT: Do NOT repeat any argument already made in the debate history above. "
        "Respond to the Skeptic's NEW point directly. Introduce fresh evidence, a different "
        "data point from the paper, or a new implication. Acknowledge a limitation honestly. "
        "2-3 confident sentences."
    )

    personality = (
        msg.speaker_personality
        or ctx.storage.get(_PERSONALITY_KEY)
        or _DEFAULT_PERSONALITY
    )
    system_prompt = (
        f"You are Host B — 'The Expert' — in a LIVE podcast debate.\n"
        f"Personality: {personality}\n"
        "Rules:\n"
        "- Respond ONLY with your spoken line. No labels, no stage directions.\n"
        "- NEVER repeat an argument you or the Skeptic already made.\n"
        "- Each turn MUST raise a genuinely new point, angle, or data from the paper.\n"
        "- Build on what was said, don't circle back."
    )

    try:
        resp = await _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.82,
            max_tokens=200,
        )
        reply_text = resp.choices[0].message.content.strip() or "…"
    except Exception as e:
        ctx.logger.error(f"[HostB] Debate LLM error: {e}")
        reply_text = "*(The Expert is consulting the data…)*"

    try:
        await ctx.send(
            sender,
            DebateResponse(
                session_id=msg.session_id,
                speaker="expert",
                reply_text=reply_text,
                turn=msg.turn,
                max_turns=msg.max_turns,
                user_address=msg.user_address,
                topic_title=msg.topic_title,
                core_thesis=msg.core_thesis,
                key_metrics=msg.key_metrics,
                controversial_point=msg.controversial_point,
                document_snippet=msg.document_snippet,
            ),
        )
        ctx.logger.info(f"[HostB] DebateResponse sent for turn {msg.turn}.")
    except Exception as e:
        ctx.logger.error(f"[HostB] Failed to send DebateResponse: {e}")


# ── User Q&A (from ASI:One chat) ──────────────────────────────────────────────


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    ctx.logger.info(
        f"[HostB] ChatMessage from {sender[:20]}… content types: {[type(c).__name__ for c in msg.content]}"
    )
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    user_text = " ".join(
        item.text.strip()
        for item in msg.content
        if isinstance(item, TextContent) and item.text.strip()
    )
    if not user_text:
        ctx.logger.warning("[HostB] No TextContent found in message — skipping.")
        return

    # Load latest session context
    session_id = ctx.storage.get(_LATEST_SESSION_KEY)
    context_str = ""
    if session_id:
        raw = ctx.storage.get(session_id)
        if raw:
            try:
                data = json.loads(raw)
                context_str = (
                    f"Episode topic: {data['topic_title']}\n"
                    f"Core thesis: {data['core_thesis']}\n"
                    f"Key metrics: {', '.join(data['key_metrics'])}\n"
                    f"Controversy: {data['controversial_point']}\n\n"
                    f"Paper excerpt:\n{data['document_snippet'][:2000]}"
                )
            except Exception:
                pass

    personality = ctx.storage.get(_PERSONALITY_KEY) or _DEFAULT_PERSONALITY
    qa_system = (
        "You are Host B from a research podcast debate — 'The Expert'.\n"
        f"Personality: {personality}\n\n"
        "The user is asking a follow-up question about a paper you just debated. "
        "Answer in character. Be concise (2–4 sentences max). Always cite at least "
        "one specific metric or finding from the context in your answer."
    )

    user_msg = {"role": "user", "content": user_text}
    if context_str:
        user_msg["content"] = (
            f"[Paper context]\n{context_str}\n\n[User question]\n{user_text}"
        )

    try:
        resp = await _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": qa_system},
                user_msg,
            ],
            temperature=0.7,
            max_tokens=300,
        )
        reply_text = resp.choices[0].message.content or "…"
    except Exception as e:
        ctx.logger.error(f"[HostB] LLM error: {e}")
        reply_text = "*(Host B is looking up the data…  try again in a moment)*"

    ctx.logger.info(f"[HostB] Sending reply to {sender[:16]}…")
    try:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(
                        type="text", text=f"**[Host B — The Expert]**\n\n{reply_text}"
                    ),
                    EndSessionContent(type="end-session"),
                ],
            ),
        )
        ctx.logger.info("[HostB] Reply sent successfully.")
    except Exception as e:
        ctx.logger.error(f"[HostB] Failed to send reply: {e}")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    pass


host_b.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    host_b.run()
