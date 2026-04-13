from __future__ import annotations

from typing import Any

from app.config.settings import get_settings


class BrightDataClient:
    """Thin async wrapper; wire real zone/host when credentials exist."""

    async def search(self, query: str) -> dict[str, Any]:
        settings = get_settings()
        if not settings.brightdata_api_token:
            return {
                "organic": [],
                "note": "BRIGHTDATA_API_TOKEN not set",
                "query": query,
            }
        return {
            "organic": [],
            "note": "Bright Data integration not configured",
            "query": query,
        }
