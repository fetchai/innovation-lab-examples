from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = ""
    appliance_type: str = ""
    symptoms: str = ""
    message: str = ""
    image_base64: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    markdown: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
