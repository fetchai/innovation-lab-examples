"""
Recommendation engine — main entry point.

Orchestrates the three layers:
  1. filter.py  — hard SQL filters → up to 200 candidates
  2. score.py   — soft scoring → top 30
  3. rerank.py  — ASI:One LLM reranking → final ranked list

Usage:
    from recommend.engine import recommend

    results = recommend({
        "keywords": "AI agents hackathon",
        "location": "San Francisco",
        "date_from": "2026-07-01",
        "date_to":   "2026-09-01",
        "hackathon_only": True,
        "registration_open": True,
        "min_prize": 5000,
    })

    for ev in results:
        print(ev["rank"], ev["title"], ev["reason"])
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from recommend.filter import fetch_candidates
from recommend.score  import score_and_rank, _parse_jsonb, _extract_prize
from recommend.rerank import rerank


def recommend(prefs: dict, skip_rerank: bool = False) -> list[dict]:
    """
    Return recommended events for the given preference dict.

    Args:
        prefs       : user preference dict (see filter.py for keys)
        skip_rerank : if True, skip LLM reranking and return score order
                      (faster, useful for testing)

    Returns list of event dicts, each with added fields:
        _score  : float 0-1 composite score
        rank    : int  final rank (1 = best)
        reason  : str  one-line LLM explanation (or score-based fallback)
    """
    print(f"\n[RECOMMEND] Fetching candidates...")
    candidates = fetch_candidates(prefs)
    print(f"[RECOMMEND] {len(candidates)} candidates after hard filters")

    if not candidates:
        return []

    print(f"[RECOMMEND] Scoring and selecting top candidates...")
    top = score_and_rank(candidates, prefs)
    print(f"[RECOMMEND] Top {len(top)} selected for reranking")

    if skip_rerank:
        for i, ev in enumerate(top):
            ev["rank"] = i + 1
            ev["reason"] = _build_fallback_reason(ev)
        return top

    print(f"[RECOMMEND] Reranking with ASI:One...")
    ranked = rerank(top, prefs)
    print(f"[RECOMMEND] Done. {len(ranked)} results returned\n")
    return ranked


def format_results(results: list[dict], max_show: int = 10) -> str:
    """Pretty-print results for CLI or agent output."""
    if not results:
        return "No events found matching your criteria."

    lines = [f"Found {len(results)} events:\n"]
    for ev in results[:max_show]:
        ed = _parse_jsonb(ev.get("external_data"))
        le = _parse_jsonb(ev.get("llm_extracted"))

        title  = ev.get("title", "Untitled")
        start  = (ev.get("start_datetime") or "")[:10]
        city   = ev.get("city") or ed.get("location") or "?"
        prize  = le.get("prize_amount") or ed.get("prize_amount") or ""
        url    = ev.get("external_url") or ev.get("event_url") or ""
        reason = ev.get("reason", "")
        rank   = ev.get("rank", "?")
        source = ev.get("source", "")

        prize_str = f" | Prize: {prize}" if prize else ""
        lines.append(
            f"#{rank}. {title}\n"
            f"    {start} | {city} | {source}{prize_str}\n"
            f"    {reason}\n"
            f"    {url}\n"
        )

    if len(results) > max_show:
        lines.append(f"... and {len(results) - max_show} more")

    return "\n".join(lines)


def _build_fallback_reason(ev: dict) -> str:
    ed = _parse_jsonb(ev.get("external_data"))
    le = _parse_jsonb(ev.get("llm_extracted"))
    parts = []
    prize = le.get("prize_amount") or ed.get("prize_amount")
    if prize:
        parts.append(f"Prize: {prize}")
    if ev.get("city"):
        parts.append(f"Location: {ev['city']}")
    if ev.get("registration_closed") is False:
        parts.append("Registration open")
    return " | ".join(parts) if parts else "Matched your search criteria"
