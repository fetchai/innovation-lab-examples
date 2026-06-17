"""
Browser-based crawler for JS-heavy platforms that block plain HTTP requests
(Devfolio, ETHGlobal, DoraHacks, Unstop).

Uses crawl4ai with extended JS delay + scroll simulation, then ASI:One LLM
to extract structured event lists from the rendered content.
"""

import re
import httpx
from datetime import datetime, timezone

from config import CRAWL4AI_BASE
from extract import parse_rsc_payload, llm_extract

# Per-source browser crawl config
SOURCE_CONFIGS: dict[str, dict] = {
    "devfolio": {
        "listing_urls": ["https://devfolio.co/hackathons"],
        "js_delay": 5,
        "scroll": True,
        "extract_instruction": (
            "Extract all hackathon events from this Devfolio page. "
            "Return a JSON array: [{title, url, date_start, date_end, "
            "prize_amount, location, is_online, tags, team_size}]"
        ),
    },
    "ethglobal": {
        "listing_urls": ["https://ethglobal.com/events"],
        "js_delay": 5,
        "scroll": True,
        "extra_headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        },
        "extract_instruction": (
            "Extract all Ethereum/Web3 hackathon events from this ETHGlobal page. "
            "Return a JSON array: [{title, url, date_start, date_end, "
            "location, is_online, prize_pool, tags}]"
        ),
    },
    "dorahacks": {
        "listing_urls": ["https://dorahacks.io/hackathon"],
        "js_delay": 6,
        "scroll": True,
        "extract_instruction": (
            "Extract all hackathon events from this DoraHacks page. "
            "Return a JSON array: [{title, url, date_start, date_end, "
            "prize_amount, location, is_online, tracks, tags}]"
        ),
    },
    "unstop": {
        "listing_urls": [
            "https://unstop.com/hackathons",
            "https://unstop.com/competitions",
        ],
        "js_delay": 6,
        "scroll": True,
        "extract_instruction": (
            "Extract all hackathon and competition events from this Unstop page. "
            "Return a JSON array: [{title, url, date_start, date_end, "
            "prize_amount, eligibility, location, tags, organizer}]"
        ),
    },
}

# JS to simulate user scroll and trigger lazy loading
SCROLL_JS = """
    for (let i = 0; i < 8; i++) {
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 700));
    }
    window.scrollTo(0, 0);
"""


def fetch_all_events(source: str) -> list[dict]:
    """Fetch and extract all events for a given browser-rendered source."""
    cfg = SOURCE_CONFIGS.get(source)
    if not cfg:
        print(f"[BROWSER] No config for source: {source}")
        return []

    all_events: list[dict] = []
    seen_slugs: set[str] = set()

    for url in cfg["listing_urls"]:
        print(f"[BROWSER:{source}] Fetching {url} (JS delay={cfg['js_delay']}s)")
        html = _fetch_html(url, cfg)
        if not html:
            continue

        rsc = parse_rsc_payload(html)
        content = rsc if len(rsc) > 500 else _html_to_text(html)

        raw_list = llm_extract(content, cfg["extract_instruction"])
        if not isinstance(raw_list, list):
            print(f"  [BROWSER:{source}] LLM returned non-list: {type(raw_list)}")
            continue

        for item in raw_list:
            if not isinstance(item, dict):
                continue
            event = _normalise(item, source)
            slug = event["slug"]
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                all_events.append(event)

        print(f"  [BROWSER:{source}] Extracted {len(raw_list)} events from {url}")

    print(f"[BROWSER:{source}] Done. Total unique: {len(all_events)} events")
    return all_events


def _normalise(raw: dict, source: str) -> dict:
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
            "prize_amount": raw.get("prize_amount") or raw.get("prize_pool"),
            "is_online": raw.get("is_online"),
            "tags": raw.get("tags", []),
            "tracks": raw.get("tracks", []),
            "team_size": raw.get("team_size"),
            "eligibility": raw.get("eligibility"),
            "organizer": raw.get("organizer"),
        },
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }


def _derive_slug(title: str, url: str, source: str) -> str:
    if title:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:70]
        return f"{source}-{slug}"
    path = url.rstrip("/").split("/")[-1]
    return f"{source}-{path}" if path else f"{source}-unknown"


def _fetch_html(url: str, cfg: dict) -> str | None:
    crawler_config: dict = {
        "delay_before_return_html": cfg.get("js_delay", 5),
    }
    if cfg.get("scroll"):
        crawler_config["js_code"] = SCROLL_JS

    payload: dict = {
        "urls": [url],
        "crawler_config": crawler_config,
    }

    if cfg.get("extra_headers"):
        payload["browser_config"] = {"headers": cfg["extra_headers"]}

    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0].get("html", "") if results else None
    except Exception as e:
        print(f"  [BROWSER] fetch error for {url}: {e}")
        return None


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]
