"""
Lyria RealTime music generation.
Streams audio via live session, saves as WAV, uploads to GCS.
"""

import asyncio
import base64
import wave
import os
import tempfile
import logging
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types

from config import (
    LYRIA_MODEL,
    LYRIA_SAMPLE_RATE,
    LYRIA_CHANNELS,
    SCENE_DURATION_SECONDS,
    key_for_scene,
    API_KEYS,
)
from utils.gcs import upload_to_storage

log = logging.getLogger(__name__)

# Lyria requires v1alpha API version
_clients = {
    k: genai.Client(http_options={"api_version": "v1alpha"}, api_key=k)
    for k in set(API_KEYS)
}


def _is_base64(data: bytes) -> bool:
    if len(data) < 100:
        return False
    b64 = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    return sum(1 for b in data[:100] if b in b64) / 100 > 0.9


def _decode_if_b64(data: bytes) -> bytes:
    if _is_base64(data):
        try:
            return base64.b64decode(data)
        except Exception:
            pass
    return data


def _save_wav(pcm: bytes, path: str) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(LYRIA_CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(LYRIA_SAMPLE_RATE)
        wf.writeframes(pcm)


# ── Public API ──────────────────────────────────────────────────


async def generate_music(
    scene_index: int,
    prompt: str,
    duration: Optional[int] = None,
) -> tuple[str, float]:
    """
    Generate music for a scene via Lyria RealTime.
    Returns (gcs_url, duration_seconds).
    """
    duration = duration or SCENE_DURATION_SECONDS
    api_key = key_for_scene(scene_index)
    client = _clients[api_key]

    log.info(
        "Music scene %d — prompt='%s', dur=%ds", scene_index, prompt[:60], duration
    )

    audio_chunks: list[bytes] = []
    is_collecting = True

    async def _receive(session):
        nonlocal is_collecting
        try:
            async for message in session.receive():
                if not is_collecting:
                    break
                if (
                    hasattr(message, "server_content")
                    and message.server_content is not None
                    and hasattr(message.server_content, "audio_chunks")
                    and message.server_content.audio_chunks
                ):
                    for chunk in message.server_content.audio_chunks:
                        audio_chunks.append(chunk.data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("Lyria receive error: %s", e)

    async with client.aio.live.music.connect(model=LYRIA_MODEL) as session:
        rx = asyncio.create_task(_receive(session))
        try:
            await session.set_weighted_prompts(
                prompts=[types.WeightedPrompt(text=prompt, weight=1.0)]
            )
            await session.set_music_generation_config(
                config=types.LiveMusicGenerationConfig(
                    bpm=120,
                    temperature=1.0,
                    music_generation_mode=types.MusicGenerationMode.QUALITY,
                )
            )
            await session.play()
            log.info("Lyria streaming for %ds…", duration)
            await asyncio.sleep(duration)
            is_collecting = False
            await session.stop()
            await asyncio.sleep(1)
        finally:
            rx.cancel()
            try:
                await rx
            except asyncio.CancelledError:
                pass

    if not audio_chunks:
        raise RuntimeError("No audio generated from Lyria")

    # Decode base64 if needed
    decoded = [_decode_if_b64(c) for c in audio_chunks]
    pcm = b"".join(decoded)
    log.info("Music scene %d: %d bytes PCM", scene_index, len(pcm))

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    _save_wav(pcm, tmp_path)

    with open(tmp_path, "rb") as f:
        wav_data = f.read()
    os.remove(tmp_path)

    filename = f"music_{int(datetime.now().timestamp())}_scene_{scene_index}.wav"
    url = upload_to_storage(wav_data, filename, "audio/wav")
    log.info("Music scene %d uploaded: %s", scene_index, url)
    return url, float(duration)
