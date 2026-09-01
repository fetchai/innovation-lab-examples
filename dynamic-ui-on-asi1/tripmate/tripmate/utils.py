"""Date helpers, IATA mapping, message parsing."""

import json
import re
from datetime import date, datetime, timedelta

from tripmate.config import CITY_IATA


def to_iata(value: str) -> str:
    val = (value or "").strip().upper()
    if len(val) == 3 and val.isalpha():
        return val
    return CITY_IATA.get(val, val)


def parse_ymd(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def normalize_future_date(value: str) -> str:
    if not value:
        return value
    d = parse_ymd(value)
    today = date.today()
    while d < today:
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:
            d = d.replace(year=d.year + 1, day=28)
    return d.isoformat()


def add_days(value: str, days: int) -> str:
    return (parse_ymd(value) + timedelta(days=days)).isoformat()


def strip_agent_mention(text: str) -> str:
    return re.sub(r"^@\S+\s*", "", (text or "").strip())


def extract_selection(text: str) -> dict:
    """Parse card selection from direct @mention JSON or planner prose."""
    text = strip_agent_mention(text)
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    selection: dict = {}
    lower = text.lower()
    for action in (
        "pick_flight",
        "pick_hotel",
        "pick_package",
        "confirm",
        "open_book",
        "approve",
        "cancel",
        "back",
        "submit_passenger",
        "more_options",
        "book_opened",
        "submit",
    ):
        if action in lower or action.replace("_", " ") in lower:
            selection["action"] = action
    for key in (
        "offer_id",
        "hotel_id",
        "package_id",
        "book_url",
        "search_id",
        "hotel_internal_id",
    ):
        m = re.search(rf'"{key}"\s*:\s*"?([^",\}}]+)"?', text, re.I)
        if m:
            selection[key] = m.group(1).strip()
    return selection


def is_card_action(selection: dict) -> bool:
    return bool(
        selection.get("action")
        or selection.get("step")
        or selection.get("offer_id")
        or selection.get("package_id")
        or selection.get("hotel_id")
    )


def needs_passenger_form(text: str) -> bool:
    """True when the user message lacks enough travel intent to search."""
    cleaned = strip_agent_mention(text).strip()
    if not cleaned:
        return False
    lower = cleaned.lower()
    if lower in {"hi", "hello", "start", "help"}:
        return False
    travel_keywords = (
        "flight",
        "hotel",
        "package",
        "trip",
        "travel",
        "book",
        "from",
        " to ",
        "→",
        "fly",
        "stay",
        "night",
        "check-in",
        "check in",
        "depart",
        "return",
        "weekend",
        "holiday",
    )
    has_travel_hint = any(k in lower for k in travel_keywords)
    has_iata = bool(re.search(r"\b[a-z]{3}\b", lower))
    has_date = bool(
        re.search(r"\d{4}-\d{2}-\d{2}", lower)
        or re.search(
            r"\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", lower
        )
    )
    if has_travel_hint or has_iata or has_date:
        return False
    if len(cleaned.split()) <= 3 and "?" not in cleaned:
        return True
    return not has_travel_hint


def parse_mcp_json(mcp_text: str) -> dict | None:
    try:
        data = json.loads(mcp_text)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def format_mcp_error(mcp_text: str) -> str:
    data = parse_mcp_json(mcp_text)
    if data and data.get("success") is False:
        return data.get("message") or data.get("error") or "Search failed."
    if "date_from must be today or later" in mcp_text:
        return "That date is in the past. Please pick a future date."
    if "validation error" in mcp_text.lower() or "value error" in mcp_text.lower():
        m = re.search(r"Value error,?\s*(.+?)(?:\"|$)", mcp_text, re.I)
        if m:
            return m.group(1).strip()
    return mcp_text[:500]


def parse_package_intent(text: str) -> tuple[str, dict] | None:
    from tripmate.mcp_args import prepare_mcp_args

    lower = strip_agent_mention(text).lower()
    if not any(
        k in lower
        for k in ("package", "flight and hotel", "flight + hotel", "flight+hotel")
    ):
        return None
    origin = destination = None
    m = re.search(
        r"from\s+([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+?)(?:\s+for|\s*,|\s+checking|\s+check|$)",
        lower,
    )
    if m:
        origin, destination = m.group(1).strip().title(), m.group(2).strip().title()
    nights = 3
    nm = re.search(r"(\d+)\s*nights?", lower)
    if nm:
        nights = int(nm.group(1))
    date_from = None
    dm = re.search(
        r"(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:\s+(\d{4}))?",
        lower,
    )
    if dm:
        months = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        day, mon, yr = int(dm.group(1)), months[dm.group(2)], dm.group(3)
        year = int(yr) if yr else date.today().year
        date_from = normalize_future_date(date(year, mon, day).isoformat())
    if not (origin and destination and date_from):
        return None
    return "search_flight_and_hotel_package", prepare_mcp_args(
        "search_flight_and_hotel_package",
        {
            "origin": origin,
            "destination": destination,
            "date_from": date_from,
            "nights": nights,
            "adults": "2",
            "lang": "en",
        },
    )
