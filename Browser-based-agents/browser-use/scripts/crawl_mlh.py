"""
MLH (Major League Hacking) crawler.

The season listing at https://www.mlh.com/seasons/2026/events renders all
events as external links. Each link's text contains the full event info:
  name, dates, location, format (In-Person/Digital), and tags (DIVERSITY, HIGH SCHOOL).

Events on events.mlh.io have their own detail pages we also crawl.
External hackathon sites are stored as external_url for future registration support.

Usage:
    from crawl_mlh import fetch_all_events
    events = fetch_all_events()
"""

import re
import httpx
from datetime import datetime, timezone

from config import CRAWL4AI_BASE

SEASON_URLS = [
    "https://www.mlh.com/seasons/2027/events",
    "https://www.mlh.com/seasons/2026/events",
    "https://www.mlh.com/seasons/2025/events",
]

SCROLL_JS = """
    for (let i = 0; i < 15; i++) {
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 600));
    }
"""

MONTH_ABBRS = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]
MONTH_MAP = {m: i + 1 for i, m in enumerate(MONTH_ABBRS)}

# Regex to find date range in link text e.g. "JUN 12 - 18" or "FEB 28 - MAR 01"
DATE_RE = re.compile(
    r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})\s*[-–]\s*(?:(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+)?(\d{1,2})"
)


def fetch_all_events() -> list[dict]:
    """Fetch all MLH events across configured seasons."""
    all_events: list[dict] = []
    seen: set[str] = set()

    for season_url in SEASON_URLS:
        year_match = re.search(r"/seasons/(\d{4})/", season_url)
        year = int(year_match.group(1)) if year_match else 0
        print(f"[MLH] Fetching {season_url}")

        result = _fetch_result(season_url)
        if not result:
            continue

        external_links = result.get("links", {}).get("external", [])
        print(f"[MLH] Found {len(external_links)} external links on {season_url}")

        for link in external_links:
            href = link.get("href", "")
            text = link.get("text", "").strip()

            # Skip nav/sponsor links (no date found in text)
            if not DATE_RE.search(text):
                continue

            event = _parse_event(href, text, year)
            if not event:
                continue

            slug = event["slug"]
            if slug in seen:
                continue
            seen.add(slug)
            all_events.append(event)

        print(f"[MLH] Parsed {len(all_events)} events so far")

    # For events hosted on events.mlh.io, crawl detail pages for extra info
    mlh_hosted = [e for e in all_events if "events.mlh.io" in e.get("external_url", "")]
    print(f"[MLH] Crawling {len(mlh_hosted)} events.mlh.io detail pages...")
    for ev in mlh_hosted:
        detail = _fetch_mlh_detail(ev["external_url"])
        if detail:
            ev["description"] = detail.get("description") or ev.get("description")
            ev["description_summary"] = detail.get("description_summary") or ev.get(
                "description_summary"
            )
            if detail.get("llm_data"):
                ev["llm_extracted"] = {
                    **(ev.get("llm_extracted") or {}),
                    **detail["llm_data"],
                }

    print(f"[MLH] Done. Total unique events: {len(all_events)}")
    return all_events


def _parse_event(href: str, text: str, year: int) -> dict | None:
    """Parse a single MLH event from its link href and link text."""
    m = DATE_RE.search(text)
    if not m:
        return None

    start_month_str, start_day, end_month_str, end_day = m.groups()
    date_str = m.group(0)

    # Split text around the date to get name and location
    before = text[: m.start()].strip()
    after = text[m.end() :].strip()

    # Determine event name and location from context
    # Format 1 (digital): "Event NameDATE_RANGELocation, WorldwideDigital"
    # Format 2 (in-person): "City, StateEvent NameDATE_RANGECity, State, COUNTRYIn-Person[TAGS]"
    is_online = "Digital" in after or "Worldwide" in after
    is_in_person = "In-Person" in after

    # Extract tags
    tags = []
    if "DIVERSITY" in after:
        tags.append("diversity")
    if "HIGH SCHOOL" in after:
        tags.append("high-school")

    # Clean up location from after-date text
    location_raw = (
        re.sub(r"(Digital|In-Person|DIVERSITY|HIGH SCHOOL)", "", after)
        .strip()
        .rstrip(",")
        .strip()
    )
    # Remove the country suffix pattern like ", US" or ", CA" at end
    city = re.sub(r",\s*[A-Z]{2}\s*$", "", location_raw).strip()

    # Determine the event name.
    # For in-person events the link text starts with "City, StateEvent Name",
    # so we strip the city prefix from `before` if it matches the parsed city.
    name = before.strip()
    if is_in_person and city and name.startswith(city):
        name = name[len(city) :].strip()
    # Also strip bare "City, State" prefix patterns (comma-separated location at start)
    if is_in_person and not name:
        name = before.strip()

    if not name:
        name = href.rstrip("/").split("/")[-1].replace("-", " ").title()

    # Build dates
    start_month = MONTH_MAP.get(start_month_str, 1)
    end_month = MONTH_MAP.get(end_month_str or start_month_str, start_month)
    start_dt: str | None
    end_dt: str | None
    try:
        start_dt = datetime(year, start_month, int(start_day)).isoformat()
        end_dt = datetime(year, end_month, int(end_day)).isoformat()
        # Handle year boundary (e.g. DEC → JAN)
        if end_month < start_month:
            end_dt = datetime(year + 1, end_month, int(end_day)).isoformat()
    except ValueError:
        start_dt = end_dt = None

    slug = _make_slug(name, href)

    return {
        "id": f"mlh:{slug}",
        "source": "mlh",
        "slug": slug,
        "event_url": href if "mlh" in href else None,
        "external_url": href,
        "external_source": _detect_source(href),
        "title": name,
        "description": None,
        "description_summary": None,
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "city": city or None,
        "is_platform_hackathon": None,
        "llm_extracted": {
            "is_online": is_online,
            "is_in_person": is_in_person,
            "tags": tags,
            "date_text": date_str,
            "mlh_season": str(year),
        },
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_mlh_detail(url: str) -> dict | None:
    """Fetch an events.mlh.io detail page and extract description."""
    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json={"urls": [url], "crawler_config": {"delay_before_return_html": 3}},
            timeout=60,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        md = results[0].get("markdown", {})
        raw_md = md.get("raw_markdown", "") if isinstance(md, dict) else ""
        html = results[0].get("html", "")

        # Extract description from markdown or text
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

        # Find the main description block (usually after event title and date)
        desc_match = re.search(
            r"About\s+(?:the\s+)?[Ee]vent(.{100,1500}?)(?:Schedule|Judges|Sponsors|FAQ|$)",
            text,
            re.DOTALL,
        )
        description = desc_match.group(1).strip() if desc_match else None

        if not description and raw_md:
            description = raw_md[:1000]

        return {
            "description": description,
            "description_summary": description[:300] if description else None,
            "llm_data": {},
        }
    except Exception as e:
        print(f"  [MLH] detail fetch failed for {url}: {e}")
        return None


def _fetch_result(url: str) -> dict | None:
    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json={
                "urls": [url],
                "crawler_config": {
                    "delay_before_return_html": 8,
                    "js_code": SCROLL_JS,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  [MLH] fetch error for {url}: {e}")
        return None


def _make_slug(name: str, href: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:70]
    if slug:
        return f"mlh-{slug}"
    path = href.rstrip("/").split("/")[-1]
    return f"mlh-{path}" if path else "mlh-unknown"


def _detect_source(url: str) -> str:
    if (
        "events.mlh.io" in url
        or "organize.mlh.io" in url
        or "mlh.io" in url
        or "mlh.com" in url
    ):
        return "mlh"
    return "external"
