"""
Free-tier analysis agent: lightweight preview only (no premium sections).
"""

from __future__ import annotations

import logging
import statistics

from models import ChannelSnapshot, FreePreviewResult

logger = logging.getLogger(__name__)


def _upload_frequency_summary(snapshot: ChannelSnapshot) -> str:
    videos = snapshot.recent_videos
    if len(videos) < 2:
        return "Not enough recent uploads in the sample to estimate cadence reliably."

    dates = sorted([v.published_at for v in videos if v.published_at], reverse=True)
    if len(dates) < 2:
        return "Upload timestamps were not fully available for cadence analysis."

    span_days = max((dates[0] - dates[-1]).days, 1)
    rate = len(dates) / span_days * 7
    return f"About {rate:.1f} uploads/week over the last ~{span_days} days (from recent sample)."


def _performance_observation(snapshot: ChannelSnapshot) -> str:
    views = [v.view_count for v in snapshot.recent_videos if v.view_count is not None]
    if not views:
        return "Recent view counts were unavailable for several uploads (common for very new or restricted videos)."

    med = statistics.median(views)
    mx = max(views)
    ratio = (mx / med) if med else 0.0
    if ratio >= 10:
        return "A few videos strongly outperform the typical recent upload (high hit-rate variance)."
    if ratio >= 3:
        return (
            "Performance is uneven: some videos punch above the median, others trail."
        )
    return "Recent uploads are relatively consistent in view performance."


def _quick_insights(snapshot: ChannelSnapshot) -> list[str]:
    insights: list[str] = []
    subs = snapshot.subscriber_count
    views = [v.view_count for v in snapshot.recent_videos if v.view_count is not None]
    if views and subs and subs > 0:
        avg_v = sum(views) / len(views)
        vr = avg_v / subs
        insights.append(
            f"Rough views-per-subscriber on recent uploads (avg views / subs): {vr:.4f}"
        )
    if snapshot.video_count is not None:
        insights.append(
            f"Public video count on the channel page: {snapshot.video_count}"
        )

    if not insights:
        insights.append(
            "Subscriber and view signals are partially hidden; premium analysis will focus on patterns we can measure."
        )

    if len(insights) < 2:
        freq = _upload_frequency_summary(snapshot)
        insights.append(freq[:200] + ("…" if len(freq) > 200 else ""))

    return insights[:2]


def build_free_preview(snapshot: ChannelSnapshot) -> FreePreviewResult:
    """Produce the required free preview object (and markdown via `.to_markdown()`)."""
    return FreePreviewResult(
        channel_name=snapshot.title,
        subscriber_count=snapshot.subscriber_count,
        upload_frequency_summary=_upload_frequency_summary(snapshot),
        performance_observation=_performance_observation(snapshot),
        insights=_quick_insights(snapshot),
        cta="Pay $5 to unlock the full growth report",
    )
