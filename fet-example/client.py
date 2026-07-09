"""ASI1 One LLM API client."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_ONE_MODEL = os.getenv("ASI_ONE_MODEL", "asi1")
TMPFILES_API_URL = "https://tmpfiles.org/api/v1/upload"


def upload_to_tmpfiles(image_bytes: bytes, filename: str = "asi1_image.png") -> str:
    """Upload image to tmpfiles.org and return the public download URL (https)."""
    try:
        response = requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": (filename, image_bytes, "image/png")},
            timeout=120,
        )
        response.raise_for_status()
        response_data = response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Tmpfiles upload failed: {e}") from e

    raw_url = response_data.get("data", {}).get("url")
    if not raw_url:
        raise RuntimeError(f"Tmpfiles upload returned no URL: {response_data}")

    # Convert page URL to direct download URL for easier image rendering in chat clients.
    return raw_url.replace("http://tmpfiles.org/", "https://tmpfiles.org/dl/")


async def call_asi_one_api(
    *,
    prompt: str,
    size: str = "auto",
) -> dict[str, Any] | None:
    """Call ASI1 One Image Generation API with a text prompt and upload image to tmpfiles.org.
    Matches the logic from the ASI1 image generation example."""
    if not ASI_ONE_API_KEY:
        return {"error": "ASI_ONE_API_KEY is not set", "status": "failed"}

    try:
        url = "https://api.asi1.ai/v1/image/generate"
        payload = {
            "model": ASI_ONE_MODEL,
            "prompt": prompt.strip(),
            "size": size,
        }
        headers = {
            "Authorization": f"Bearer {ASI_ONE_API_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if not response.ok:
            return {
                "error": f"{response.status_code} Error from ASI image API: {response.text}",
                "status": "failed",
            }

        response_data = response.json()

        # Follow the exact logic from the example
        image_url = response_data.get("image_url") or response_data.get("url")

        if not image_url:
            data_items = response_data.get("data", [])
            if data_items and isinstance(data_items, list):
                first_item = data_items[0] if data_items else {}
                image_url = first_item.get("url")
                if not image_url and first_item.get("b64_json"):
                    # Decode base64 and upload to tmpfiles
                    try:
                        image_bytes = base64.b64decode(first_item["b64_json"])
                        image_url = await asyncio.to_thread(
                            upload_to_tmpfiles, image_bytes
                        )
                    except Exception as e:
                        return {
                            "error": f"Failed to process base64 image: {str(e)}",
                            "status": "failed",
                        }

        if not image_url:
            return {
                "error": f"ASI image API returned no image URL: {response_data}",
                "status": "failed",
            }

        return {
            "image_url": image_url,
            "status": "success",
        }
    except requests.RequestException as e:
        return {
            "error": f"Image generation request failed: {str(e)}",
            "status": "failed",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
