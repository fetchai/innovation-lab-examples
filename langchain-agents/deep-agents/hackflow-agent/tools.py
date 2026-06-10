import os
import re

import httpx


def _tavily():
    """Return a TavilyClient, initialized lazily on first use."""
    from tavily import TavilyClient

    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def search_hackathon_events(query: str, max_results: int = 5) -> dict:
    """
    Search for hackathon events, conferences, or tech summits.
    Pass the full search query as you want it -- do not add extra keywords.
    Examples: "ETHGlobal SF 2027", "AI hackathons San Francisco upcoming",
              "YC Conversational AI Hackathon June 2026"
    Returns structured results with titles, URLs, dates, and snippets.
    """
    return _tavily().search(
        query,
        max_results=max_results,
        topic="general",
        include_raw_content=False,
    )


def fetch_event_detail(url: str) -> str:
    """
    Fetch the full text of a hackathon event or sponsor page.
    Use after finding a URL to extract sponsors, prizes, tracks, or tech stack.
    Returns up to 6000 characters of cleaned page text.
    """
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:6000]
    except Exception as exc:
        return f"Error fetching {url}: {exc}"


def search_past_winners(query: str) -> dict:
    """
    Search for winning projects from hackathons.
    """
    return _tavily().search(
        query,
        max_results=5,
        topic="general",
        include_raw_content=False,
    )
