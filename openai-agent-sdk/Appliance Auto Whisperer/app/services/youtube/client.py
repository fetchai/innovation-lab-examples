from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import get_settings
from app.models.tutorial import VideoHit
from app.services.youtube.query_builder import build_query
from app.services.youtube.ranking import score_videos


async def search_repair_videos(
    appliance_type: str, symptoms: str, *, max_results: int = 5
) -> list[VideoHit]:
    settings = get_settings()
    q = build_query(appliance_type, symptoms)
    if not settings.youtube_api_key:
        return []

    params: dict[str, Any] = {
        "part": "snippet",
        "type": "video",
        "maxResults": max_results,
        "q": q,
        "key": settings.youtube_api_key,
    }
    url = "https://www.googleapis.com/youtube/v3/search"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    hits: list[VideoHit] = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId", "")
        sn = item.get("snippet", {})
        title = sn.get("title", "")
        ch = sn.get("channelTitle", "")
        if vid:
            hits.append(
                VideoHit(
                    title=title,
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    channel=ch,
                )
            )
    return score_videos(hits)
