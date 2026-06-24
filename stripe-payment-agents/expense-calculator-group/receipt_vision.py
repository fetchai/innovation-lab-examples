"""
Extract line items (name, price) from a receipt image using OpenAI Vision.
"""

from __future__ import annotations

import base64
import json
import re
from decimal import Decimal
from typing import Any

# Lazy import openai so agent can run without it for non-photo flows
_openai_client: Any = None


def _get_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        import os

        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for receipt photo extraction")
        _openai_client = OpenAI(api_key=key)
    return _openai_client


def _image_media_type_from_bytes(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and b"WEBP" in data[:12]:
        return "image/webp"
    return "image/jpeg"


EXTRACT_PROMPT = """You are looking at a photo of a receipt (restaurant, grocery, or store).
Extract every line item that has a price. For each line return:
- name: short item name (e.g. "Pizza", "Coffee")
- price: number only (e.g. 12.50)

Return ONLY a JSON array, no other text. Example:
[{"name": "Pizza", "price": 12.00}, {"name": "Coffee", "price": 3.50}]
If you cannot read the receipt or find no items, return [].
Use decimal numbers for prices. No currency symbols in the JSON."""


def extract_items_from_receipt_image(image_bytes: bytes) -> list[tuple[str, Decimal]]:
    """
    Call OpenAI Vision to extract (name, price) line items from receipt image.
    Returns list of (name, price) tuples. Empty list on failure or no items.
    """
    client = _get_client()
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = _image_media_type_from_bytes(image_bytes)
    url = f"data:{mime};base64,{b64}"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACT_PROMPT},
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }
            ],
            max_tokens=1024,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        return []

    # Parse JSON array from response (may be wrapped in markdown code block)
    text = re.sub(r"^```\w*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    result: list[tuple[str, Decimal]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("item") or ""
        price = entry.get("price")
        if not name or price is None:
            continue
        try:
            p = Decimal(str(price))
            if p > 0:
                result.append((str(name).strip(), p))
        except Exception:
            continue
    return result
