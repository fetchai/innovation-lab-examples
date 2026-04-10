"""
Host A – The Skeptic  (Post-Show Q&A Agent)
============================================
Run in its own terminal AFTER the Orchestrator has started:

    python host_a_agent.py

This agent does two things:
  1. Receives a ContextInjection from the Orchestrator after each podcast is
     generated and stores the paper context in persistent local storage.
  2. Responds to ChatMessages from users in ASI:One, answering in-character as
     "The Skeptic" — the host who pushes back and demands hard evidence.

Users interact by tagging @pdf_podcast_host_a in ASI:One chat:
    "@pdf_podcast_host_a  At 01:12 you said the baseline was crushed.
     What was the actual sample size?"
"""

import os
import json
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from uagents import Agent, Context

from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents import Protocol

from schemas import ContextInjection, DebateTurn, DebateResponse

# ── Config ─────────────────────────────────────────────────────────────────────

_MODEL  = os.getenv("ASI1_MODEL", "asi1-mini")
_client = AsyncOpenAI(
    api_key=os.getenv("ASI1_API_KEY", ""),
    base_url="https://api.asi1.ai/v1",
)

_DEFAULT_PERSONALITY = (
    "You demand hard empirical evidence. You always ask 'what's the sample size?' "
    "and 'was this peer-reviewed?'. You challenge methodology relentlessly but fairly. "
    "You are NOT dismissive — you are intellectually rigorous."
)

_LATEST_SESSION_KEY  = "__latest_session__"
_PERSONALITY_KEY     = "__personality__"

# ── Agent ──────────────────────────────────────────────────────────────────────

_agentverse_key = os.getenv("AGENTVERSE_API_KEY", "")

host_a = Agent(
    name="pdf_podcast_host_a",
    seed=os.getenv("HOST_A_SEED", "pdf_podcast_host_a_seed_v1"),
    port=8004,
    **({
        "mailbox": _agentverse_key,
    } if _agentverse_key else {
        "endpoint": ["http://localhost:8004/submit"],
    }),
    network="testnet",
)

chat_proto = Protocol(spec=chat_protocol_spec)

# ── Context injection (from Orchestrator) ──────────────────────────────────────

@host_a.on_message(ContextInjection)
async def receive_context(ctx: Context, sender: str, msg: ContextInjection) -> None:
    """Store paper context keyed by session_id and track the latest session."""
    payload = {
        "topic_title":         msg.topic_title,
        "core_thesis":         msg.core_thesis,
        "key_metrics":         msg.key_metrics,
        "controversial_point": msg.controversial_point,
        "document_snippet":    msg.document_snippet,
    }
    ctx.storage.set(msg.session_id, json.dumps(payload))
    ctx.storage.set(_LATEST_SESSION_KEY, msg.session_id)
    if msg.host_a_personality:
        ctx.storage.set(_PERSONALITY_KEY, msg.host_a_personality)
    ctx.logger.info(f"[HostA] Context stored for session {msg.session_id[:8]} — '{msg.topic_title}'")

# ── Debate turn (Orchestrator → HostA → Orchestrator) ────────────────────────

@host_a.on_message(DebateTurn)
async def handle_debate_turn(ctx: Context, sender: str, msg: DebateTurn) -> None:
    ctx.logger.info(f"[HostA] Debate turn {msg.turn}/{msg.max_turns} — session {msg.session_id[:8]}")

    history_block = ""
    if msg.debate_history:
        history_block = f"--- DEBATE SO FAR ---\n{msg.debate_history}\n--- END OF DEBATE HISTORY ---\n\n"

    if msg.previous_statement:
        user_content = (
            f"Topic: {msg.topic_title}\n"
            f"Core thesis: {msg.core_thesis}\n"
            f"Key metrics: {', '.join(msg.key_metrics)}\n"
            f"Controversy: {msg.controversial_point}\n"
            f"Paper excerpt: {msg.document_snippet[:1500]}\n\n"
            f"{history_block}"
            f"The Expert just said:\n\"{msg.previous_statement}\"\n\n"
            f"This is turn {msg.turn + 1} of {msg.max_turns}.\n"
            "IMPORTANT: Do NOT repeat any argument already made in the debate history above. "
            "Introduce a NEW angle, a different data point from the paper, or a fresh implication. "
            "Push the conversation forward. 2-3 punchy sentences."
        )
    else:
        user_content = (
            f"Topic: {msg.topic_title}\n"
            f"Core thesis: {msg.core_thesis}\n"
            f"Key metrics: {', '.join(msg.key_metrics)}\n"
            f"Controversy: {msg.controversial_point}\n"
            f"Paper excerpt: {msg.document_snippet[:1500]}\n\n"
            "Open the debate with a sharp, skeptical challenge. "
            "2-3 provocative but grounded sentences."
        )

    personality = msg.speaker_personality or ctx.storage.get(_PERSONALITY_KEY) or _DEFAULT_PERSONALITY
    system_prompt = (
        f"You are Host A — 'The Skeptic' — in a LIVE podcast debate.\n"
        f"Personality: {personality}\n"
        "Rules:\n"
        "- Respond ONLY with your spoken line. No labels, no stage directions.\n"
        "- NEVER repeat an argument you or the Expert already made.\n"
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
        ctx.logger.error(f"[HostA] Debate LLM error: {e}")
        reply_text = "*(The Skeptic is gathering thoughts…)*"

    try:
        await ctx.send(sender, DebateResponse(
            session_id=msg.session_id,
            speaker="skeptic",
            reply_text=reply_text,
            turn=msg.turn,
            max_turns=msg.max_turns,
            user_address=msg.user_address,
            topic_title=msg.topic_title,
            core_thesis=msg.core_thesis,
            key_metrics=msg.key_metrics,
            controversial_point=msg.controversial_point,
            document_snippet=msg.document_snippet,
        ))
        ctx.logger.info(f"[HostA] DebateResponse sent for turn {msg.turn}.")
    except Exception as e:
        ctx.logger.error(f"[HostA] Failed to send DebateResponse: {e}")


# ── User Q&A (from ASI:One chat) ──────────────────────────────────────────────

@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    ctx.logger.info(f"[HostA] ChatMessage from {sender[:20]}… content types: {[type(c).__name__ for c in msg.content]}")
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
        ctx.logger.warning("[HostA] No TextContent found in message — skipping.")
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
        "You are Host A from a research podcast debate — 'The Skeptic'.\n"
        f"Personality: {personality}\n\n"
        "The user is asking a follow-up question about a paper you just debated. "
        "Answer in character. Be concise (2–4 sentences max). Cite exact numbers "
        "from the context when you challenge or probe a claim."
    )

    user_msg = {"role": "user", "content": user_text}
    if context_str:
        user_msg["content"] = f"[Paper context]\n{context_str}\n\n[User question]\n{user_text}"

    try:
        resp = await _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": qa_system},
                user_msg,
            ],
            temperature=0.75,
            max_tokens=300,
        )
        reply_text = resp.choices[0].message.content or "…"
    except Exception as e:
        ctx.logger.error(f"[HostA] LLM error: {e}")
        reply_text = "*(Host A is thinking…  try again in a moment)*"

    ctx.logger.info(f"[HostA] Sending reply to {sender[:16]}…")
    try:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=f"**[Host A — The Skeptic]**\n\n{reply_text}"),
                    EndSessionContent(type="end-session"),
                ],
            ),
        )
        ctx.logger.info("[HostA] Reply sent successfully.")
    except Exception as e:
        ctx.logger.error(f"[HostA] Failed to send reply: {e}")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    pass


host_a.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    host_a.run()
