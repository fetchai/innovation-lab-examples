"""
Layer 3 — LLM reranking via ASI:One.

Takes the top N scored candidates, asks ASI:One to rerank them
against the user's full preference context, and returns a final
ranked list with a one-line explanation per event.
"""

import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from config import ASI_ONE_API_KEY, ASI_ONE_BASE_URL, ASI_ONE_MODEL
from recommend.score import _parse_jsonb


def rerank(candidates: list[dict], prefs: dict) -> list[dict]:
    """
    Ask ASI:One to rerank candidates and add an explanation to each.
    Returns the reranked list with an added 'reason' field.
    """
    if not candidates:
        return []

    summaries = _build_summaries(candidates)
    prefs_text = _format_prefs(prefs)

    prompt = f"""You are a hackathon recommendation assistant.

User preferences:
{prefs_text}

Below are {len(candidates)} hackathon/event candidates (numbered). Rerank them from most to least relevant for this user. For each event return a one-line reason why it's a good or bad fit.

Events:
{summaries}

Return ONLY a JSON array in this exact format (no markdown, no explanation outside the array):
[
  {{"rank": 1, "id": "<event_id>", "reason": "one line explaining fit"}},
  ...
]

Include ALL {len(candidates)} events in your response."""

    try:
        resp = httpx.post(
            f"{ASI_ONE_BASE_URL}/chat/completions",
            json={
                "model": ASI_ONE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 3000,
                "temperature": 0,
            },
            headers={"Authorization": f"Bearer {ASI_ONE_API_KEY}"},
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        rankings = json.loads(content)
    except Exception as e:
        print(f"  [RERANK] LLM call failed: {e} — returning score order")
        for i, ev in enumerate(candidates):
            ev["reason"] = "Matched your search criteria"
            ev["rank"] = i + 1
        return candidates

    # Build lookup by id
    id_to_ev = {ev["id"]: ev for ev in candidates}

    reranked: list[dict] = []
    for item in rankings:
        ev_id = item.get("id")
        ev = id_to_ev.get(ev_id) or {}
        if ev:
            ev["reason"] = item.get("reason", "")
            ev["rank"] = item.get("rank", len(reranked) + 1)
            reranked.append(ev)

    # Append any events the LLM dropped (shouldn't happen)
    seen = {ev["id"] for ev in reranked}
    for ev in candidates:
        if ev["id"] not in seen:
            ev["reason"] = "Matched your search criteria"
            ev["rank"] = len(reranked) + 1
            reranked.append(ev)

    return reranked


def _build_summaries(candidates: list[dict]) -> str:
    lines = []
    for i, ev in enumerate(candidates, 1):
        ed = _parse_jsonb(ev.get("external_data"))
        le = _parse_jsonb(ev.get("llm_extracted"))

        title = ev.get("title", "Untitled")
        city = ev.get("city") or ed.get("location") or "Unknown location"
        start = (ev.get("start_datetime") or "")[:10]
        prize = le.get("prize_amount") or ed.get("prize_amount") or "Unknown"
        tags = ed.get("tags") or le.get("tags") or []
        tracks = ed.get("tracks") or []
        desc = ev.get("description_summary") or ed.get("description") or ""
        source = ev.get("source", "")
        online = ed.get("is_online")

        location_str = "Online" if online else city
        tags_str = ", ".join(tags[:5]) if isinstance(tags, list) else str(tags)[:60]
        tracks_str = ", ".join(tracks[:3]) if isinstance(tracks, list) else ""
        desc_str = desc[:150] if desc else ""

        line = (
            f"{i}. [{ev['id']}] {title}\n"
            f"   Date: {start} | Location: {location_str} | Prize: {prize} | Platform: {source}\n"
        )
        if tags_str:
            line += f"   Tags: {tags_str}\n"
        if tracks_str:
            line += f"   Tracks: {tracks_str}\n"
        if desc_str:
            line += f"   About: {desc_str}\n"
        lines.append(line)

    return "\n".join(lines)


def _format_prefs(prefs: dict) -> str:
    parts = []
    if prefs.get("keywords"):
        parts.append(f"- Looking for: {prefs['keywords']}")
    if prefs.get("topics"):
        parts.append(f"- Topics of interest: {', '.join(prefs['topics'])}")
    if prefs.get("location"):
        parts.append(f"- Location: {prefs['location']}")
    if prefs.get("online"):
        parts.append("- Preference: online/virtual events")
    if prefs.get("date_from") or prefs.get("date_to"):
        parts.append(
            f"- Date range: {prefs.get('date_from', '')} to {prefs.get('date_to', '')}"
        )
    if prefs.get("min_prize"):
        parts.append(f"- Minimum prize: ${prefs['min_prize']:,}")
    if prefs.get("hackathon_only"):
        parts.append("- Only hackathons (not meetups/conferences)")
    if prefs.get("team_size"):
        parts.append(f"- Team size: {prefs['team_size']}")
    return "\n".join(parts) if parts else "No specific preferences provided"
