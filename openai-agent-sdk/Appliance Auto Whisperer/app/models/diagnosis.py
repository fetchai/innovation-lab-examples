from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DiagnosisPayload(BaseModel):
    summary: str = ""
    likely_causes: list[str] = Field(default_factory=list)
    suggested_parts: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
