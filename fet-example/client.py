"""Gemini Imagen image generation client."""

from __future__ import annotations

import asyncio
import os
from io import BytesIO
from typing import Any, Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
IMAGEN_MODEL = os.getenv("GEMINI_IMAGEN_MODEL", "imagen-4.0-fast-generate-001")
TMPFILES_API_URL = "https://tmpfiles.org/api/v1/upload"


async def upload_image_to_tmpfiles(image_data: bytes, content_type: str) -> Optional[str]:
    """Upload image to tmpfiles.org and return the public download URL (https)."""
    ext = "png" if "png" in content_type else "jpg"
    for attempt in range(3):
        try:
            form = aiohttp.FormData()
            form.add_field("file", image_data, filename=f"image.{ext}", content_type=content_type)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TMPFILES_API_URL, data=form, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if data.get("status") == "success" and data.get("data"):
                        url = (data["data"].get("url") or data.get("url") or "").strip()
                        if url and url.startswith("http"):
                            if url.startswith("http://"):
                                url = "https://" + url[7:]
                            if "tmpfiles.org/" in url and "/dl/" not in url:
                                url = url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/", 1)
                            return url
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
    return None


def run_gemini_image_blocking(
    *,
    prompt: str,
) -> dict[str, Any] | None:
    """Generate one image from a text prompt using Gemini Imagen."""
    if not GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY is not set", "status": "failed"}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {"error": "google-genai not installed. pip install google-genai", "status": "failed"}

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt.strip(),
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )
    except Exception as e:
        return {"error": str(e), "status": "failed"}

    if not response.generated_images or len(response.generated_images) == 0:
        return {"error": "No image generated", "status": "failed"}

    gen = response.generated_images[0]
    image_obj = getattr(gen, "image", None)
    if image_obj is None:
        return {"error": "Generated image has no image attribute", "status": "failed"}

    image_data = None
    content_type = "image/png"

    img_bytes = getattr(image_obj, "image_bytes", None)
    if img_bytes is not None:
        image_data = img_bytes if isinstance(img_bytes, bytes) else bytes(img_bytes)
    else:
        try:
            if hasattr(image_obj, "save"):
                buf = BytesIO()
                image_obj.save(buf, format="PNG")
                image_data = buf.getvalue()
        except Exception as e:
            return {"error": f"Could not extract image bytes: {e}", "status": "failed"}

    if not image_data:
        return {"error": "Could not extract image bytes", "status": "failed"}

    return {
        "image_data": image_data,
        "content_type": content_type,
        "status": "success",
    }
