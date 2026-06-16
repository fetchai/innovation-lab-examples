"""
Data models used across the pipeline.
Pure dataclasses — no uagents dependency.
"""

from __future__ import annotations
from dataclasses import dataclass, field  # noqa: F401
from typing import List, Optional


@dataclass
class SceneBrief:
    """Per-scene creative brief produced by the Creative Director."""

    scene_index: int  # 1-based (1..8)
    scene_title: str
    visual_prompt: str  # for Veo
    voiceover_prompt: str  # for TTS (≤16 words)
    music_prompt: str  # for Lyria
    duration_seconds: int = 8


@dataclass
class StoryPlan:
    """Full story plan returned by the Creative Director."""

    title: str
    logline: str
    scenes: List[SceneBrief]
    status: str = "ok"  # "ok" | "fallback" | "error"
    error: Optional[str] = None


@dataclass
class SceneResult:
    """Aggregated result for a single scene after all pipeline steps."""

    scene_index: int
    scene_title: str = ""
    video_url: Optional[str] = None
    voice_url: Optional[str] = None
    music_url: Optional[str] = None
    assembled_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class FilmResult:
    """Final output of the full pipeline."""

    title: str
    logline: str
    scenes: List[SceneResult]
    opening_url: Optional[str] = None
    closing_url: Optional[str] = None
    final_url: Optional[str] = None
    error: Optional[str] = None
