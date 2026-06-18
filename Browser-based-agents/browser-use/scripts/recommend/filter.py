"""
Layer 1 — Hard filters.

Queries Supabase with the user's hard constraints and returns a list of
candidate event dicts. Designed to be robust to sparse/missing fields.
"""

import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import get_client
from datetime import datetime, timezone


MAX_CANDIDATES = 200  # max rows to pull before scoring


def fetch_candidates(prefs: dict) -> list[dict]:
    """
    Apply hard filters from prefs and return candidate events.

    prefs keys (all optional):
        keywords    : str  — free text (searched across title + description)
        location    : str  — city/country substring, or "online"
        online      : bool — if True, only online events
        date_from   : str  — ISO date "2026-07-01"
        date_to     : str  — ISO date "2026-08-31"
        sources     : list[str] — restrict to these platforms
        hackathon_only : bool — only hackathons (not meetups/conferences)
        registration_open : bool — only events with open registration
        min_prize   : int  — minimum prize in USD (best effort)
    """
    client = get_client()

    q = (
        client.table("events")
        .select(
            "id, slug, source, title, description_summary, city, venue, "
            "start_datetime, end_datetime, timezone, "
            "registration_closed, approval_required, is_platform_hackathon, "
            "event_type, status, cv_event, "
            "external_url, external_source, image_url, "
            "llm_extracted, external_data"
        )
    )

    # ── Date filters ──────────────────────────────────────────────
    date_from = prefs.get("date_from")
    date_to = prefs.get("date_to")

    if not date_from:
        # Default: from today
        date_from = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    q = q.gte("start_datetime", date_from)

    if date_to:
        q = q.lte("start_datetime", date_to)

    # ── Source filter ─────────────────────────────────────────────
    sources = prefs.get("sources")
    if sources:
        q = q.in_("source", sources)

    keywords_raw = prefs.get("keywords", "").strip()
    topics = prefs.get("topics", [])
    all_kw = [k for k in re.split(r"[\s,]+", keywords_raw) if len(k) >= 2]
    all_kw += [t for t in topics if len(t) >= 2]

    location = (prefs.get("location") or "").strip().lower()
    online = prefs.get("online") or False
    reg_open = prefs.get("registration_open") or False

    # ── Single OR block — supabase-py ANDs multiple .or_() calls, so we
    #    must fit everything into one. We use nested OR groups via the
    #    PostgREST `or(...)` filter which supports parenthesised groups.
    # ── Group A: keyword/online signal (at least one must match) ──────────
    group_a = []
    if all_kw:
        kw = f"%{all_kw[0]}%"
        group_a += [f"title.ilike.{kw}", f"description_summary.ilike.{kw}"]
    if online:
        group_a += [
            "city.ilike.%worldwide%", "city.ilike.%online%",
            "city.ilike.%digital%",   "city.ilike.%everywhere%",
            "city.ilike.%remote%",
        ]
    if group_a:
        q = q.or_(",".join(group_a))

    # ── Registration: handled post-fetch to avoid AND conflict ────────────
    # (stored separately in prefs, applied below)

    # Order by soonest first, cap results
    q = q.order("start_datetime", desc=False).limit(MAX_CANDIDATES)

    try:
        rows = q.execute().data or []
    except Exception as e:
        print(f"  [FILTER] query failed: {e}")
        return []

    # ── Post-fetch filters (things supabase-py can't do in one query) ──
    results = []
    for row in rows:
        # Location filter
        if online:
            city = (row.get("city") or "").lower()
            ed = row.get("external_data") or {}
            if isinstance(ed, str):
                import json
                try:
                    ed = json.loads(ed)
                except Exception:
                    ed = {}
            is_online = ed.get("is_online") or "worldwide" in city or "online" in city or "digital" in city or "everywhere" in city
            if not is_online:
                continue
        elif location and location != "online":
            city = (row.get("city") or "").lower()
            title = (row.get("title") or "").lower()
            ed = row.get("external_data") or {}
            if isinstance(ed, str):
                import json
                try:
                    ed = json.loads(ed)
                except Exception:
                    ed = {}
            ext_loc = (ed.get("location") or "").lower()
            if location not in city and location not in title and location not in ext_loc:
                continue

        # Registration open (NULL = unknown = treat as possibly open)
        if reg_open:
            if row.get("registration_closed") is True:
                continue

        # Hackathon-only filter
        if prefs.get("hackathon_only"):
            title_lower = (row.get("title") or "").lower()
            source = row.get("source", "")
            is_hackathon = (
                row.get("is_platform_hackathon") is True
                or source in ("devpost", "devfolio", "dorahacks", "ethglobal", "lablab")
                or "hackathon" in title_lower
                or "hack" in title_lower
            )
            if not is_hackathon:
                continue

        results.append(row)

    return results
