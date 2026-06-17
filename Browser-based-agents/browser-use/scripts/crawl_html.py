"""
Generic HTML crawler for platforms that don't have a public API
but render event listings in server-side HTML (MLH, HackerEarth).

Uses crawl4ai for fetching + ASI:One LLM to extract structured event
lists from the rendered page content.
"""

import re
import httpx
from datetime import datetime, timezone

from config import CRAWL4AI_BASE, BASE_URLS
from extract import parse_rsc_payload, llm_extract

# Per-source scraping config
SOURCE_CONFIGS: dict[str, dict] = {
    "mlh": {
        "listing_urls": [
            "https://www.mlh.com/seasons/2025/events",
            "https://www.mlh.com/seasons/2026/events",
        ],
        "js_delay": 5,
        "link_path_prefix": "/events/",
        "extract_instruction": (
            "Extract all hackathon events from this MLH events page. "
            "Return a JSON array of objects: "
            "[{title, url, date_start, date_end, location, is_online, tags}]"
        ),
    },
    "hackerearth": {
        "listing_urls": [
            "https://www.hackerearth.com/challenges/hackathon/",
        ],
        "js_delay": 4,
        "extract_instruction": (
            "Extract all hackathon challenges from this HackerEarth page. "
            "Return a JSON array of objects: "
            "[{title, url, date_start, date_end, prize_amount, participants_count, tags}]"
        ),
    },
}


def fetch_all_events(source: str) -> list[dict]:
    """Fetch and extract all events for a given HTML-based source."""
    cfg = SOURCE_CONFIGS.get(source)
    if not cfg:
        print(f"[HTML] No config for source: {source}")
        return []

    all_events: list[dict] = []
    for url in cfg["listing_urls"]:
        print(f"[HTML:{source}] Fetching {url}")
        result = _fetch_result(url, js_delay=cfg["js_delay"])
        if not result:
            continue

        html = result.get("html", "")
        link_prefix = cfg.get("link_path_prefix")

        # Strategy 1: extract from links object when a path prefix is configured
        if link_prefix:
            from urllib.parse import urlparse
            base = url.split("/")[2]  # domain
            internal = result.get("links", {}).get("internal", [])
            link_events = []
            for link in internal:
                href = link.get("href", "")
                parsed = urlparse(href)
                if base not in parsed.netloc:
                    continue
                if not parsed.path.startswith(link_prefix):
                    continue
                if parsed.path.rstrip("/") == link_prefix.rstrip("/"):
                    continue
                title = link.get("text", "").strip()
                slug = _derive_slug(title, href, source)
                link_events.append(_normalise({"title": title, "url": href}, source))
            if link_events:
                all_events.extend(link_events)
                print(f"  [HTML:{source}] Links extracted {len(link_events)} events from {url}")
                continue

        # Strategy 2: LLM extraction on page text
        rsc = parse_rsc_payload(html)
        content = (rsc if len(rsc) > 500 else _html_to_text(html))[:6000]

        raw_list = llm_extract(content, cfg["extract_instruction"])
        if not isinstance(raw_list, list):
            print(f"  [HTML:{source}] LLM returned non-list: {type(raw_list)}")
            continue

        for item in raw_list:
            if not isinstance(item, dict):
                continue
            all_events.append(_normalise(item, source))

        print(f"  [HTML:{source}] Extracted {len(raw_list)} events from {url}")

    print(f"[HTML:{source}] Done. Total: {len(all_events)} events")
    return all_events


def _normalise(raw: dict, source: str) -> dict:
    """Map a LLM-extracted event dict to the DB schema."""
    title = raw.get("title", "")
    event_url = raw.get("url", "")
    slug = _derive_slug(title, event_url, source)

    return {
        "id": f"{source}:{slug}",
        "source": source,
        "slug": slug,
        "event_url": event_url,
        "external_url": event_url,
        "external_source": source,
        "title": title,
        "description": raw.get("description"),
        "description_summary": raw.get("description"),
        "start_datetime": raw.get("date_start"),
        "end_datetime": raw.get("date_end"),
        "city": raw.get("location"),
        "llm_extracted": {
            "prize_amount": raw.get("prize_amount"),
            "is_online": raw.get("is_online"),
            "tags": raw.get("tags", []),
            "participants_count": raw.get("participants_count"),
        },
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


def _derive_slug(title: str, url: str, source: str) -> str:
    if title:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:70]
        # Add source prefix to avoid clashes with other sources
        return f"{source}-{slug}"
    # Fallback: derive from URL path
    path = url.rstrip("/").split("/")[-1]
    return f"{source}-{path}" if path else f"{source}-unknown"


def _fetch_result(url: str, js_delay: int = 3) -> dict | None:
    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json={"urls": [url], "crawler_config": {"delay_before_return_html": js_delay}},
            timeout=90,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  [HTML] fetch error for {url}: {e}")
        return None


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]
