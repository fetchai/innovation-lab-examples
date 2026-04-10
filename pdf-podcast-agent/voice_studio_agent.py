"""
Agent 3 – The Voice Studio
==========================
Run in its own terminal:

    python voice_studio_agent.py

Receives the PodcastScript, fires parallel OpenAI TTS calls for every
dialogue line (HostA → "alloy", HostB → "echo"), stitches the audio chunks
into a single MP3 using pydub, saves it to disk, and returns the base64-
encoded final MP3 to the Orchestrator.

Requires:  openai, pydub
ffmpeg on PATH for MP3 export  →  winget install ffmpeg  |  brew install ffmpeg
Fallback: raw byte concatenation if pydub/ffmpeg are unavailable.
"""

import asyncio
import io
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from uagents import Agent, Context
from openai import AsyncOpenAI

from schemas import AudioResponse, PodcastScript

# ── Configuration ─────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TTS_MODEL      = os.getenv("TTS_MODEL", "tts-1")
OUTPUT_DIR     = Path(os.getenv("OUTPUT_DIR", "output"))

VOICE_MAP = {
    "HostA": os.getenv("VOICE_HOST_A", "alloy"),
    "HostB": os.getenv("VOICE_HOST_B", "echo"),
}

SILENCE_BETWEEN_LINES_MS = int(os.getenv("SILENCE_MS", "400"))

# ── Agent ─────────────────────────────────────────────────────────────────────

voice_studio = Agent(
    name="voice_studio",
    seed=os.getenv("VOICE_STUDIO_SEED", "voice_studio_podcast_seed_v1"),
    port=8003,
    endpoint=["http://localhost:8003/submit"],
    network="testnet",
)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _tts_call(text: str, voice: str) -> bytes:
    response = await client.audio.speech.create(
        model=TTS_MODEL,
        voice=voice,
        input=text,
        response_format="mp3",
    )
    return response.content


def _stitch_audio(chunks: list[bytes], silence_ms: int) -> bytes:
    """Stitch MP3 chunks with pydub (best quality) or raw bytes (fallback)."""
    try:
        from pydub import AudioSegment  # noqa: PLC0415

        segments = [AudioSegment.from_mp3(io.BytesIO(c)) for c in chunks]
        gap = AudioSegment.silent(duration=silence_ms) if silence_ms > 0 else None

        combined = segments[0]
        for seg in segments[1:]:
            if gap:
                combined = combined + gap + seg
            else:
                combined = combined + seg

        buf = io.BytesIO()
        combined.export(buf, format="mp3")
        return buf.getvalue()

    except Exception:
        # ffmpeg not available — raw concatenation still plays in most players
        return b"".join(chunks)

# ── Handlers ──────────────────────────────────────────────────────────────────

@voice_studio.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(f"[Voice Studio] ready")
    ctx.logger.info(f"[Voice Studio] address: {ctx.agent.address}")
    ctx.logger.info(f"[Voice Studio] HostA={VOICE_MAP['HostA']}  HostB={VOICE_MAP['HostB']}  model={TTS_MODEL}")


@voice_studio.on_message(model=PodcastScript)
async def handle_voice(ctx: Context, sender: str, msg: PodcastScript) -> None:
    sid = msg.session_id[:8]
    ctx.logger.info(f"[{sid}] Generating {len(msg.lines)} TTS chunks in parallel …")

    try:
        tasks  = [_tts_call(line.text, VOICE_MAP.get(line.speaker, "alloy")) for line in msg.lines]
        chunks = await asyncio.gather(*tasks)

        ctx.logger.info(f"[{sid}] Stitching audio …")
        final_bytes = _stitch_audio(list(chunks), silence_ms=SILENCE_BETWEEN_LINES_MS)

        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in msg.topic_title)[:40]
        filename   = f"podcast_{safe_title}_{timestamp}.mp3"
        audio_path = str(OUTPUT_DIR / filename)

        with open(audio_path, "wb") as f:
            f.write(final_bytes)

        ctx.logger.info(f"[{sid}] Saved → {audio_path}  ({len(final_bytes)/1024:.1f} KB)")

        # Send path only — base64 blob (~2 MB+) exceeds Agentverse mailbox size limit.
        # The orchestrator constructs the download URL from audio_path directly.
        await ctx.send(
            sender,
            AudioResponse(
                audio_base64="",
                audio_path=audio_path,
                session_id=msg.session_id,
                line_count=len(msg.lines),
            ),
        )

    except Exception as exc:
        ctx.logger.error(f"[{sid}] Error: {exc}")
        await ctx.send(
            sender,
            AudioResponse(
                audio_base64="",
                audio_path="",
                session_id=msg.session_id,
                line_count=0,
            ),
        )


if __name__ == "__main__":
    voice_studio.run()
