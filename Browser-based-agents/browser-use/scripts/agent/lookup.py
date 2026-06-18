"""
Direct event lookup by name/slug for the "lookup" intent.
Searches title with ILIKE and returns the best match.
"""

import re
import sys
import os
import json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db import get_client

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def lookup_event(event_name: str) -> dict | None:
    """
    Find the closest matching event by name.
    Tries progressively broader patterns and scores matches by
    how many words from the query appear in the title.
    """
    client = get_client()
    words = [w for w in event_name.lower().split() if len(w) >= 3
             and w not in ("the", "and", "for", "with", "about")]

    candidates = []
    _select = ("id, slug, title, city, start_datetime, source, "
               "description_summary, external_url, event_url, "
               "registration_closed, approval_required, "
               "end_datetime, timezone, venue, "
               "is_platform_hackathon, llm_extracted, external_data, "
               "hosts, questions")

    # 1. Try slug search first (handles acronyms like AIEWF → aiewf-hackathon-2026)
    slug_term = re.sub(r"[^a-z0-9]+", "-", event_name.lower()).strip("-")
    for slug_word in slug_term.split("-"):
        if len(slug_word) < 3:
            continue
        try:
            rows = (
                client.table("events")
                .select(_select)
                .ilike("slug", f"%{slug_word}%")
                .order("start_datetime", desc=False)
                .limit(10)
                .execute()
                .data or []
            )
            candidates.extend(rows)
        except Exception:
            pass

    # 2. Try each significant word against title
    for word in words:
        try:
            rows = (
                client.table("events")
                .select(_select)
                .ilike("title", f"%{word}%")
                .order("start_datetime", desc=False)
                .limit(20)
                .execute()
                .data or []
            )
            candidates.extend(rows)
        except Exception as e:
            print(f"  [LOOKUP] error: {e}")

    if not candidates:
        return None

    # Deduplicate by id and score by word overlap
    seen = {}
    for ev in candidates:
        eid = ev["id"]
        if eid not in seen:
            title_lower = (ev.get("title") or "").lower()
            score = sum(1 for w in words if w in title_lower)
            ev["_match_score"] = score
            seen[eid] = ev
        else:
            # Update score if higher
            title_lower = (seen[eid].get("title") or "").lower()
            score = sum(1 for w in words if w in title_lower)
            seen[eid]["_match_score"] = max(seen[eid].get("_match_score", 0), score)

    # Sort: first by word match score, then prefer platform events and future dates
    def sort_key(ev):
        score = ev.get("_match_score", 0)
        is_platform = 1 if ev.get("is_platform_hackathon") else 0
        start = ev.get("start_datetime") or ""
        is_future = 1 if start >= TODAY else 0
        return (score, is_platform, is_future)

    ranked = sorted(seen.values(), key=sort_key, reverse=True)
    return ranked[0] if ranked else None


def format_event_detail(ev: dict) -> str:
    """Format a single event's full details as readable text."""
    if not ev:
        return "Event not found."

    def jparse(val):
        if not val:
            return {}
        if isinstance(val, dict):
            return val
        try:
            return json.loads(val)
        except Exception:
            return {}

    ed = jparse(ev.get("external_data"))
    le = jparse(ev.get("llm_extracted"))
    qs = jparse(ev.get("questions")) if ev.get("questions") else []

    lines = [f"**{ev.get('title', 'Unknown')}**\n"]

    start = (ev.get("start_datetime") or "")[:16].replace("T", " ")
    end   = (ev.get("end_datetime") or "")[:16].replace("T", " ")
    tz    = ev.get("timezone") or ""
    if start:
        lines.append(f"📅 Date: {start} → {end} {tz}".strip())

    city = ev.get("city") or ed.get("location") or ""
    venue = ev.get("venue") or ed.get("venue") or ""
    if city:
        lines.append(f"📍 Location: {city}" + (f", {venue}" if venue else ""))

    prize = le.get("prize_amount") or ed.get("prize_amount") or ""
    if prize:
        lines.append(f"🏆 Prize: {prize}")

    reg_closed = ev.get("registration_closed")
    approval   = ev.get("approval_required")
    if reg_closed is False:
        status = "Open"
        if approval:
            status += " (approval required)"
        lines.append(f"✅ Registration: {status}")
    elif reg_closed is True:
        lines.append("❌ Registration: Closed")

    desc = ev.get("description_summary") or ed.get("description") or ev.get("description") or ""
    if desc:
        lines.append(f"\n📝 About: {desc[:400]}")

    tags   = ed.get("tags") or le.get("tags") or []
    tracks = ed.get("tracks") or []
    if tracks:
        t = tracks if isinstance(tracks, list) else [tracks]
        lines.append(f"🎯 Tracks: {', '.join(str(x) for x in t[:5])}")
    if tags:
        t = tags if isinstance(tags, list) else [tags]
        lines.append(f"🏷  Tags: {', '.join(str(x) for x in t[:8])}")

    sponsors = ed.get("sponsors") or []
    if sponsors and isinstance(sponsors, list) and sponsors:
        lines.append(f"🤝 Sponsors: {', '.join(str(s) for s in sponsors[:5])}")

    schedule = ed.get("schedule") or []
    if schedule and isinstance(schedule, list):
        lines.append("\n🗓 Schedule:")
        for item in schedule[:5]:
            if isinstance(item, dict):
                t = item.get("time") or ""
                a = item.get("activity") or ""
                if a:
                    lines.append(f"   {t} {a}".strip())

    if qs and isinstance(qs, list):
        lines.append("\n📋 Registration questions:")
        for q in qs[:5]:
            if isinstance(q, dict):
                req = " (required)" if q.get("required") else ""
                lines.append(f"   • {q.get('question','')}{req}")

    url = ev.get("external_url") or ev.get("event_url") or ""
    if url:
        lines.append(f"\n🔗 {url}")

    source = ev.get("source") or ""
    if source:
        lines.append(f"   Source: {source}")

    return "\n".join(lines)
