"""
YouTube Data API v3: find the best DIY repair tutorial.

Selection criteria (per spec):
  - Highest like-to-view ratio  (engagement quality proxy)
  - Shortest duration           (viewer-friendly for a repair task)
  - Composite score: (likes / views) / max(duration_minutes, 0.5)

Falls back to a search-URL stub when YOUTUBE_API_KEY is not set.
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote_plus

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config.settings import get_settings

log = logging.getLogger(__name__)


def _yt_search_url(query: str) -> str:
    """Build a clean YouTube search URL, truncating to avoid absurdly long links."""
    short = " ".join(query.split()[:12])
    return f"https://www.youtube.com/results?search_query={quote_plus(short)}"


async def find_best_tutorial_video(search_query: str) -> tuple[str, str, int]:
    """
    Returns (video_url, video_title, duration_seconds).

    Queries YouTube Data API v3, fetches video statistics + duration for the top
    10 results, then ranks by: shortest video with highest engagement (likes/views).
    """
    settings = get_settings()
    if not settings.youtube_api_key:
        log.warning("YOUTUBE_API_KEY not set — returning search-URL stub.")
        return (
            _yt_search_url(search_query),
            "Search YouTube for tutorial (set YOUTUBE_API_KEY for auto-selection)",
            0,
        )

    def _run() -> tuple[str, str, int]:
        yt = build(
            "youtube",
            "v3",
            developerKey=settings.youtube_api_key,
            cache_discovery=False,
        )

        search_res = (
            yt.search()
            .list(
                part="id,snippet",
                q=search_query,
                type="video",
                maxResults=10,
                relevanceLanguage="en",
                safeSearch="none",
            )
            .execute()
        )
        items = search_res.get("items") or []
        video_ids = [
            it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")
        ]
        if not video_ids:
            return (
                _yt_search_url(search_query),
                "No tutorials found — search YouTube directly",
                0,
            )

        details_res = (
            yt.videos()
            .list(
                part="contentDetails,statistics,snippet",
                id=",".join(video_ids[:10]),
            )
            .execute()
        )

        best: tuple[str, str, int] | None = None
        best_score = -1.0

        for v in details_res.get("items", []):
            vid = v["id"]
            title = v.get("snippet", {}).get("title", "")
            stats = v.get("statistics", {})
            views = int(stats.get("viewCount") or 0)
            likes = int(stats.get("likeCount") or 0)
            dur_s = _parse_iso_duration(
                v.get("contentDetails", {}).get("duration") or "PT0S"
            )

            if dur_s == 0:
                continue

            dur_min = dur_s / 60.0
            engagement = likes / max(views, 1)
            score = engagement / max(dur_min, 0.5)

            log.debug(
                "  %s | dur=%ds | views=%d | likes=%d | score=%.6f | %s",
                vid,
                dur_s,
                views,
                likes,
                score,
                title,
            )

            if score > best_score:
                best_score = score
                best = (vid, title, dur_s)

        if not best:
            vid = video_ids[0]
            return (f"https://www.youtube.com/watch?v={vid}", "Top result tutorial", 0)

        vid, title, dur_s = best
        log.info("Best tutorial: '%s' (%ds) score=%.6f", title, dur_s, best_score)
        return (f"https://www.youtube.com/watch?v={vid}", title, dur_s)

    try:
        return await asyncio.to_thread(_run)
    except HttpError as exc:
        log.error("YouTube API HttpError: %s", exc)
        return (
            _yt_search_url(search_query),
            "YouTube API error — search manually",
            0,
        )
    except Exception as exc:
        log.error("YouTube service error: %s", exc)
        return (
            _yt_search_url(search_query),
            "Tutorial search unavailable",
            0,
        )


def _parse_iso_duration(iso: str) -> int:
    """Parse ISO 8601 duration (PT#H#M#S) → total seconds."""
    h = m = s = 0
    hm = re.search(r"(\d+)H", iso)
    mm = re.search(r"(\d+)M", iso)
    sm = re.search(r"(\d+)S", iso)
    if hm:
        h = int(hm.group(1))
    if mm:
        m = int(mm.group(1))
    if sm:
        s = int(sm.group(1))
    return h * 3600 + m * 60 + s
