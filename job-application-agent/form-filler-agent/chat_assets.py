"""Helpers for uploading binary assets to Agentverse external storage and
wrapping them in `ChatMessage(ResourceContent)` so they render inline in
ASI:One. Used by the live-fill flow to stream form screenshots into chat.

Pattern follows `gemini-quickstart/02-imagen-agent/imagen_agent.py`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    Resource,
    ResourceContent,
    TextContent,
)
from uagents_core.storage import ExternalStorage


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
) -> Optional[tuple[str, str]]:
    """Upload `image_bytes` to Agentverse external storage.

    Returns (asset_id, asset_uri) on success, or None on any error so the
    caller can drop back to text-only chat messages.
    """
    storage = get_storage()
    if storage is None:
        return None

    ts = int(datetime.now(UTC).timestamp())
    try:
        asset_id = storage.create_asset(
            name=f"{name_prefix}_{ts}",
            content=image_bytes,
            mime_type=mime_type,
        )
    except Exception:  # noqa: BLE001
        return None

    if grant_to_address:
        try:
            storage.set_permissions(asset_id=asset_id, agent_address=grant_to_address)
        except Exception:  # noqa: BLE001
            # Permission set failure usually still leaves the asset readable
            # via the agent-storage URI for the originating chat session,
            # so try to render anyway.
            pass

    asset_uri = f"agent-storage://{STORAGE_URL}/{asset_id}"
    return str(asset_id), asset_uri


def make_image_message(
    asset_id: str,
    asset_uri: str,
    *,
    caption: Optional[str] = None,
    mime_type: str = "image/png",
    role: str = "form-fill-preview",
) -> ChatMessage:
    """Build a `ChatMessage` carrying a `ResourceContent` (image) and an
    optional text caption underneath."""
    try:
        resource_uuid: UUID = UUID(asset_id)
    except (ValueError, TypeError):
        # ExternalStorage usually returns a UUID string; fall back to a fresh
        # UUID if the asset id isn't parseable so the message still validates.
        resource_uuid = uuid4()

    content: list = [
        ResourceContent(
            type="resource",
            resource_id=resource_uuid,
            resource=Resource(
                uri=asset_uri,
                metadata={"mime_type": mime_type, "role": role},
            ),
        )
    ]
    if caption:
        content.append(TextContent(type="text", text=caption))

    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=content,
    )
