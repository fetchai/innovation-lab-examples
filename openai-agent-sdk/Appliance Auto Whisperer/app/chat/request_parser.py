from __future__ import annotations

from typing import Any

from app.models.messages import ChatRequest


def parse_chat_payload(payload: dict[str, Any]) -> ChatRequest:
    return ChatRequest(
        session_id=str(payload.get("session_id") or ""),
        appliance_type=str(payload.get("appliance_type") or ""),
        symptoms=str(payload.get("symptoms") or payload.get("message") or ""),
        message=str(payload.get("message") or ""),
        image_base64=payload.get("image_base64"),
    )
