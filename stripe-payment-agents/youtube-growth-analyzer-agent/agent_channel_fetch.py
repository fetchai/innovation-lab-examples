"""
Channel resolution and YouTube Data API fetching.

Accepts a channel URL or a plain channel name, resolves a single channel,
then loads statistics and recent uploads for downstream agents.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from config import RECENT_VIDEO_MAX_RESULTS, get_youtube_api_key
from models import ChannelSnapshot, VideoSnippet, YouTubeResolutionError

logger = logging.getLogger(__name__)

YOUTUBE_BASE = "https://www.googleapis.com/youtube/v3"


def _parse_rfc3339(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except Exception:
        return None


_CONVERSATIONAL_PHRASES = frozenset(
    {
        "hello",
        "hi",
        "hey",
        "help",
        "yes",
        "no",
        "ok",
        "okay",
        "sure",
        "thanks",
        "thank you",
        "bye",
        "reset",
        "start over",
        "new analysis",
        "i paid",
        "done",
        "cancel",
        "stop",
        "what",
        "how",
        "why",
    }
)


def _is_conversational(text: str) -> bool:
    """Return True if the text looks like a conversational phrase rather than a channel name."""
    normalized = re.sub(r"[^\w\s]", "", text.lower()).strip()
    return normalized in _CONVERSATIONAL_PHRASES


def extract_channel_locator(user_text: str) -> str:
    """
    Extract a channel URL, @handle, channel id, or fall back to the first non-empty line
    only when it looks like a plausible channel name (not a conversational phrase).

    Scans all lines so users can type a greeting on line 1 and paste a URL on line 2.
    """
    lines = [ln.strip() for ln in (user_text or "").splitlines() if ln.strip()]
    if not lines:
        return ""

    for ln in lines:
        low = ln.lower()
        if "youtube.com" in low or "youtu.be" in low:
            return ln
        if ln.startswith("@"):
            return ln
        if re.fullmatch(r"UC[\w-]{10,}", ln.strip()):
            return ln.strip()

    candidate = lines[0].strip()
    if _is_conversational(candidate):
        return ""
    return candidate


def parse_youtube_channel_id_or_handle(text: str) -> tuple[str | None, str | None]:
    """
    Return (channel_id, handle) if detectable from a URL or handle string.
    If neither is found, returns (None, None) and callers should search by name.
    """
    t = (text or "").strip()
    if not t:
        return None, None

    # Direct channel id token (UC...)
    m_uc = re.fullmatch(r"(UC[\w-]{10,})", t)
    if m_uc:
        return m_uc.group(1), None

    # URL forms
    if "youtube.com" in t or "youtu.be" in t:
        parsed = urlparse(t if "://" in t else f"https://{t}")
        path = (parsed.path or "").strip("/")
        parts = path.split("/") if path else []

        if "channel" in parts:
            idx = parts.index("channel")
            if idx + 1 < len(parts) and re.match(r"^UC[\w-]{10,}$", parts[idx + 1]):
                return parts[idx + 1], None

        if "@" in path:
            handle = path.split("@", 1)[-1].split("/")[0]
            if handle:
                return None, handle

        qs = parse_qs(parsed.query)
        if "channel" in qs and qs["channel"]:
            cid = qs["channel"][0]
            if re.match(r"^UC[\w-]{10,}$", cid):
                return cid, None

    # @handle in plain text
    if t.startswith("@"):
        return None, t[1:].split()[0].strip()

    return None, None


def _yt_get(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    p = {"key": get_youtube_api_key(), **params}
    r = client.get(f"{YOUTUBE_BASE}/{path}", params=p, timeout=30.0)
    r.raise_for_status()
    return r.json()


def resolve_channel_id(
    client: httpx.Client, query: str
) -> tuple[str | None, YouTubeResolutionError | None]:
    """
    Resolve a channel id from a user-provided URL, handle, or search string.
    """
    cid, handle = parse_youtube_channel_id_or_handle(query)

    if handle:
        try:
            data = _yt_get(client, "channels", {"part": "id", "forHandle": handle})
            items = data.get("items") or []
            if items:
                # channels.list returns the channel id as a string in `id`.
                cid_raw = items[0].get("id")
                if isinstance(cid_raw, str):
                    return cid_raw, None
        except httpx.HTTPStatusError as e:
            logger.warning("forHandle lookup failed: %s", e)

    if cid:
        return cid, None

    try:
        data = _yt_get(
            client,
            "search",
            {"part": "snippet", "type": "channel", "q": query, "maxResults": 5},
        )
        items = data.get("items") or []
        if not items:
            return None, YouTubeResolutionError(
                message="No YouTube channel matched that name.",
                hint="Try a more specific channel name or paste the full channel URL.",
            )
        return items[0]["id"]["channelId"], None
    except httpx.HTTPStatusError as e:
        logger.exception("YouTube search failed")
        return None, YouTubeResolutionError(
            message=f"YouTube API error while searching: {e.response.status_code}",
            hint="Verify YOUTUBE_API_KEY and API quota.",
        )


def fetch_channel_snapshot(
    channel_id: str,
) -> tuple[ChannelSnapshot | None, YouTubeResolutionError | None]:
    """Fetch channel metadata, uploads playlist, and recent video statistics."""
    with httpx.Client() as client:
        try:
            ch = _yt_get(
                client,
                "channels",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": channel_id,
                },
            )
            items = ch.get("items") or []
            if not items:
                return None, YouTubeResolutionError(
                    message="Channel not found after resolution.",
                    hint="The channel may have been deleted or is unavailable.",
                )
            it = items[0]
            stats = it.get("statistics") or {}
            snip = it.get("snippet") or {}
            content = it.get("contentDetails") or {}
            related = content.get("relatedPlaylists") or {}
            uploads = related.get("uploads")
            if not uploads:
                return None, YouTubeResolutionError(
                    message="Channel has no uploads playlist metadata.",
                    hint="Try a different channel.",
                )

            pl = _yt_get(
                client,
                "playlistItems",
                {
                    "part": "snippet,contentDetails",
                    "playlistId": uploads,
                    "maxResults": RECENT_VIDEO_MAX_RESULTS,
                },
            )
            pl_items = pl.get("items") or []
            video_ids: list[str] = []
            playlist_published_at: dict[str, datetime] = {}
            for row in pl_items:
                vid = (row.get("contentDetails") or {}).get("videoId")
                if not vid:
                    continue
                video_ids.append(vid)
                published = (row.get("contentDetails") or {}).get(
                    "videoPublishedAt"
                ) or (row.get("snippet") or {}).get("publishedAt")
                parsed = _parse_rfc3339(published)
                if parsed:
                    playlist_published_at[vid] = parsed

            videos: list[VideoSnippet] = []
            # Batch videos.list in chunks
            for i in range(0, len(video_ids), 50):
                chunk = video_ids[i : i + 50]
                vd = _yt_get(
                    client,
                    "videos",
                    {
                        "part": "statistics,snippet",
                        "id": ",".join(chunk),
                    },
                )
                for v in vd.get("items") or []:
                    vid = v["id"]
                    st = v.get("statistics") or {}
                    sn = v.get("snippet") or {}
                    pub = _parse_rfc3339(
                        sn.get("publishedAt")
                    ) or playlist_published_at.get(vid)
                    if pub is None:
                        # Skip entries with unknown timestamps to avoid corrupting recency-based analysis.
                        continue
                    views = int(st["viewCount"]) if st.get("viewCount") else None
                    likes = int(st["likeCount"]) if st.get("likeCount") else None
                    comments = (
                        int(st["commentCount"]) if st.get("commentCount") else None
                    )
                    videos.append(
                        VideoSnippet(
                            video_id=vid,
                            title=sn.get("title") or "",
                            published_at=pub,
                            view_count=views,
                            like_count=likes,
                            comment_count=comments,
                        )
                    )

            subs = (
                int(stats["subscriberCount"]) if stats.get("subscriberCount") else None
            )
            snapshot = ChannelSnapshot(
                channel_id=channel_id,
                title=snip.get("title") or "Unknown channel",
                description=snip.get("description") or "",
                custom_url=snip.get("customUrl"),
                subscriber_count=subs,
                video_count=int(stats["videoCount"])
                if stats.get("videoCount")
                else None,
                view_count=int(stats["viewCount"]) if stats.get("viewCount") else None,
                country=snip.get("country"),
                published_at=_parse_rfc3339(snip.get("publishedAt")),
                recent_videos=sorted(
                    videos, key=lambda x: x.published_at, reverse=True
                ),
                raw_channel_response=it,
            )
            return snapshot, None
        except httpx.HTTPStatusError as e:
            logger.exception("YouTube HTTP error")
            return None, YouTubeResolutionError(
                message=f"YouTube API HTTP error: {e.response.status_code}",
                hint="Check YOUTUBE_API_KEY, quotas, and channel availability.",
            )
        except Exception as e:
            logger.exception("Unexpected error fetching channel")
            return None, YouTubeResolutionError(
                message=f"Unexpected error while fetching channel data: {e}",
                hint="Retry later or verify inputs.",
            )


def resolve_and_fetch(
    user_query: str,
) -> tuple[ChannelSnapshot | None, YouTubeResolutionError | None]:
    """
    End-to-end: parse user text, resolve channel id, return `ChannelSnapshot` or error.
    """
    q = extract_channel_locator(user_query)
    if not q:
        return None, YouTubeResolutionError(
            message="Please send a YouTube channel URL or channel name.",
            hint="Example: https://www.youtube.com/@SomeChannel or `Some Channel Name`",
        )

    with httpx.Client() as client:
        cid, err = resolve_channel_id(client, q)
        if err or not cid:
            return None, err or YouTubeResolutionError(
                message="Could not resolve channel id."
            )

    return fetch_channel_snapshot(cid)
