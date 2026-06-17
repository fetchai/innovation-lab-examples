"""
Fetch all events from the Cerebral Valley public API with full pagination.

The API at https://api.cerebralvalley.ai/v1/public/event/pull is the real
source of truth — the HTML listing only shows ~5 upcoming events, while the
API has 2,700+ events going back to 2024.

Returns a list of raw event dicts ready for upsert. Each dict already contains
all fields available from the API; the detail-page crawl is only done for
platform hackathons that have a dedicated /e/<slug> page.
"""

import httpx
from datetime import datetime, timezone

API_BASE = "https://api.cerebralvalley.ai/v1/public/event/pull"
PAGE_SIZE = 50
# Fetch everything from this date (far past = all events)
FETCH_SINCE = "2020-01-01T00:00:00.000Z"


def fetch_all_events(source: str = "cerebralvalley") -> list[dict]:
    """
    Paginate through the entire Cerebral Valley API and return all events.
    Each event is normalised into the DB schema format.
    """
    all_events: list[dict] = []
    offset = 0

    print(f"[API] Fetching all events from Cerebral Valley API...")

    while True:
        batch = _fetch_page(offset)
        if not batch:
            break

        for raw in batch:
            all_events.append(_normalise(raw, source))

        print(f"[API] offset={offset:>5} → {len(batch)} events (total: {len(all_events)})")

        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    print(f"[API] Done. Total events fetched: {len(all_events)}")
    return all_events


def _fetch_page(offset: int) -> list[dict]:
    try:
        resp = httpx.get(
            API_BASE,
            params={
                "approved": "true",
                "startDateTime": FETCH_SINCE,
                "limit": PAGE_SIZE,
                "offset": offset,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as e:
        print(f"  [API] fetch error at offset={offset}: {e}")
        return []


def _normalise(raw: dict, source: str) -> dict:
    """
    Map a raw API event dict to the DB schema.
    The API uses different field names from the platform event pages.
    """
    event_id = raw.get("id", "")
    name = raw.get("name", "")
    external_url = raw.get("url", "")

    # Derive slug from external_url or id
    slug = _derive_slug(raw)

    # Image URL — API returns without scheme prefix sometimes
    image_url = raw.get("imageUrl", "") or ""
    if image_url and not image_url.startswith("http"):
        image_url = f"https://{image_url.rstrip(';')}"

    return {
        "id": event_id or f"{source}:{slug}",
        "source": source,
        "slug": slug,
        "event_url": f"https://cerebralvalley.ai/e/{slug}" if slug else None,
        "title": name,
        "description": raw.get("description"),
        "description_summary": raw.get("descriptionSummary"),
        "start_datetime": raw.get("startDateTime"),
        "end_datetime": raw.get("endDateTime"),
        "city": raw.get("location"),
        "venue": raw.get("venue"),
        "event_type": raw.get("type"),
        "status": raw.get("status"),
        "cv_event": raw.get("CVEvent"),
        "featured_start_time": raw.get("featuredStartTime"),
        "featured_end_time": raw.get("featuredEndTime"),
        "image_url": image_url or None,
        "external_url": external_url or None,
        "external_source": _detect_source(external_url),
        "platform_updated_at": None,
        "platform_created_at": None,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


def _derive_slug(raw: dict) -> str:
    """
    Derive a unique slug for the event. Platform events have a real slug
    embedded in the API data or derivable from the name. Fallback to the ID.
    """
    # Check platformEventData for a slug (platform hackathons)
    platform_data = raw.get("platformEventData")
    if isinstance(platform_data, dict) and platform_data.get("slug"):
        return platform_data["slug"]

    # Derive from name: lowercase, replace spaces/special chars with hyphens
    name = raw.get("name", "")
    if name:
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        slug = slug[:80]
        # Append first 8 chars of ID to ensure uniqueness
        uid = (raw.get("id") or "")[:8]
        if uid:
            return f"{slug}-{uid}"
        return slug

    return raw.get("id", "unknown")


def _detect_source(url: str) -> str | None:
    """Identify which external platform the URL belongs to."""
    if not url:
        return None
    url_lower = url.lower()
    platform_map = {
        "lu.ma": "luma",
        "luma.com": "luma",
        "eventbrite.com": "eventbrite",
        "devpost.com": "devpost",
        "devfolio.co": "devfolio",
        "dorahacks.io": "dorahacks",
        "partiful.com": "partiful",
        "unstop.com": "unstop",
        "hackerearth.com": "hackerearth",
        "meetup.com": "meetup",
        "hopin.com": "hopin",
        "lablab.ai": "lablab",
        "konfhub.com": "konfhub",
    }
    for domain, name in platform_map.items():
        if domain in url_lower:
            return name
    return "external"
