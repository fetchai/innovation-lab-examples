"""
Devpost hackathon crawler — uses the public JSON API.

Endpoint: https://devpost.com/api/hackathons
Pagination: ?page=1&per_page=25 (max per_page appears to be 25)
Total: 13,469+ hackathons

API response shape:
{
  "hackathons": [...],
  "meta": {"total_count": 13469, "current_page": 1, "total_pages": 539}
}

Each hackathon object contains:
  id, title, url, submission_gallery_url, start_time, end_time,
  time_left_to_submission, displayed_location, open_state,
  eligibility_requirement_to_join_count, prize_amount,
  registrations_count, themes, submission_count, featured,
  organization_name, winners_announced, submission_period_dates
"""

import re
import httpx
from datetime import datetime, timezone

SOURCE = "devpost"
API_URL = "https://devpost.com/api/hackathons"
PER_PAGE = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HackathonCrawler/1.0)",
    "Accept": "application/json",
}


def fetch_all_events() -> list[dict]:
    """Paginate through the full Devpost hackathon catalogue."""
    all_events: list[dict] = []
    page = 1
    total_pages = None

    print(f"[DEVPOST] Fetching hackathons from Devpost API...")

    while True:
        batch, meta = _fetch_page(page)
        if not batch:
            break

        if total_pages is None:
            total_pages = meta.get("total_pages", "?")
            total_count = meta.get("total_count", "?")
            print(f"[DEVPOST] Total: {total_count} hackathons across {total_pages} pages")

        for raw in batch:
            all_events.append(_normalise(raw))

        print(f"[DEVPOST] page={page}/{total_pages} → {len(batch)} events (total: {len(all_events)})")

        if total_pages and page >= total_pages:
            break
        if len(batch) < PER_PAGE:
            break
        page += 1

    print(f"[DEVPOST] Done. Total events fetched: {len(all_events)}")
    return all_events


def _fetch_page(page: int) -> tuple[list[dict], dict]:
    try:
        resp = httpx.get(
            API_URL,
            params={"page": page, "per_page": PER_PAGE},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("hackathons", []), data.get("meta", {})
    except Exception as e:
        print(f"  [DEVPOST] fetch error at page={page}: {e}")
        return [], {}


def _normalise(raw: dict) -> dict:
    """Map a Devpost hackathon object to the DB schema."""
    devpost_url = raw.get("url", "")
    slug = _derive_slug(raw)

    # Themes → tags
    themes = raw.get("themes") or []
    tags = [t.get("name") for t in themes if t.get("name")]

    # Location
    location = raw.get("displayed_location", {}) or {}
    city = location.get("location") if isinstance(location, dict) else str(location)

    # Prize
    prize_raw = raw.get("prize_amount", "")
    prize = str(prize_raw).strip() if prize_raw else None

    return {
        "id": f"devpost:{raw.get('id', slug)}",
        "source": SOURCE,
        "slug": slug,
        "event_url": devpost_url,
        "external_url": devpost_url,
        "external_source": SOURCE,
        "title": raw.get("title"),
        "description": None,           # not in listing API — fetched on detail crawl
        "description_summary": None,
        "start_datetime": raw.get("start_time"),
        "end_datetime": raw.get("end_time"),
        "city": city,
        "status": raw.get("open_state"),
        "cv_event": False,
        "image_url": raw.get("thumbnail_url"),
        "llm_extracted": {
            "prize_amount": prize,
            "registrations_count": raw.get("registrations_count"),
            "submission_count": raw.get("submission_count"),
            "winners_announced": raw.get("winners_announced"),
            "featured": raw.get("featured"),
            "organization_name": raw.get("organization_name"),
            "submission_period_dates": raw.get("submission_period_dates"),
            "eligibility_requirements": raw.get("eligibility_requirement_to_join_count"),
            "tags": tags,
            "time_left": raw.get("time_left_to_submission"),
        },
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


def _derive_slug(raw: dict) -> str:
    """Generate a unique slug from the Devpost hackathon."""
    title = raw.get("title", "")
    devpost_id = str(raw.get("id", ""))

    if title:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:70]
        return f"{slug}-dp{devpost_id[-6:]}" if devpost_id else slug

    return f"devpost-{devpost_id}"
