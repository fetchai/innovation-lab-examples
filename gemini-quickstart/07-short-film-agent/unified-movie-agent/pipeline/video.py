"""
Veo 3.1 video generation — scene videos, opening, and closing.
Each call uses the API key assigned to its scene index.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from google import genai
from google.genai import types

from config import (
    VEO_MODEL,
    VEO_RESOLUTION,
    VEO_ASPECT_RATIO,
    SCENE_DURATION_SECONDS,
    key_for_scene,
    OPENING_KEY,
    CLOSING_KEY,
    API_KEYS,
)
from utils.gcs import upload_to_storage

log = logging.getLogger(__name__)

# Minimum video file size (bytes). Black/blank Veo outputs are typically
# 50-150 KB, while real 8s 720p videos are 2-15 MB.
MIN_VIDEO_BYTES = 200_000  # 200 KB

# ── Pre-build one client per API key ────────────────────────────
_clients = {k: genai.Client(api_key=k) for k in set(API_KEYS)}


def _get_client(api_key: str) -> genai.Client:
    return _clients[api_key]


# ── Helpers ──────────────────────────────────────────────────────


async def _download_image(url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        data = resp.content
        if data.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            mime = "image/gif"
        elif data.startswith(b"RIFF") and b"WEBP" in data[:12]:
            mime = "image/webp"
        else:
            mime = "image/jpeg"
        return data, mime


async def _build_refs(urls: Optional[List[str]]) -> Optional[list]:
    if not urls:
        return None
    refs = []
    for url in urls[:3]:
        try:
            img_bytes, mime = await _download_image(url)
            refs.append(
                types.VideoGenerationReferenceImage(
                    image=types.Image(image_bytes=img_bytes, mime_type=mime),
                    reference_type="asset",
                )
            )
        except Exception as e:
            log.warning("Failed to download ref image %s: %s", url, e)
    return refs or None


async def _generate_video(
    client: genai.Client,
    api_key: str,
    prompt: str,
    ref_images: Optional[list] = None,
) -> str:
    """
    Submit a Veo job, poll until done, download bytes, upload to GCS.
    Returns the public URL.
    """
    cfg = types.GenerateVideosConfig(
        number_of_videos=1,
        resolution=VEO_RESOLUTION,
        duration_seconds=SCENE_DURATION_SECONDS,
        aspect_ratio=VEO_ASPECT_RATIO,
    )
    if ref_images:
        cfg = types.GenerateVideosConfig(
            number_of_videos=1,
            resolution=VEO_RESOLUTION,
            duration_seconds=SCENE_DURATION_SECONDS,
            aspect_ratio=VEO_ASPECT_RATIO,
            reference_images=ref_images,
        )

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        config=cfg,
    )
    log.info("Veo operation started: %s", operation.name)

    # Poll (max ~10 min)
    for tick in range(60):
        if operation.done:
            break
        log.info("Polling Veo… %ds", tick * 10)
        await asyncio.sleep(10)
        operation = client.operations.get(operation)

    if not operation.done:
        raise TimeoutError("Veo generation timed out after 10 min")

    if hasattr(operation, "error") and operation.error:
        raise RuntimeError(f"Veo operation error: {operation.error}")

    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError("No video generated (possibly content-policy block)")

    video = operation.response.generated_videos[0].video

    # Download bytes
    try:
        video_bytes = client.files.download(file=video)
    except Exception:
        uri = (
            getattr(video, "uri", None)
            or f"https://generativelanguage.googleapis.com/v1beta/{video.name}"
        )
        import requests

        resp = requests.get(uri, headers={"Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
        video_bytes = resp.content

    # Guard: detect black / blank videos by file size
    size = len(video_bytes)
    if size < MIN_VIDEO_BYTES:
        raise RuntimeError(
            f"Veo returned a likely black/blank video ({size:,} bytes < "
            f"{MIN_VIDEO_BYTES:,} byte minimum). Will retry."
        )
    log.info("Video size OK: %s bytes", f"{size:,}")

    filename = f"video_{int(datetime.now().timestamp())}_{id(video_bytes) % 10000}.mp4"
    url = upload_to_storage(video_bytes, filename, "video/mp4")
    log.info("Video uploaded: %s", url)
    return url


# ── Public API ──────────────────────────────────────────────────


async def generate_scene_video(
    scene_index: int,
    prompt: str,
    ref_urls: Optional[List[str]] = None,
) -> str:
    """Generate a scene video. Returns GCS URL."""
    api_key = key_for_scene(scene_index)
    client = _get_client(api_key)
    refs = await _build_refs(ref_urls)
    log.info("Generating video for scene %d", scene_index)
    return await _generate_video(client, api_key, prompt, refs)


async def generate_opening(
    title: str,
    logline: str,
    ref_urls: Optional[List[str]] = None,
) -> str:
    """Generate opening title sequence. Returns GCS URL."""
    client = _get_client(OPENING_KEY)
    refs = await _build_refs(ref_urls)
    prompt = (
        f"Cinematic opening title sequence: '{title}' appears in bold elegant text "
        f"over a dramatic background with sweeping camera movement, fast-paced montage "
        f"style, epic and engaging, professional film opening."
    )
    log.info("Generating opening video")
    return await _generate_video(client, OPENING_KEY, prompt, refs)


async def generate_closing(title: str) -> str:
    """Generate closing credits. Returns GCS URL."""
    client = _get_client(CLOSING_KEY)
    prompt = (
        "Professional film end credits scrolling upward over elegant bokeh background. "
        "Text reads: 'Produced by ASI:One. Directed by Google Gemini. Executed by Agentverse.' "
        "Powered by Veo 3.1, Lyria Music, Gemini TTS, ASI:One and Agentverse.' "
        "Soft cinematic lighting, warm and grateful tone, classic movie credits style."
    )
    log.info("Generating closing credits")
    return await _generate_video(client, CLOSING_KEY, prompt)
