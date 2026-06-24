"""
Auto-generate character reference images using Gemini image generation.
Used when the user doesn't provide reference images, to ensure character
consistency across all Veo-generated scenes.

Flow:
  1. Gemini Flash extracts main characters (up to 3) from the story plan
  2. Gemini Flash Image generates a portrait reference for each character
  3. Images are uploaded to GCS and returned as URLs
  4. These URLs are passed as ref_urls to all Veo scene calls
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import List

from google import genai
from google.genai import types

from config import API_KEYS, CREATIVE_MODEL, IMAGE_GEN_MODEL
from utils.gcs import upload_to_storage

log = logging.getLogger(__name__)

# Use key 0 (same as creative director) — runs sequentially after creative planning
_client = genai.Client(api_key=API_KEYS[0])

MAX_CHARACTER_REFS = 3


# ── Step 1: Extract characters from the story plan ───────────────


async def _extract_characters(
    story_title: str,
    story_logline: str,
    scene_visual_prompts: List[str],
) -> List[dict]:
    """Use Gemini to identify main characters and build image-gen prompts."""
    scenes_text = "\n".join(
        f"- Scene {i + 1}: {vp}" for i, vp in enumerate(scene_visual_prompts)
    )

    prompt = f"""Analyze this story plan and identify up to {MAX_CHARACTER_REFS} main characters.

Title: {story_title}
Logline: {story_logline}
Scene visual prompts:
{scenes_text}

For each character, provide:
- name: the character's name exactly as used in the visual prompts
- image_prompt: a detailed prompt for generating a REFERENCE PORTRAIT image.
  Describe physical appearance (species, age, size, coloring, features),
  clothing or distinguishing accessories. The image should show the FULL
  character in a clear, well-lit portrait pose against a simple clean background.

Return ONLY valid JSON, no markdown code blocks:
{{
  "characters": [
    {{
      "name": "Character Name",
      "image_prompt": "Full body portrait of [detailed visual description]. Standing naturally against a simple clean background, well-lit, high detail."
    }}
  ]
}}"""

    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=CREATIVE_MODEL,
        contents=[prompt],
    )

    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    data = json.loads(text)
    characters = data.get("characters", [])[:MAX_CHARACTER_REFS]

    for c in characters:
        log.info("Character found: %s", c.get("name", "unknown"))

    return characters


# ── Step 2: Generate one reference image ─────────────────────────


async def _generate_character_image(name: str, image_prompt: str, index: int) -> str:
    """Generate one character reference image and upload to GCS."""
    log.info("Generating reference image for: %s", name)

    config = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    )

    response = await asyncio.to_thread(
        _client.models.generate_content,
        model=IMAGE_GEN_MODEL,
        contents=[image_prompt],
        config=config,
    )

    for part in response.parts:
        if hasattr(part, "inline_data") and part.inline_data is not None:
            image_data = part.inline_data.data
            mime_type = (
                getattr(part.inline_data, "mime_type", "image/png") or "image/png"
            )

            # Handle base64-encoded data (str or bytes)
            if isinstance(image_data, str):
                img_bytes = base64.b64decode(image_data)
            elif isinstance(image_data, bytes):
                # Gemini sometimes returns base64 as bytes
                try:
                    if (
                        image_data[:20]
                        .decode("ascii", errors="ignore")
                        .replace("=", "")
                        .replace("+", "")
                        .replace("/", "")
                        .isalnum()
                    ):
                        img_bytes = base64.b64decode(image_data)
                    else:
                        img_bytes = image_data
                except Exception:
                    img_bytes = image_data
            else:
                log.warning("Unexpected image data type: %s", type(image_data))
                continue

            ext = "png" if "png" in mime_type else "jpg"
            ts = int(datetime.now().timestamp())
            filename = f"charref_{ts}_{index}.{ext}"
            url = upload_to_storage(img_bytes, filename, mime_type)
            log.info(
                "Character ref '%s' uploaded: %s (%d bytes)", name, url, len(img_bytes)
            )
            return url

    raise RuntimeError(f"Image generation returned no image for '{name}'")


# ── Public API ───────────────────────────────────────────────────


async def generate_character_refs(
    story_title: str,
    story_logline: str,
    scene_visual_prompts: List[str],
) -> List[str]:
    """
    Auto-generate character reference images for the story.
    Returns list of GCS URLs (up to MAX_CHARACTER_REFS).
    Falls back gracefully to empty list on any failure.
    """
    log.info("Extracting characters from story plan…")
    try:
        characters = await _extract_characters(
            story_title,
            story_logline,
            scene_visual_prompts,
        )
    except Exception as e:
        log.warning("Character extraction failed: %s — skipping ref generation", e)
        return []

    if not characters:
        log.info("No characters extracted — skipping reference generation")
        return []

    log.info("Generating %d character reference image(s)…", len(characters))

    # Generate all character images in parallel
    tasks = [
        _generate_character_image(c["name"], c["image_prompt"], i)
        for i, c in enumerate(characters)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    urls = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            log.warning("Character ref %d failed: %s", i, result)
        else:
            urls.append(result)

    log.info("Generated %d/%d character reference images", len(urls), len(characters))
    return urls
