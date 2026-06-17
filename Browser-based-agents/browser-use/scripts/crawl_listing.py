"""
Crawl a hackathon listing page and return all event {slug, url} pairs.

Strategy:
- The Cerebral Valley events page loads event cards via client-side JS after
  the initial RSC shell. We use crawl4ai with a JS delay so the DOM is fully
  populated, then extract event slugs from the `links.internal` object which
  crawl4ai populates with all anchor hrefs found in the rendered page.
- Events appear as links of the form:
    https://cerebralvalley.ai/events/~/e/<slug>?modalCloseUrl=...
- We normalise these to canonical URLs: https://cerebralvalley.ai/e/<slug>
"""

import re
import httpx

from config import CRAWL4AI_BASE, BASE_URLS

# Seconds to wait after page load for JS-rendered event cards to appear
JS_RENDER_DELAY = 4


def crawl_listing(source: str, listing_url: str) -> list[dict[str, str]]:
    """
    Crawl the listing page and return deduplicated {slug, url} dicts.
    """
    base_url = BASE_URLS.get(source, "")
    print(f"[LISTING] Fetching {listing_url} (waiting {JS_RENDER_DELAY}s for JS render)")

    result = _fetch_result(listing_url)
    if not result:
        print(f"[LISTING] Failed to fetch page")
        return []

    # Extract from rendered links object (most reliable after JS execution)
    internal_links = result.get("links", {}).get("internal", [])
    events = _extract_from_links(internal_links, base_url)
    print(f"[LISTING] Found {len(events)} unique events from rendered page")

    return events


def _extract_from_links(internal_links: list, base_url: str) -> list[dict[str, str]]:
    """Parse event slugs from crawl4ai's links.internal list."""
    seen: set[str] = set()
    events: list[dict[str, str]] = []

    for link in internal_links:
        href = link.get("href", "")
        m = re.search(r"/e/([a-z0-9][a-z0-9\-]+)", href)
        if not m:
            continue
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        events.append({
            "slug": slug,
            "url": f"{base_url}/e/{slug}",
            "title": link.get("text", "").strip(),
        })

    return events


def _fetch_result(url: str) -> dict | None:
    """POST to crawl4ai with JS delay and return the result object."""
    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json={
                "urls": [url],
                "crawler_config": {
                    "delay_before_return_html": JS_RENDER_DELAY,
                },
            },
            timeout=90,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  [CRAWL] listing fetch error: {e}")
        return None
