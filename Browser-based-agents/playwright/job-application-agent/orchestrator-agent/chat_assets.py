"""Helpers for getting binary assets into chat.

We try two channels because chat clients (especially ASI:One builds) are
inconsistent about which one they will render inline:

1. **Public HTTPS host (catbox.moe)** — direct URL, embedded in markdown
   image syntax inside a `TextContent`. This renders in virtually any
   markdown-capable chat UI.
2. **Agentverse external storage** — `agent-storage://...` URI wrapped in
   `ResourceContent`. This is the canonical path but some clients fall
   back to a plain link.

Callers should try the public path first and only fall back to
external storage if the public upload fails.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

import requests
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    Resource,
    ResourceContent,
    TextContent,
)
from uagents_core.storage import ExternalStorage


CATBOX_URL = "https://catbox.moe/user/api.php"


def upload_public_image(
    image_bytes: bytes,
    *,
    filename: str = "form-preview.png",
    mime_type: str = "image/png",
    logger=None,
    timeout: float = 15.0,
) -> Optional[str]:
    """Upload bytes to catbox.moe (free, anonymous, no API key). Returns a
    direct HTTPS URL on success, or None on any failure so callers can
    fall back."""
    try:
        resp = requests.post(
            CATBOX_URL,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (filename, image_bytes, mime_type)},
            timeout=timeout,
        )
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("https://"):
            if logger:
                logger.warning(f"catbox: unexpected response: {url[:200]!r}")
            return None
        if logger:
            logger.info(f"catbox: uploaded {len(image_bytes)} bytes → {url}")
        return url
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning(f"catbox: upload failed: {exc}")
        return None


def make_markdown_image_message(
    image_url: str, *, caption: Optional[str] = None
) -> ChatMessage:
    """Build a `ChatMessage` whose content is markdown text embedding the
    image with `![](url)` syntax. Renders inline in any markdown-aware
    chat client; gracefully degrades to a clickable link otherwise."""
    md_lines: list[str] = []
    if caption:
        md_lines.append(caption)
    md_lines.append(f"![form preview]({image_url})")
    md_lines.append(f"[🔍 Open full size]({image_url})")
    body = "\n\n".join(md_lines)
    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=body)],
    )


AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
AGENTVERSE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai")
STORAGE_URL = f"{AGENTVERSE_URL}/v1/storage"


_storage_singleton: Optional[ExternalStorage] = None


def get_storage() -> Optional[ExternalStorage]:
    """Lazy-init the storage client. Returns None if no API key is set, so
    callers can fall back to text-only updates without crashing."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton
    if not AGENTVERSE_API_KEY:
        return None
    _storage_singleton = ExternalStorage(
        api_token=AGENTVERSE_API_KEY,
        storage_url=STORAGE_URL,
    )
    return _storage_singleton


def upload_image(
    image_bytes: bytes,
    *,
    name_prefix: str = "form-fill",
    mime_type: str = "image/png",
    grant_to_address: Optional[str] = None,
    logger=None,
) -> Optional[tuple[str, str]]:
    """Upload `image_bytes` to Agentverse external storage.

    Returns (asset_id, asset_uri) on success, or None on any error so the
    caller can drop back to text-only chat messages.
    """
    storage = get_storage()
    if storage is None:
        if logger:
            logger.warning("chat_assets: no AGENTVERSE_API_KEY set; skipping upload")
        return None

    ts = int(datetime.now(UTC).timestamp())
    try:
        asset_id = storage.create_asset(
            name=f"{name_prefix}_{ts}",
            content=image_bytes,
            mime_type=mime_type,
        )
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning(f"chat_assets: create_asset failed: {exc}")
        return None

    if grant_to_address:
        try:
            storage.set_permissions(
                asset_id=asset_id,
                agent_address=grant_to_address,
                read=True,
                write=False,
            )
        except Exception as exc:  # noqa: BLE001
            if logger:
                logger.warning(
                    f"chat_assets: set_permissions failed (continuing): {exc}"
                )

    asset_uri = f"agent-storage://{STORAGE_URL}/{asset_id}"
    if logger:
        logger.info(
            f"chat_assets: uploaded {len(image_bytes)} bytes → asset_id={asset_id}"
        )
    return str(asset_id), asset_uri


def make_image_message(
    asset_id: str,
    asset_uri: str,
    *,
    caption: Optional[str] = None,  # noqa: ARG001 — accepted for back-compat, ignored
    mime_type: str = "image/png",
    role: str = "generated-image",
) -> ChatMessage:
    """Build a `ChatMessage` carrying ONLY a `ResourceContent`.

    Captions are sent as a separate `TextContent` message by the caller —
    mixing TextContent + ResourceContent in the same payload has caused
    inconsistent rendering in some ASI:One builds, where the resource
    falls back to a plain link.
    """
    try:
        resource_uuid: UUID = UUID(asset_id)
    except (ValueError, TypeError):
        resource_uuid = uuid4()

    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[
            ResourceContent(
                resource_id=resource_uuid,
                resource=Resource(
                    uri=asset_uri,
                    metadata={
                        "mime_type": mime_type,
                        "role": role,
                    },
                ),
            )
        ],
    )
