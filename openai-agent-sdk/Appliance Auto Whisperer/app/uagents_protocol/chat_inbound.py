"""
Parse incoming `ChatMessage` (Fetch.ai Chat Protocol) for the Diagnostic Orchestrator.

Extracts:
  - context_text  : the user's plain-text message (appliance/vehicle model string)
  - image_base64  : raw base64 bytes (no data-URL prefix) for the OpenAI vision call

Image sources handled (in priority order):
  1. ResourceContent with an HTTP/HTTPS URI  → fetch bytes, encode to base64
  2. ResourceContent with a data: URI        → strip prefix, use base64 payload directly
  3. data:image/...;base64,... embedded in text
  4. A line in text that is entirely base64 (≥ 256 chars, no spaces)
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any

import httpx
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    Resource,
    ResourceContent,
    TextContent,
)

log = logging.getLogger(__name__)

_DATA_URL_RE = re.compile(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", re.DOTALL)
_BARE_B64_RE = re.compile(r"^[A-Za-z0-9+/]{256,}={0,2}$")


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _extract_resource_uri(content: Any) -> str | None:
    """Return the first URI from a ResourceContent block, or None."""
    if not isinstance(content, ResourceContent):
        return None
    r = content.resource
    if isinstance(r, list):
        r = r[0] if r else None
    if r is None:
        return None
    if isinstance(r, Resource) and r.uri:
        return str(r.uri).strip()
    return None


def _collect_text(msg: ChatMessage) -> str:
    """Join all TextContent blocks into one string."""
    parts: list[str] = []
    for c in msg.content:
        if isinstance(c, TextContent) and c.text:
            parts.append(c.text.strip())
    return "\n".join(parts).strip()


async def _uri_to_base64(uri: str) -> str | None:
    """
    Convert a resource URI to raw base64.
    Handles both:
      - data:image/jpeg;base64,<payload>  → return payload directly
      - https://...                       → HTTP fetch, then base64-encode bytes
    """
    if uri.lower().startswith("data:"):
        m = _DATA_URL_RE.match(uri)
        if m:
            return m.group(1)
        # malformed data URI
        return None

    if uri.lower().startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                r = await client.get(uri)
                r.raise_for_status()
                return base64.b64encode(r.content).decode("ascii")
        except Exception as exc:
            log.warning("Failed to fetch image from URI %s: %s", uri, exc)
            return None

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


async def resolve_image_base64(
    image_url: str | None, image_base64: str | None
) -> str | None:
    """
    Utility kept for back-compat with non-Chat-Protocol callers.
    Prefer `extract_diagnostic_inputs` for Chat Protocol messages.
    """
    if image_base64:
        b64 = image_base64.strip()
        if "," in b64 and b64.lower().startswith("data:"):
            b64 = b64.split(",", 1)[1]
        return b64
    if image_url:
        return await _uri_to_base64(image_url)
    return None


async def extract_diagnostic_inputs(msg: ChatMessage) -> tuple[str, str | None]:
    """
    Returns (context_text, image_base64_raw_or_none).

    context_text  : the user's model/context string after stripping image data
    image_base64  : raw base64 (no data-URL prefix), ready for OpenAI vision
    """
    text = _collect_text(msg)
    image_b64: str | None = None

    # Priority 1 & 2: ResourceContent blocks (data: URI or HTTP URL)
    for c in msg.content:
        uri = _extract_resource_uri(c)
        if uri:
            image_b64 = await _uri_to_base64(uri)
            if image_b64:
                break

    # Priority 3: data:image/...;base64,... embedded in the text body
    if not image_b64:
        m = _DATA_URL_RE.search(text)
        if m:
            image_b64 = m.group(1)
            text = _DATA_URL_RE.sub("", text).strip()

    # Priority 4: bare base64 blob on its own line (some clients send this way)
    if not image_b64:
        for line in text.splitlines():
            stripped = line.strip()
            if _BARE_B64_RE.match(stripped):
                try:
                    base64.b64decode(stripped, validate=True)
                    image_b64 = stripped
                    text = text.replace(line, "").strip()
                    break
                except Exception:
                    pass

    # Strip @mention prefixes added by ASI:One (e.g. "@appliance-agent ...")
    context_text = re.sub(r"@\S+\s*", "", text).strip()
    return context_text, image_b64
