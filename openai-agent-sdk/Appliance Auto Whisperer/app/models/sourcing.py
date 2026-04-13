from __future__ import annotations

from pydantic import BaseModel, Field


class PartOffer(BaseModel):
    title: str = ""
    url: str = ""
    vendor: str = ""
    price_hint: str | None = None


class SourcingResult(BaseModel):
    query: str = ""
    offers: list[PartOffer] = Field(default_factory=list)
    notes: str = ""
