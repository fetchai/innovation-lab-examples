import os
from pathlib import Path

from dotenv import load_dotenv

# Load from .env in the project root (one level up from scripts/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)

ASI_ONE_API_KEY = os.environ["ASI_ONE_API_KEY"]
ASI_ONE_BASE_URL = "https://api.asi1.ai/v1"
ASI_ONE_MODEL = "asi1-mini"

CRAWL4AI_BASE = "http://localhost:11235"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ---------------------------------------------------------------------------
# Source registry
# Each entry maps source_name → config dict with:
#   url        : primary listing URL
#   crawler    : which crawler module handles it (api | html | browser)
#   base_url   : canonical base for building event URLs
#   notes      : any caveats
# ---------------------------------------------------------------------------
SOURCES = {
    # ── Tier 1: direct REST API ─────────────────────────────────────────────
    "cerebralvalley": {
        "url": "https://cerebralvalley.ai/events?locations=ALL",
        "crawler": "api",
        "base_url": "https://cerebralvalley.ai",
        "notes": "Uses internal API at api.cerebralvalley.ai/v1/public/event/pull",
    },
    "devpost": {
        "url": "https://devpost.com/api/hackathons",
        "crawler": "api",
        "base_url": "https://devpost.com",
        "notes": "Public JSON API, 13,469+ hackathons, paginated by page number",
    },
    # ── Tier 2: HTML scraping ────────────────────────────────────────────────
    "mlh": {
        "url": "https://www.mlh.com/seasons/2026/events",
        "crawler": "mlh",
        "base_url": "https://www.mlh.com",
        "notes": "Custom parser: extracts 250+ events from external link text + crawls events.mlh.io detail pages",
    },
    "hackerearth": {
        "url": "https://www.hackerearth.com/challenges/hackathon/",
        "crawler": "html",
        "base_url": "https://www.hackerearth.com",
        "notes": "HTML listing, may require delay for JS render",
    },
    # ── Tier 3: browser automation (JS-rendered) ─────────────────────────────
    "devfolio": {
        "url": "https://devfolio.co/hackathons",
        "crawler": "browser",
        "base_url": "https://devfolio.co",
        "notes": "Next.js/React Query, needs JS delay + scroll",
    },
    "ethglobal": {
        "url": "https://ethglobal.com/events",
        "crawler": "browser",
        "base_url": "https://ethglobal.com",
        "notes": "403 on direct fetch, needs browser with realistic headers",
    },
    "dorahacks": {
        "url": "https://dorahacks.io/hackathon",
        "crawler": "browser",
        "base_url": "https://dorahacks.io",
        "notes": "No REST API, requires full browser rendering",
    },
    "unstop": {
        "url": "https://unstop.com/hackathons",
        "crawler": "browser",
        "base_url": "https://unstop.com",
        "notes": "GraphQL blocked, requires browser automation",
    },
}

BASE_URLS = {name: cfg["base_url"] for name, cfg in SOURCES.items()}
