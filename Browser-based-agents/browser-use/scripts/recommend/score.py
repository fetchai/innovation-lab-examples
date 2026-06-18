"""
Layer 2 — Soft scoring.

Scores each candidate on multiple weighted signals and returns
the top N sorted by score descending.
"""

import re
import json
from datetime import datetime, timezone


# Weight config — tune these to change ranking behaviour
WEIGHTS = {
    "prize":          0.30,
    "upcoming":       0.25,
    "keyword_match":  0.20,
    "data_quality":   0.15,
    "featured":       0.10,
}

TOP_N = 30  # how many to pass to the LLM reranker


def score_and_rank(candidates: list[dict], prefs: dict) -> list[dict]:
    """Score all candidates and return top TOP_N sorted by score."""
    keywords = [k.strip().lower() for k in re.split(r"[\s,]+", prefs.get("keywords", "")) if k.strip()]
    topics   = [t.strip().lower() for t in prefs.get("topics", [])]
    all_terms = list(set(keywords + topics))

    scored = []
    for ev in candidates:
        score = _compute_score(ev, all_terms, prefs)
        ev["_score"] = round(score, 4)
        scored.append(ev)

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:TOP_N]


# ── Individual signal scorers ──────────────────────────────────────────────

def _compute_score(ev: dict, terms: list[str], prefs: dict) -> float:
    total = 0.0
    total += WEIGHTS["prize"]        * _prize_score(ev, prefs.get("min_prize", 0))
    total += WEIGHTS["upcoming"]     * _upcoming_score(ev)
    total += WEIGHTS["keyword_match"] * _keyword_score(ev, terms)
    total += WEIGHTS["data_quality"] * _data_quality_score(ev)
    total += WEIGHTS["featured"]     * _featured_score(ev)
    return total


def _prize_score(ev: dict, min_prize: int = 0) -> float:
    """Normalised prize score 0-1. $50k+ = 1.0, $0 = 0.0."""
    amount = _extract_prize(ev)
    if amount is None:
        return 0.1  # small bump for events with unknown prize (may still have one)
    if min_prize and amount < min_prize:
        return 0.0
    # Normalise: $50,000 → 1.0
    return min(amount / 50_000, 1.0)


def _upcoming_score(ev: dict) -> float:
    """Events starting sooner score higher. >180 days away → 0."""
    start = ev.get("start_datetime")
    if not start:
        return 0.0
    try:
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        days = (start - now).days
        if days < 0:
            return 0.0
        if days > 180:
            return 0.0
        return 1.0 - (days / 180)
    except Exception:
        return 0.0


def _keyword_score(ev: dict, terms: list[str]) -> float:
    """Count how many search terms appear across text fields."""
    if not terms:
        return 0.5  # neutral when no keywords given

    text_fields = [
        ev.get("title", "") or "",
        ev.get("description_summary", "") or "",
    ]
    ed = _parse_jsonb(ev.get("external_data"))
    le = _parse_jsonb(ev.get("llm_extracted"))
    text_fields += [
        ed.get("description", "") or "",
        ed.get("title", "") or "",
        str(ed.get("tags", "") or ""),
        str(ed.get("tracks", "") or ""),
        str(le.get("tags", "") or ""),
        str(le.get("prize_amount", "") or ""),
    ]

    combined = " ".join(text_fields).lower()
    hits = sum(1 for t in terms if t in combined)
    return min(hits / len(terms), 1.0)


def _data_quality_score(ev: dict) -> float:
    """Score based on how much data we have for this event."""
    score = 0.0
    if ev.get("description_summary"):
        score += 0.4
    if ev.get("external_data") and ev["external_data"] not in (None, "null"):
        ed = _parse_jsonb(ev["external_data"])
        if ed.get("description"):
            score += 0.3
        if ed.get("prize_amount"):
            score += 0.2
        if ed.get("tracks") or ed.get("tags"):
            score += 0.1
    return min(score, 1.0)


def _featured_score(ev: dict) -> float:
    """Boost featured/CV-verified events."""
    if ev.get("status") == "featured":
        return 1.0
    if ev.get("cv_event"):
        return 0.5
    if ev.get("source") in ("cerebralvalley", "ethglobal"):
        return 0.3
    return 0.0


# ── Helpers ────────────────────────────────────────────────────────────────

def _extract_prize(ev: dict) -> int | None:
    """Parse prize amount from various fields into an integer USD value."""
    candidates = []

    le = _parse_jsonb(ev.get("llm_extracted"))
    ed = _parse_jsonb(ev.get("external_data"))

    for src in [le.get("prize_amount"), ed.get("prize_amount")]:
        if src:
            candidates.append(str(src))

    for raw in candidates:
        amount = _parse_prize_string(raw)
        if amount is not None:
            return amount

    return None


def _parse_prize_string(s: str) -> int | None:
    """Convert "$10,000+" or "€5k" or "25000" to an integer."""
    if not s:
        return None
    s = s.replace(",", "").replace("+", "").strip()
    # Handle k/K suffix
    m = re.search(r"[\$€£]?\s*(\d+(?:\.\d+)?)\s*[kK]", s)
    if m:
        return int(float(m.group(1)) * 1000)
    # Handle plain number with optional currency
    m = re.search(r"[\$€£]?\s*(\d+(?:\.\d+)?)", s)
    if m:
        return int(float(m.group(1)))
    return None


def _parse_jsonb(val) -> dict:
    if not val:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}
