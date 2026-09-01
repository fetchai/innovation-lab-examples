"""News API client.

Backends (in priority order, first one with a key wins):

1. **Tavily** (`TAVILY_API_KEY`) — web search with a `topic: "news"` mode.
   Returns titles, snippets and image URLs from across the web.
2. **NewsAPI.org** (`NEWS_API_KEY`) — top-headlines or /everything search.
3. **Hacker News** — public Firebase API, no key required. Default fallback.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_SEARCH_URL = "https://api.tavily.com/search"

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
NEWS_API_TOP_URL = "https://newsapi.org/v2/top-headlines"
NEWS_API_EVERYTHING_URL = "https://newsapi.org/v2/everything"

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

DEFAULT_LIMIT = 6

# Country values that mean "no country filter".
_ANY_COUNTRY = {"", "any", "all", "global", "world"}


@dataclass
class Article:
    """Normalised article shape consumed by the card builder."""

    article_id: str
    title: str
    description: str
    url: str
    image_url: str
    source: str
    published_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Article":
        return cls(**data)


def _placeholder_image(seed: str) -> str:
    """Deterministic picsum.photos image URL for a given seed string."""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:10]
    return f"https://picsum.photos/seed/{digest}/800/450"


def _short_id(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:12]


def _force_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def _country_param() -> str | None:
    """Return the NEWS_API_COUNTRY env value, or None when set to 'any'."""
    raw = os.getenv("NEWS_API_COUNTRY", "").strip().lower()
    if raw in _ANY_COUNTRY:
        return None
    return raw


# ---------------------------------------------------------------------------
# Tavily backend
# ---------------------------------------------------------------------------


def _fetch_tavily(query: str | None, limit: int) -> list[Article]:
    """Fetch news-topic search results from Tavily.

    Tavily returns `results` (article-like records) and a parallel `images`
    array. We pair them by index and fall back to a picsum placeholder when
    no image is available.
    """
    search_query = (query or "").strip() or "latest breaking news today"
    payload: dict[str, Any] = {
        "api_key": TAVILY_API_KEY,
        "query": search_query,
        "topic": "news",
        "max_results": max(limit, 1),
        "search_depth": "basic",
        "include_images": True,
        "include_answer": False,
    }
    headers = {"Content-Type": "application/json"}

    resp = requests.post(TAVILY_SEARCH_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    raw_results = data.get("results") or []
    raw_images = data.get("images") or []

    # Normalise the image list — Tavily returns either a list of URL strings
    # or a list of {"url": ..., "description": ...} dicts depending on flags.
    image_urls: list[str] = []
    for img in raw_images:
        if isinstance(img, str):
            image_urls.append(img)
        elif isinstance(img, dict):
            url = img.get("url")
            if isinstance(url, str):
                image_urls.append(url)

    articles: list[Article] = []
    for idx, item in enumerate(raw_results[:limit]):
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url:
            continue

        article_id = "tv_" + _short_id(url)
        image_url = (
            image_urls[idx] if idx < len(image_urls) else _placeholder_image(article_id)
        )
        image_url = _force_https(image_url)

        content = (item.get("content") or item.get("raw_content") or "").strip()
        if not content:
            content = "Tap to read the full article."
        if len(content) > 600:
            content = content[:600].rstrip() + "…"

        netloc = urlparse(url).netloc or "Web"
        source = netloc.removeprefix("www.")

        articles.append(
            Article(
                article_id=article_id,
                title=title,
                description=content,
                url=url,
                image_url=image_url,
                source=source,
                published_at=str(item.get("published_date") or ""),
            )
        )
    return articles


# ---------------------------------------------------------------------------
# NewsAPI.org backend
# ---------------------------------------------------------------------------


def _detect_category(query: str | None) -> str | None:
    """Map a free-text query to a NewsAPI category if possible."""
    if not query:
        return None
    q = query.lower()
    mapping = {
        "tech": "technology",
        "technology": "technology",
        "business": "business",
        "sports": "sports",
        "sport": "sports",
        "entertainment": "entertainment",
        "health": "health",
        "science": "science",
        "general": "general",
        "world": "general",
        "latest": None,
    }
    for key, value in mapping.items():
        if key in q:
            return value
    return None


def _fetch_newsapi(
    query: str | None, category: str | None, limit: int
) -> list[Article]:
    """Fetch articles from NewsAPI.org. Requires NEWS_API_KEY."""
    params: dict[str, Any] = {
        "pageSize": min(limit, 20),
        "apiKey": NEWS_API_KEY,
        "language": "en",
    }

    country = _country_param()
    generic_query = (query or "").strip().lower() in {"", "latest", "news", "top"}

    if query and not generic_query:
        # Specific user search → /everything.
        params["q"] = query
        params["sortBy"] = "publishedAt"
        url = NEWS_API_EVERYTHING_URL
    elif country or category:
        # Generic ask + a country/category filter → /top-headlines.
        url = NEWS_API_TOP_URL
        if country:
            params["country"] = country
        if category:
            params["category"] = category
    else:
        # No constraints → fall back to /everything with a generic query.
        url = NEWS_API_EVERYTHING_URL
        params["q"] = "news"
        params["sortBy"] = "publishedAt"

    resp = requests.get(url, params=params, timeout=25)
    resp.raise_for_status()
    payload = resp.json()

    raw_articles = payload.get("articles", []) or []
    articles: list[Article] = []
    for raw in raw_articles[:limit]:
        title = raw.get("title")
        url_field = raw.get("url")
        if not title or not url_field:
            continue

        article_id = "na_" + _short_id(url_field)
        image_url = _force_https(
            raw.get("urlToImage") or _placeholder_image(article_id)
        )

        description = (raw.get("description") or raw.get("content") or "").strip()
        if not description:
            description = "Tap to read the full article."

        articles.append(
            Article(
                article_id=article_id,
                title=title.strip(),
                description=description,
                url=url_field,
                image_url=image_url,
                source=((raw.get("source") or {}).get("name") or "News").strip(),
                published_at=raw.get("publishedAt", ""),
            )
        )
    return articles


# ---------------------------------------------------------------------------
# Hacker News backend (no key required)
# ---------------------------------------------------------------------------


def _fetch_hackernews(limit: int) -> list[Article]:
    """Fetch top stories from the public Hacker News API (no key required)."""
    resp = requests.get(HN_TOP_URL, timeout=20)
    resp.raise_for_status()
    ids: list[int] = resp.json()[: max(limit * 2, limit)]

    articles: list[Article] = []
    for story_id in ids:
        if len(articles) >= limit:
            break
        try:
            item_resp = requests.get(HN_ITEM_URL.format(id=story_id), timeout=15)
            item_resp.raise_for_status()
            item = item_resp.json() or {}
        except requests.RequestException:
            continue

        title = item.get("title")
        url = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
        if not title:
            continue

        score = item.get("score", 0)
        by = item.get("by", "anonymous")
        descendants = item.get("descendants", 0)
        description = (
            f"Posted by {by} · {score} points · {descendants} comments on Hacker News."
        )

        articles.append(
            Article(
                article_id=f"hn_{story_id}",
                title=title,
                description=description,
                url=url,
                image_url=_placeholder_image(f"hn-{story_id}-{title}"),
                source="Hacker News",
                published_at=str(item.get("time", "")),
            )
        )
    return articles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def active_backend() -> str:
    """Human-readable label for the active news backend."""
    if TAVILY_API_KEY:
        return "Tavily"
    if NEWS_API_KEY:
        return "NewsAPI.org"
    return "Hacker News"


async def fetch_news(
    *,
    query: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[Article]:
    """Fetch a list of articles.

    Picks the highest-priority configured backend (Tavily → NewsAPI → Hacker
    News) and runs the blocking HTTP call in a worker thread. `query` is a
    free-text user query: it becomes the search term for Tavily/NewsAPI and
    is ignored by Hacker News (which always returns top stories).
    """

    def _work() -> list[Article]:
        try:
            if TAVILY_API_KEY:
                return _fetch_tavily(query=query, limit=limit)
            if NEWS_API_KEY:
                category = _detect_category(query)
                return _fetch_newsapi(query=query, category=category, limit=limit)
            return _fetch_hackernews(limit=limit)
        except requests.RequestException as exc:
            raise RuntimeError(f"News API request failed: {exc}") from exc

    return await asyncio.to_thread(_work)
