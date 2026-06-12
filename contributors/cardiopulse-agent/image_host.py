"""
Public image hosting for inline chart delivery.

ASI:One renders markdown images (`![alt](https://...)`) from public URLs
reliably, but it does NOT render Agentverse `ResourceContent` inline. So we
upload the generated chart PNG to a public host and embed the returned URL.

Primary host: catbox.moe — anonymous, no API key, permanent hosting, widely
used by bots. Just POST the file, get a URL back as plain text.

Optional fallback: Imgur, only if IMGUR_CLIENT_ID happens to be set.

`upload_image(png_bytes)` returns a public URL string, or None on failure.
"""

from __future__ import annotations

import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

CATBOX_API = "https://catbox.moe/user/api.php"
IMGUR_API = "https://api.imgur.com/3/image"


def _upload_catbox(png_bytes: bytes) -> str | None:
    """Upload to catbox.moe anonymously. No key required."""
    try:
        files = {"fileToUpload": ("chart.png", png_bytes, "image/png")}
        data = {"reqtype": "fileupload"}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(CATBOX_API, data=data, files=files)
        text = (resp.text or "").strip()
        if resp.status_code == 200 and text.startswith("https://"):
            return text
        logger.warning(
            "catbox upload failed: status=%d body=%s",
            resp.status_code,
            text[:200],
        )
        return None
    except Exception as e:
        logger.warning("catbox upload exception: %s: %s", type(e).__name__, e)
        return None


def _upload_imgur(png_bytes: bytes, title: str) -> str | None:
    """Fallback: upload to Imgur if IMGUR_CLIENT_ID is set."""
    client_id = os.environ.get("IMGUR_CLIENT_ID")
    if not client_id:
        return None
    try:
        headers = {"Authorization": f"Client-ID {client_id}"}
        payload = {
            "image": base64.b64encode(png_bytes).decode(),
            "type": "base64",
            "title": title[:128],
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(IMGUR_API, headers=headers, data=payload)
        if resp.status_code == 200:
            url = (resp.json() or {}).get("data", {}).get("link")
            if url:
                return url
        logger.warning("imgur upload failed: %d %s", resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.warning("imgur upload exception: %s: %s", type(e).__name__, e)
        return None


def upload_image(png_bytes: bytes, title: str = "CardioPulse chart") -> str | None:
    """Upload PNG bytes to a public host. Returns a public URL or None.

    Tries catbox.moe first (no key needed). Falls back to Imgur only if a
    Client-ID is configured.
    """
    url = _upload_catbox(png_bytes)
    if url:
        logger.info("Chart hosted at %s", url)
        return url

    url = _upload_imgur(png_bytes, title)
    if url:
        logger.info("Chart hosted at %s (imgur fallback)", url)
        return url

    logger.warning("All image hosts failed — chart will be skipped.")
    return None
