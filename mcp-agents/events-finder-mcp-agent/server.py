# Ticketmaster Discovery API MCP Agent
# Implements four tools: search_events, get_event_details, search_venues, find_suggestions
# Sequential thinking: Each tool is atomic, but the agent is designed for LLMs to chain tool calls (e.g., suggest → search_events → get_event_details) as needed. All outputs include IDs for follow-up. Ambiguous queries should be clarified or handled with reasonable defaults.
# SYSTEM PROMPT: Always include event/venue IDs in responses. Clarify ambiguous queries. Never invent IDs or URLs.

import os
import httpx
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("events_finder")

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY")
TICKETMASTER_API_URL = "https://app.ticketmaster.com/discovery/v2"

def _clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}

async def ticketmaster_get(path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    params = _clean_params(params)
    params["apikey"] = TICKETMASTER_API_KEY
    url = f"{TICKETMASTER_API_URL}{path}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

@mcp.tool()
async def search_events(
    keyword: Optional[str] = None,
    countryCode: Optional[str] = None,
    startDateTime: Optional[str] = None,
    endDateTime: Optional[str] = None,
    size: Optional[int] = 10,
    page: Optional[int] = 0,
    classificationName: Optional[str] = None,
) -> str:
    """Find events by keyword, location, date range, classification, etc. Returns a numbered list with event name, date, venue, event ID, and URL. Always include event IDs for follow-up queries."""
    params = {
        "keyword": keyword,
        "countryCode": countryCode,
        "startDateTime": startDateTime,
        "endDateTime": endDateTime,
        "size": size,
        "page": page,
        "classificationName": classificationName,
    }
    data = await ticketmaster_get("/events.json", params)
    if not data or "_embedded" not in data or "events" not in data["_embedded"]:
        return "No events found."
    events = data["_embedded"]["events"]
    lines = []
    for idx, event in enumerate(events, 1):
        venue = event.get("_embedded", {}).get("venues", [{}])[0]
        lines.append(f"{idx}. {event.get('name')}\n   Date: {event.get('dates', {}).get('start', {}).get('dateTime', 'N/A')}\n   Venue: {venue.get('name', 'N/A')}\n   Event ID: {event.get('id')}\n   More info: {event.get('url', 'N/A')}\n")
    return "\n".join(lines)

@mcp.tool()
async def get_event_details(
    id: str,
    locale: Optional[str] = None,
    domain: Optional[str] = None,
) -> str:
    """Get full details for a specific event ID, including name, date, venue, city, price range, genres, ticket link, and description. Always include the event ID."""
    params = {"locale": locale, "domain": domain}
    data = await ticketmaster_get(f"/events/{id}.json", params)
    if not data or "name" not in data:
        return "Event not found."
    venue = data.get("_embedded", {}).get("venues", [{}])[0]
    price = data.get("priceRanges", [{}])[0]
    genres = ", ".join([
        c.get("genre", {}).get("name", "") for c in data.get("classifications", []) if c.get("genre")
    ])
    return (
        f"Event ID: {data.get('id')}\n"
        f"Name: {data.get('name')}\n"
        f"Date: {data.get('dates', {}).get('start', {}).get('dateTime', 'N/A')}\n"
        f"Venue: {venue.get('name', 'N/A')}\n"
        f"City: {venue.get('city', {}).get('name', 'N/A')}\n"
        f"Price Range: {price.get('min', 'N/A')} - {price.get('max', 'N/A')} {price.get('currency', '') if price else ''}\n"
        f"Genres: {genres if genres else 'N/A'}\n"
        f"More info: {data.get('url', 'N/A')}\n"
        f"Description: {data.get('info', '') or data.get('pleaseNote', '') or 'N/A'}"
    )

@mcp.tool()
async def search_venues(
    keyword: Optional[str] = None,
    countryCode: Optional[str] = None,
    stateCode: Optional[str] = None,
    geoPoint: Optional[str] = None,
    radius: Optional[int] = None,
    size: Optional[int] = 10,
    page: Optional[int] = 0,
) -> str:
    """Lookup venues by name or location. Returns a numbered list with venue name, address, venue ID, and URL. Always include venue IDs for follow-up queries."""
    params = {
        "keyword": keyword,
        "countryCode": countryCode,
        "stateCode": stateCode,
        "geoPoint": geoPoint,
        "radius": radius,
        "size": size,
        "page": page,
    }
    data = await ticketmaster_get("/venues.json", params)
    if not data or "_embedded" not in data or "venues" not in data["_embedded"]:
        return "No venues found."
    venues = data["_embedded"]["venues"]
    lines = []
    for idx, venue in enumerate(venues, 1):
        address = venue.get("address", {}).get("line1", "N/A")
        city = venue.get("city", {}).get("name", "N/A")
        lines.append(f"{idx}. {venue.get('name')}\n   Address: {address}, {city}\n   Venue ID: {venue.get('id')}\n   More info: {venue.get('url', 'N/A')}\n")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio") 