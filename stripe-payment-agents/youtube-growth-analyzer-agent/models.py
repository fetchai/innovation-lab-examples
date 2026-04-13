"""Pydantic schemas for requests, channel data, and analysis outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VideoSnippet(BaseModel):
    """Lightweight video metadata used by analysis agents."""

    video_id: str
    title: str
    published_at: datetime
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None


class ChannelSnapshot(BaseModel):
    """Resolved channel plus recent uploads for analysis."""

    channel_id: str
    title: str
    description: str = ""
    custom_url: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None
    country: str | None = None
    published_at: datetime | None = None
    recent_videos: list[VideoSnippet] = Field(default_factory=list)
    raw_channel_response: dict[str, Any] = Field(default_factory=dict)


class FreePreviewResult(BaseModel):
    """Structured free preview (also rendered as user-facing text)."""

    channel_name: str
    subscriber_count: int | None
    upload_frequency_summary: str
    performance_observation: str
    insights: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    cta: str = Field(
        default="Pay $5 to unlock the full growth report",
        description="Required call-to-action for premium unlock.",
    )

    def to_markdown(self) -> str:
        lines: list[str] = [
            f"**Channel:** {self.channel_name}",
            f"**Subscribers:** {self.subscriber_count if self.subscriber_count is not None else 'Not available (hidden or unavailable)'}",
            f"**Upload cadence:** {self.upload_frequency_summary}",
            f"**Performance (high level):** {self.performance_observation}",
            "**Quick insights:**",
        ]
        for i, ins in enumerate(self.insights, start=1):
            lines.append(f"{i}. {ins}")
        lines.append("")
        lines.append(f"_{self.cta}_")
        return "\n".join(lines)


class EngagementMetrics(BaseModel):
    """Aggregated engagement metrics for premium sections."""

    avg_views_recent: float | None = None
    median_views_recent: float | None = None
    avg_engagement_rate: float | None = Field(
        default=None,
        description="Rough (likes+comments)/views for recent uploads where data exists.",
    )
    uploads_per_week_recent: float | None = None
    top_video_ids_by_views: list[str] = Field(default_factory=list)
    comment_to_view_ratio_hint: str | None = None


class PremiumReport(BaseModel):
    """Structured premium report sections."""

    channel_overview: str
    performance_summary: str
    engagement_analysis: str
    content_pattern_analysis: str
    top_performing_video_patterns: str
    growth_weaknesses: str
    actionable_recommendations: list[str] = Field(
        default_factory=list, min_length=7, max_length=10
    )
    suggested_content_pillars: list[str] = Field(
        default_factory=list, min_length=3, max_length=6
    )
    suggested_posting_cadence: str
    final_growth_strategy_summary: str

    def to_markdown(self) -> str:
        recs = "\n".join(
            f"{i}. {r}" for i, r in enumerate(self.actionable_recommendations, start=1)
        )
        pillars = "\n".join(f"- {p}" for p in self.suggested_content_pillars)
        parts = [
            "## Channel overview",
            self.channel_overview,
            "",
            "## Performance summary",
            self.performance_summary,
            "",
            "## Engagement analysis",
            self.engagement_analysis,
            "",
            "## Content pattern analysis",
            self.content_pattern_analysis,
            "",
            "## Top-performing video patterns",
            self.top_performing_video_patterns,
            "",
            "## Growth weaknesses",
            self.growth_weaknesses,
            "",
            "## 7 actionable recommendations",
            recs,
            "",
            "## Suggested content pillars",
            pillars,
            "",
            "## Suggested posting cadence",
            self.suggested_posting_cadence,
            "",
            "## Final growth strategy summary",
            self.final_growth_strategy_summary,
        ]
        return "\n".join(parts)


class PaymentActionPayload(BaseModel):
    """
    Machine-readable hint for frontends that parse chat text.
    The canonical payment rail payload is still AgentPayment `RequestPayment.metadata['stripe']`.
    """

    type: str = Field(
        default="stripe_embedded_checkout", description="Payment UX action type."
    )
    amount_usd: str = "5.00"
    currency: str = "USD"
    label: str = "Pay $5 for full report"


class ChannelInput(BaseModel):
    """User-provided channel locator."""

    text: str = Field(..., description="Raw user message or pasted channel URL / name.")

    def normalized_query(self) -> str:
        return (self.text or "").strip()


class YouTubeResolutionError(BaseModel):
    """Error payload when a channel cannot be resolved."""

    message: str
    hint: str | None = None
