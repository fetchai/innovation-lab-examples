"""
Gemini TTS voice generation.
Streams audio chunks, decodes base64 if needed, converts to WAV, uploads to GCS.
"""

import asyncio
import base64
import struct
import logging
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types

from config import TTS_MODEL, TTS_DEFAULT_VOICE, key_for_scene, API_KEYS
from utils.gcs import upload_to_storage

log = logging.getLogger(__name__)

_clients = {k: genai.Client(api_key=k) for k in set(API_KEYS)}


# ── Helpers ──────────────────────────────────────────────────────


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


def _parse_mime(mime_type: str) -> dict:
    bits, rate = 16, 24000
    for param in mime_type.split(";"):
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits": bits, "rate": rate}


def _to_wav(pcm: bytes, mime_type: str) -> bytes:
    info = _parse_mime(mime_type)
    bits, rate = info["bits"], info["rate"]
    ch = 1
    byte_rate = rate * ch * (bits // 8)
    block_align = ch * (bits // 8)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        ch,
        rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        len(pcm),
    )
    return header + pcm


def _estimate_duration(wav_bytes: bytes, rate: int = 24000, bits: int = 16) -> float:
    data_size = len(wav_bytes) - 44
    return data_size / (rate * (bits // 8))


# ── Public API ──────────────────────────────────────────────────


def _generate_voice_sync(
    client: genai.Client,
    scene_index: int,
    text: str,
    voice: str,
) -> tuple[bytes, str]:
    """
    Synchronous TTS streaming + WAV conversion.
    Runs in a thread pool so it doesn't block the async event loop.
    """
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
        )
    )

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=text)],
        ),
    ]

    gen_config = types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=speech_config,
    )

    chunks = []
    for chunk in client.models.generate_content_stream(
        model=TTS_MODEL,
        contents=contents,
        config=gen_config,
    ):
        if (
            chunk.candidates
            and chunk.candidates[0].content
            and chunk.candidates[0].content.parts
        ):
            part = chunk.candidates[0].content.parts[0]
            if part.inline_data and part.inline_data.data:
                chunks.append(
                    {
                        "data": part.inline_data.data,
                        "mime_type": part.inline_data.mime_type,
                    }
                )

    if not chunks:
        raise RuntimeError("No audio generated from TTS")

    # Decode base64 if needed
    for c in chunks:
        c["data"] = _decode_if_b64(c["data"])

    pcm = b"".join(c["data"] for c in chunks)
    mime = chunks[0]["mime_type"]
    wav = _to_wav(pcm, mime)
    return wav, mime


async def generate_voice(
    scene_index: int,
    text: str,
    voice: Optional[str] = None,
) -> tuple[str, float]:
    """
    Generate TTS for a scene. Returns (gcs_url, duration_seconds).
    Runs the synchronous Gemini streaming in a thread pool so parallel
    TTS calls don't block each other on the event loop.
    """
    api_key = key_for_scene(scene_index)
    client = _clients[api_key]
    voice = voice or TTS_DEFAULT_VOICE

    log.info("TTS scene %d — voice=%s, text='%s'", scene_index, voice, text[:60])

    # Run synchronous streaming in thread pool (matches original multi-process parallelism)
    wav, mime = await asyncio.to_thread(
        _generate_voice_sync, client, scene_index, text, voice
    )

    duration = _estimate_duration(wav)

    filename = f"tts_{int(datetime.now().timestamp())}_scene_{scene_index}.wav"
    url = upload_to_storage(wav, filename, "audio/wav")
    log.info("TTS scene %d uploaded: %s (%.1fs)", scene_index, url, duration)
    return url, duration
