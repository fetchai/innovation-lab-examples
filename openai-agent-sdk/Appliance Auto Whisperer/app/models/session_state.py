from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    session_id: str = ""
    appliance_type: str = ""
    last_symptoms: str = ""
    turns: list[dict[str, Any]] = Field(default_factory=list)
