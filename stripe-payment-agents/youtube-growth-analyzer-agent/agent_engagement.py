"""
Engagement agent: views, likes, comments, cadence, and top-performing videos.
Used for the paid premium report only.
"""

from __future__ import annotations

import logging
import statistics
from collections import Counter
from typing import Iterable

from models import ChannelSnapshot, EngagementMetrics

logger = logging.getLogger(__name__)


def _tokenize_title(title: str) -> list[str]:
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "vs",
        "v",
        "i",
        "my",
        "our",
        "you",
        "your",
        "is",
        "are",
        "this",
        "that",
        "it",
        "at",
        "from",
    }
    raw = [t.strip(".,|:()[]\"'").lower() for t in title.split()]
    return [t for t in raw if t and len(t) > 2 and t not in stop]


def analyze_engagement(snapshot: ChannelSnapshot) -> EngagementMetrics:
    videos = list(snapshot.recent_videos)
    views = [v.view_count for v in videos if v.view_count is not None]
    avg_v = float(sum(views) / len(views)) if views else None
    med_v = float(statistics.median(views)) if views else None

    rates: list[float] = []
    for v in videos:
        if (
            v.view_count
            and v.view_count > 0
            and v.like_count is not None
            and v.comment_count is not None
        ):
            eng = (v.like_count + v.comment_count) / v.view_count
            rates.append(eng)
    avg_eng = float(sum(rates) / len(rates)) if rates else None

    dates = sorted([v.published_at for v in videos if v.published_at], reverse=True)
    uploads_week: float | None = None
    if len(dates) >= 2:
        span_days = max((dates[0] - dates[-1]).days, 1)
        uploads_week = len(dates) / span_days * 7

    ranked = sorted(
        [v for v in videos if v.view_count is not None],
        key=lambda x: x.view_count or 0,
        reverse=True,
    )
    top_ids = [v.video_id for v in ranked[:5]]

    c_hint = None
    if views:
        c_ratios = []
        for v in videos:
            if v.view_count and v.view_count > 0 and v.comment_count is not None:
                c_ratios.append(v.comment_count / v.view_count)
        if c_ratios:
            c_hint = "higher" if statistics.median(c_ratios) >= 0.002 else "mixed/low"

    return EngagementMetrics(
        avg_views_recent=avg_v,
        median_views_recent=med_v,
        avg_engagement_rate=avg_eng,
        uploads_per_week_recent=uploads_week,
        top_video_ids_by_views=top_ids,
        comment_to_view_ratio_hint=c_hint,
    )


def top_performing_patterns(snapshot: ChannelSnapshot, top_ids: Iterable[str]) -> str:
    """Heuristic content patterns from titles of top videos."""
    id_set = set(top_ids)
    top_videos = [v for v in snapshot.recent_videos if v.video_id in id_set]
    tokens: list[str] = []
    for v in top_videos:
        tokens.extend(_tokenize_title(v.title))
    counts = Counter(tokens)
    common = [w for w, _ in counts.most_common(8)]
    if not common:
        return "Titles in the top-performing set are diverse; patterns are not obvious from keywords alone."
    return "Recurring themes in top-performing titles include: " + ", ".join(common)
