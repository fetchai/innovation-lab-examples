"""
Unified Movie Agent — single process, full pipeline.

One uagent that:
  - Exposes the chat protocol on Agentverse
  - Receives user prompts
  - Runs the complete film production pipeline (safety → creative → scenes → stitch)
  - Sends real-time progress updates back to the user
  - Manages a multi-user request queue (one film at a time)
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

from config import AGENT_NAME, AGENT_SEED, AGENT_PORT, SCENE_COUNT  # noqa: E402
from pipeline.orchestrator import produce_film  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# ── Agent + chat protocol ───────────────────────────────────────

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)

# ── URL extractor ───────────────────────────────────────────────

_URL_RE = re.compile(r"https?://\S+")


def _extract(raw: str):
    urls = _URL_RE.findall(raw)
    prompt = raw
    for u in urls:
        prompt = prompt.replace(u, "")
    return urls[:3], prompt.strip()


# ── Chat helpers ────────────────────────────────────────────────


def _chat_msg(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=str(uuid4()),
        content=[TextContent(text=text, type="text")],
    )


# ── Request queue ───────────────────────────────────────────────

_active: Optional[str] = None  # request-id of in-flight film
_queue: List[Dict[str, Any]] = []  # waiting requests


async def _process_queue(ctx: Context) -> None:
    global _active
    if not _queue:
        _active = None
        log.info("Queue empty — ready for new requests.")
        return
    nxt = _queue.pop(0)
    for i, q in enumerate(_queue):
        await ctx.send(
            q["user"], _chat_msg(f"⏳ Queue update: you are now #{i + 1} in line.")
        )
    await _run_film(ctx, nxt["user"], nxt["prompt"], nxt["refs"])


async def _run_film(ctx: Context, user: str, prompt: str, refs: List[str]) -> None:
    """Kick off the full pipeline in-process and stream progress to the user."""
    global _active
    request_id = str(uuid4())
    _active = request_id

    log.info("▶️  Processing request %s from %s…", request_id, user[:16])

    # Notify callback — sends chat messages to the user
    async def notify(msg: str) -> None:
        await ctx.send(user, _chat_msg(msg))

    result = await produce_film(
        user_prompt=prompt,
        ref_urls=refs,
        notify=notify,
    )

    if result.error:
        log.warning("Film failed: %s", result.error)
        if not result.final_url:
            await notify(
                f"🛑 **Film production failed.**\n"
                f"Reason: {result.error}\n\n"
                f"Please try again with a different prompt."
            )
    else:
        # Build final consolidated message with all per-scene links
        lines = [
            f"🎉 **Your full {SCENE_COUNT}-scene AI film is ready!**\n",
            f"📖 **Title:** {result.title}",
            f"🧵 **Logline:** {result.logline}\n",
        ]
        for s in result.scenes:
            lines.append(f"**Scene {s.scene_index}: {s.scene_title}**")
            if s.video_url:
                lines.append(f"🎥 Video: [View]({s.video_url})")
            if s.voice_url:
                lines.append(f"🗣️ Voice: [Listen]({s.voice_url})")
            if s.music_url:
                lines.append(f"🎵 Music: [Listen]({s.music_url})")
            if s.assembled_url:
                lines.append(f"📽️ Assembled: [Watch]({s.assembled_url})")
            lines.append("")
        if result.final_url:
            lines.append(f"📽️ **[Watch Full Movie]({result.final_url})**\n")
            lines.append(f"**Final Movie:**\n")  # noqa: F541
            lines.append(f"![]({result.final_url})\n")
        lines.append("Thank you for creating with the Unified Movie Agent ✨")
        await notify("\n".join(lines))

    log.info("✅ Request %s complete.", request_id)
    await _process_queue(ctx)


# ── Chat handler ────────────────────────────────────────────────


@chat_proto.on_message(ChatMessage)
async def handle_user_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    # Extract text
    full_text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            full_text += item.text + "\n"
    full_text = full_text.strip()
    if not full_text:
        return

    # Acknowledge
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    refs, prompt = _extract(full_text)
    log.info("📨 New request from %s — prompt: %s", sender[:16], prompt[:100])

    if _active is not None:
        _queue.append({"user": sender, "prompt": prompt, "refs": refs})
        pos = len(_queue)
        await ctx.send(
            sender,
            _chat_msg(
                f"⏳ **You're #{pos} in the queue.**\n"
                f"Another film is being produced. I'll start yours automatically!"
            ),
        )
        return

    # No active film — run immediately (as background task so agent stays responsive)
    asyncio.create_task(_run_film(ctx, sender, prompt, refs))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    pass


# ── Lifecycle ───────────────────────────────────────────────────


@agent.on_event("startup")
async def startup(ctx: Context) -> None:
    log.info("🎬 Unified Movie Agent starting…")
    log.info("📍 Address: %s", agent.address)
    log.info("🎞️  %d scenes, parallel mode, 5 API keys", SCENE_COUNT)


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    print("🎬 Unified Movie Agent")
    print(f"📍 Address: {agent.address}")
    print(f"🎞️  {SCENE_COUNT} scenes, parallel, 5 API keys")
    print()
    agent.run()
