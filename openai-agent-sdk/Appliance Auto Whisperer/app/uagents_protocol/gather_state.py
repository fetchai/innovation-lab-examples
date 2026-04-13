"""Helpers for scatter-gather state stored on the orchestrator KeyValueStore."""

from __future__ import annotations

from typing import Any


def gather_key(correlation_id: str) -> str:
    return f"gather:{correlation_id}"


def initial_gather(
    *,
    vision: dict[str, Any],
    user_session_id: str,
    reply_to: str,
) -> dict[str, Any]:
    return {
        "vision": vision,
        "scrape": None,
        "video": None,
        "user_session_id": user_session_id,
        "reply_to": reply_to,
    }


def with_scrape(state: dict[str, Any], scrape: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["scrape"] = scrape
    return out


def with_video(state: dict[str, Any], video: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["video"] = video
    return out


def is_gather_complete(state: dict[str, Any]) -> bool:
    return bool(state.get("vision") and state.get("scrape") and state.get("video"))
