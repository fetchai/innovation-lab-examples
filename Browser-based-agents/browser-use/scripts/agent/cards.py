"""
Card builder — fills ui_cards.json templates with real event data.

All card structures come from ui_cards.json so the UI can be changed
without touching this file.
"""

import json
import copy
import os
from pathlib import Path
from datetime import datetime

# Load templates from ui_cards.json (sibling to scripts/)
_CARDS_PATH = Path(__file__).parent.parent.parent / "ui_cards.json"
with open(_CARDS_PATH) as f:
    _TEMPLATES = json.load(f)


def welcome_card() -> dict:
    return copy.deepcopy(_TEMPLATES["welcome"])


def event_list_card(events: list[dict], subtitle: str = "") -> dict:
    """Build a list card from a list of scored/ranked event dicts."""
    card = copy.deepcopy(_TEMPLATES["event_list"])
    card["root"]["subtitle"] = subtitle or f"{len(events)} events found"

    items = [_build_event_item(ev) for ev in events[:5]]  # cap at 5 in list
    card["root"]["children"][0]["items"] = items
    return card


def event_detail_card(ev: dict) -> dict:
    """Build a full detail card for a single event."""
    card = copy.deepcopy(_TEMPLATES["event_detail"])
    root = card["root"]

    ed = _parse_jsonb(ev.get("external_data"))
    le = _parse_jsonb(ev.get("llm_extracted"))
    qs = _parse_jsonb(ev.get("questions")) if ev.get("questions") else []

    title      = ev.get("title", "Untitled")
    slug       = ev.get("slug", "")
    url        = ev.get("external_url") or ev.get("event_url") or ""
    source     = ev.get("source", "")
    prize      = le.get("prize_amount") or ed.get("prize_amount") or "—"
    desc       = ev.get("description_summary") or ed.get("description") or ""
    city       = ev.get("city") or ed.get("location") or "—"
    venue      = ev.get("venue") or ed.get("venue") or ""
    location   = f"{venue}, {city}" if venue else city
    reg_closed = ev.get("registration_closed")
    status     = "Closed" if reg_closed else "Open"
    capacity   = ed.get("capacity") or ev.get("capacity") or "—"
    team_size  = ed.get("team_size") or le.get("team_size") or "—"
    org        = ed.get("organization_name") or le.get("organizer") or "—"
    reg_count  = ed.get("registrations_count") or "—"

    start = _fmt_date(ev.get("start_datetime"))
    end   = _fmt_date(ev.get("end_datetime"))
    date_range = f"{start} → {end}" if end and end != start else start

    # Questions text
    q_lines = []
    if isinstance(qs, list):
        for q in qs[:10]:
            req = " *" if q.get("required") else ""
            q_lines.append(f"• {q.get('question','')}{req}")
    q_text = "\n".join(q_lines) if q_lines else "No custom questions"

    # Badges
    badges = _build_badges(ev, ed, le)

    _fill(root, {
        "_TITLE_":       title,
        "_PLATFORM_":    source.capitalize() or "—",
        "_STATUS_":      status,
        "_DATE_RANGE_":  date_range or "—",
        "_LOCATION_":    location,
        "_PRIZE_":       prize,
        "_CAPACITY_":    str(capacity),
        "_TEAM_SIZE_":   str(team_size),
        "_ORGANIZER_":   str(org),
        "_REG_COUNT_":   str(reg_count),
        "_DESCRIPTION_": desc[:500] + ("…" if len(desc) > 500 else "") if desc else "No description available.",
        "_QUESTIONS_":   q_text,
        "_SLUG_":        slug,
        "_URL_":         url,
    })

    # Replace badge placeholder
    _replace_badges(root, badges)
    return card


def registration_confirm_card(ev: dict, answers: dict) -> dict:
    """Build a registration confirmation card showing pre-generated answers."""
    card = copy.deepcopy(_TEMPLATES["registration_confirm"])
    root = card["root"]

    slug  = ev.get("slug", "")
    title = ev.get("title", "")

    answers_preview = "\n".join(
        f"• {q[:50]}: {a[:60]}"
        for q, a in list(answers.items())[:5]
    )

    _fill(root, {
        "_TITLE_":           title,
        "_ANSWERS_PREVIEW_": answers_preview or "Profile fields will be filled automatically.",
        "_SLUG_":            slug,
    })
    return card


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_event_item(ev: dict) -> dict:
    """Fill in one event_item template."""
    item = copy.deepcopy(_TEMPLATES["event_item"])

    ed = _parse_jsonb(ev.get("external_data"))
    le = _parse_jsonb(ev.get("llm_extracted"))

    title  = ev.get("title", "Untitled")
    slug   = ev.get("slug", "")
    url    = ev.get("external_url") or ev.get("event_url") or ""
    reason = ev.get("reason", "Matches your search criteria")
    city   = ev.get("city") or ed.get("location") or "Unknown"
    prize  = le.get("prize_amount") or ed.get("prize_amount") or "—"
    start  = _fmt_date(ev.get("start_datetime"))
    badges = _build_badges(ev, ed, le)

    _fill(item, {
        "_TITLE_":    title,
        "_REASON_":   reason[:100],
        "_DATE_":     start,
        "_LOCATION_": city[:30],
        "_PRIZE_":    prize,
        "_SLUG_":     slug,
        "_URL_":      url,
    })

    _replace_badges(item, badges)
    return item


def _build_badges(ev: dict, ed: dict, le: dict) -> list[dict]:
    """Build badge list from event tags, source, and online status."""
    badges = []

    # Source platform
    source = ev.get("source", "")
    if source:
        badges.append({"type": "badge", "label": source.capitalize(), "variant": "info"})

    # Online/In-person
    is_online = ed.get("is_online")
    city = (ev.get("city") or "").lower()
    if is_online or any(w in city for w in ["worldwide", "online", "remote", "everywhere"]):
        badges.append({"type": "badge", "label": "Online", "variant": "success"})
    elif city:
        badges.append({"type": "badge", "label": "In-Person", "variant": "warning"})

    # Registration status
    if ev.get("registration_closed") is False:
        badges.append({"type": "badge", "label": "Open", "variant": "success"})
    elif ev.get("registration_closed") is True:
        badges.append({"type": "badge", "label": "Closed", "variant": "error"})

    # Tags (up to 3)
    tags = ed.get("tags") or le.get("tags") or []
    if isinstance(tags, list):
        for tag in tags[:3]:
            if isinstance(tag, str):
                badges.append({"type": "badge", "label": tag[:20], "variant": "info"})

    # Tracks (up to 2)
    tracks = ed.get("tracks") or []
    if isinstance(tracks, list):
        for track in tracks[:2]:
            if isinstance(track, str):
                badges.append({"type": "badge", "label": track[:20], "variant": "info"})

    return badges[:8]  # cap total badges


def _fill(obj, replacements: dict) -> None:
    """Recursively replace string placeholders in a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                for placeholder, value in replacements.items():
                    v = v.replace(placeholder, str(value))
                obj[k] = v
            else:
                _fill(v, replacements)
    elif isinstance(obj, list):
        for item in obj:
            _fill(item, replacements)


def _replace_badges(obj, badges: list[dict]) -> None:
    """Replace the string placeholder '_BADGES_' in children arrays with actual badge dicts."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v == "_BADGES_":
                obj[k] = badges
            else:
                _replace_badges(v, badges)
    elif isinstance(obj, list):
        for item in obj:
            _replace_badges(item, badges)


def _fmt_date(dt_str: str | None) -> str:
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(dt_str)[:10]


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
