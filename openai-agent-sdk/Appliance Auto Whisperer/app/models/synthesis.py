from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SynthesisResult(BaseModel):
    summary: str = ""
    next_steps: list[str] = Field(default_factory=list)
    estimated_cost_range: tuple[float, float] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
