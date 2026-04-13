from __future__ import annotations

import logging

from agent_engagement import top_performing_patterns
from models import ChannelSnapshot, EngagementMetrics, PremiumReport

logger = logging.getLogger(__name__)


def build_premium_report(
    snapshot: ChannelSnapshot, engagement: EngagementMetrics
) -> PremiumReport:
    """Create the full paid report (deterministic, API-friendly, demo-ready)."""
    tops = top_performing_patterns(snapshot, engagement.top_video_ids_by_views)
    subs = snapshot.subscriber_count
    med_v = engagement.median_views_recent
    avg_v = engagement.avg_views_recent
    cadence = engagement.uploads_per_week_recent

    overview = (
        f"{snapshot.title} focuses on content surfaced via the public channel metadata and the most recent uploads. "
        f"Subscriber count is {'hidden or unavailable' if subs is None else f'~{subs:,}'}. "
        f"The channel lists {snapshot.video_count if snapshot.video_count is not None else 'an unknown number of'} public videos."
    )

    perf = (
        f"Across the recent sample, median views per upload are about "
        f"{med_v:,.0f} (avg {avg_v:,.0f}) when view counts are available. "
        f"Estimated upload cadence is about {cadence:.2f} uploads/week."
        if cadence and avg_v and med_v
        else "View and cadence signals are partially missing; the premium sections still outline practical next steps."
    )

    if engagement.avg_engagement_rate is not None:
        eng = (
            "Average engagement intensity (likes+comments divided by views) on measurable uploads is "
            f"{engagement.avg_engagement_rate:.4f}. "
        )
    else:
        eng = "Engagement ratios could not be computed for most uploads (likes/comments hidden or missing). "
    eng += f"Comment-to-view signal looks {engagement.comment_to_view_ratio_hint or 'mixed'} in the sample."

    patterns = (
        "Recent titles show a mix of formats; consistency in packaging (title + thumbnail promise) tends to reduce variance. "
        + tops
    )

    weaknesses = (
        "Common growth gaps for channels with similar signals: inconsistent publishing, uneven packaging across hits vs misses, "
        "under-optimized first 24 hours (titles/thumbnails), and weak retention loops (end screens, playlists). "
        "If subscribers are hidden, social proof must be reinforced with on-video clarity and pinned comments."
    )

    recs = [
        "Double down on the top 2 title themes that correlate with your highest recent views; make them a repeatable format.",
        "Stabilize cadence: pick a sustainable weekly rhythm and batch-produce to avoid long gaps.",
        "Improve clickability: rewrite titles for specificity + curiosity while staying accurate to the video.",
        "Add a consistent intro promise in the first 5 seconds to reduce early drop-off.",
        "Use playlists to chain related uploads and increase session time on the channel.",
        "End screens + pinned comment CTA: drive one primary action (subscribe / next video / newsletter).",
        "Measure weekly: track median views per upload and engagement rate, not only peak outliers.",
    ]

    pillars = [
        "Foundational ‘how-to’ or explainers aligned with your best-performing topics",
        "Occasional ‘proof’ or case-style videos that demonstrate outcomes",
        "Lightweight community Q&A or updates to build return viewers",
    ]

    cadence_plan = (
        "If you are under ~2 uploads/week, aim for 2–3 consistent uploads/week for 6 weeks, then reassess median views. "
        "If you already publish frequently, prioritize packaging experiments over raw volume."
    )

    final_sum = (
        "Premium takeaway: treat growth as a packaging + cadence system. Identify your highest median-view themes, "
        "repeat them with small controlled experiments (titles/thumbnails), and compound with playlists and strong CTAs."
    )

    return PremiumReport(
        channel_overview=overview,
        performance_summary=perf,
        engagement_analysis=eng,
        content_pattern_analysis=patterns,
        top_performing_video_patterns=tops,
        growth_weaknesses=weaknesses,
        actionable_recommendations=recs,
        suggested_content_pillars=pillars,
        suggested_posting_cadence=cadence_plan,
        final_growth_strategy_summary=final_sum,
    )
