"""
Crawl external event registration pages (Luma, Eventbrite, Devpost, etc.)
and extract additional event details via ASI:One LLM.

Called from crawl_event.py when a Cerebral Valley event links out to
a third-party platform. The extracted data is stored in external_data JSONB
and merged into the event row.
"""

import re
import httpx
from urllib.parse import urlparse

from config import CRAWL4AI_BASE
from extract import parse_rsc_payload, llm_extract

# Known event/hackathon platform domains to follow
KNOWN_PLATFORMS: dict[str, str] = {
    "lu.ma": "luma",
    "luma.com": "luma",
    "eventbrite.com": "eventbrite",
    "eventbrite.co.uk": "eventbrite",
    "devpost.com": "devpost",
    "devfolio.co": "devfolio",
    "dorahacks.io": "dorahacks",
    "unstop.com": "unstop",
    "hackerearth.com": "hackerearth",
    "meetup.com": "meetup",
    "hopin.com": "hopin",
    "airmeet.com": "airmeet",
    "konfhub.com": "konfhub",
    "lablab.ai": "lablab",
}

# Domains to explicitly ignore (CDNs, analytics, maps, social)
IGNORED_DOMAINS = {
    "cdn.", "maps.google", "maps.googleapis", "fonts.google",
    "posthog", "sentry", "clerk.", "github.com", "linkedin.com",
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "w3.org", "schema.org",
}


def detect_external_url(crawl_result: dict, rsc_text: str) -> tuple[str, str] | None:
    """
    Scan a crawl result and RSC text for links to known event platforms.
    Returns (url, source_name) or None.
    """
    candidates: list[tuple[str, str]] = []

    # 1. Check crawl4ai links.external
    for link in crawl_result.get("links", {}).get("external", []):
        href = link.get("href", "")
        match = _match_platform(href)
        if match:
            candidates.append((href, match))

    # 2. Scan RSC payload text for platform URLs
    for url in re.findall(r'https?://[^\s"\'<>\\]+', rsc_text):
        match = _match_platform(url)
        if match:
            # Clean up URL (strip trailing punctuation/quotes)
            url = url.rstrip('",\'\\)')
            candidates.append((url, match))

    if not candidates:
        return None

    # Prefer the first clean candidate
    for url, source in candidates:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return url, source

    return None


def crawl_external(url: str, source: str) -> dict:
    """
    Fetch an external event page and extract event details via LLM.
    Returns a dict with extracted fields (stored in external_data JSONB).
    """
    print(f"  [EXTERNAL] Crawling {source} → {url}")

    html = _fetch_html(url)
    if not html:
        print(f"  [EXTERNAL] Failed to fetch {url}")
        return {"error": "fetch_failed", "url": url, "source": source}

    # Get readable text — for most platforms the HTML is more useful than RSC
    # Try RSC first (Luma uses Next.js too), fall back to raw HTML text
    rsc_text = parse_rsc_payload(html)
    content = rsc_text if len(rsc_text) > 500 else _html_to_text(html)

    instruction = (
        f"Extract hackathon/event details from this {source} event page. "
        "Return a JSON object with these fields (null if missing): "
        "title, date_start (ISO8601), date_end (ISO8601), timezone, location, "
        "description, prize_amount, registration_deadline, max_participants, "
        "team_size (e.g. '1-4'), tracks (array), sponsors (array of names), "
        "judges (array of names), schedule (array of {time, activity}), "
        "tags (array), registration_url, is_online (bool), extra (any other relevant info)."
    )

    extracted = llm_extract(content, instruction)
    if isinstance(extracted, dict):
        extracted["_source"] = source
        extracted["_url"] = url
    else:
        extracted = {"_source": source, "_url": url, "_raw": str(extracted)}

    print(f"  [EXTERNAL] ✓ extracted {len(extracted)} fields from {source}")
    return extracted


def _match_platform(url: str) -> str | None:
    """Return the platform name if the URL belongs to a known event platform."""
    if not url.startswith("http"):
        return None
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return None

    # Skip ignored domains
    if any(ig in netloc for ig in IGNORED_DOMAINS):
        return None

    for domain, name in KNOWN_PLATFORMS.items():
        if netloc == domain or netloc.endswith("." + domain):
            return name

    return None


def _fetch_html(url: str) -> str | None:
    """Fetch a page via crawl4ai with a short JS delay for dynamic content."""
    try:
        resp = httpx.post(
            f"{CRAWL4AI_BASE}/crawl",
            json={
                "urls": [url],
                "crawler_config": {"delay_before_return_html": 3},
            },
            timeout=90,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0].get("html", "") if results else None
    except Exception as e:
        print(f"  [EXTERNAL] fetch error: {e}")
        return None


def _html_to_text(html: str) -> str:
    """Strip HTML tags for a plain-text view to pass to the LLM."""
    import re
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]
