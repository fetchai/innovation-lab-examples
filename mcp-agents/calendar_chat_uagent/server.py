# Copied Calendar FastMCP server – see original for full details
# (Identical to snrauto/python-calendar-mcp-uagents copy/server.py)

from __future__ import annotations

import os, json, logging
from dotenv import load_dotenv
from fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

load_dotenv()

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to your Google OAuth *desktop* client JSON.  Override with env var or place
# the file next to this script.
_default_secret = os.path.join(CURRENT_DIR, "calendar_client_secret.json")
CREDENTIALS_PATH = os.getenv("CAL_CREDENTIALS_FILE", _default_secret)

# Where persistent tokens are stored (one file shared across sessions)
_default_tokens = os.path.join(CURRENT_DIR, "oauth_tokens.json")
TOKENS_PATH = os.getenv("CAL_TOKENS_FILE", _default_tokens)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.settings.readonly",
]

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

mcp = FastMCP("Calendar MCP")


class CalendarAuth:
    def __init__(self):
        self.tokens_path = TOKENS_PATH
        self.credentials_path = CREDENTIALS_PATH
        self._service = None
        self._flow = None

    def get_oauth_url(self, session_id: str | None = None) -> str:
        self._flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri="http://localhost:8080/callback",
        )
        url, _ = self._flow.authorization_url(prompt="consent", state=session_id)
        return url

    def exchange_code_for_token(self, code: str):
        if not self._flow:
            raise RuntimeError("OAuth flow not initialised. Call get_oauth_url first.")
        self._flow.fetch_token(code=code)
        creds = self._flow.credentials
        with open(self.tokens_path, "w", encoding="utf-8") as f:
            json.dump({
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes,
            }, f, indent=2)

    def service(self):
        if self._service:
            return self._service
        if not os.path.exists(self.tokens_path):
            raise RuntimeError("Not authenticated – run setup_oauth first.")
        with open(self.tokens_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        creds = Credentials(
            data["token"],
            refresh_token=data.get("refresh_token"),
            token_uri=data["token_uri"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            scopes=data["scopes"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            data["token"] = creds.token
            with open(self.tokens_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        self._service = build("calendar", "v3", credentials=creds)
        return self._service


calendar_auth = CalendarAuth()


@mcp.tool()
def setup_oauth(session_id: str | None = None) -> str:
    try:
        url = calendar_auth.get_oauth_url(session_id)
        return json.dumps({"success": True, "auth_url": url})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def complete_oauth(auth_code: str) -> str:
    try:
        calendar_auth.exchange_code_for_token(auth_code)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def check_auth_status() -> str:
    ok = os.path.exists(calendar_auth.tokens_path)
    return json.dumps({"success": True, "authenticated": ok})


@mcp.tool()
def list_calendars() -> str:
    try:
        svc = calendar_auth.service()
        resp = svc.calendarList().list().execute()
        return json.dumps(resp)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

# ---------------------------------------------------------------------------
# New tool: list_events (primary calendar by default, date or range support)
# ---------------------------------------------------------------------------


def _parse_date_span(date: str) -> tuple[str, str]:
    """Return ISO start/end for a given natural-language *date* string."""
    date_orig = date
    date = date.lower().strip()
    now = datetime.now(timezone.utc)
    if date in ("today", ""):  # default
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date == "tomorrow":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        try:
            # Expect YYYY-MM-DD format
            parts = [int(p) for p in date.split("-")]
            if len(parts) == 3:
                start = datetime(parts[0], parts[1], parts[2], tzinfo=timezone.utc)
            else:
                raise ValueError
        except Exception:
            # Fallback – treat as today
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    logger.debug("🗓️ Parsed date span: input=%s start=%s end=%s", date_orig, start, end)
    return start.isoformat(), end.isoformat()


@mcp.tool()
def list_events(calendar_id: str = "primary", date: str = "", max_results: int = 20) -> str:
    """List events for a given date (default today) in the specified calendar.

    Args:
        calendar_id: Calendar ID (default "primary").
        date: "today", "tomorrow" or YYYY-MM-DD. Empty = today.
        max_results: Limit number of events returned (default 20).
    """
    try:
        logger.info("🛠️ list_events called: calendar_id=%s date=%s max_results=%s", calendar_id, date or "today", max_results)
        service = calendar_auth.service()

        time_min, time_max = _parse_date_span(date)

        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = resp.get("items", [])
        logger.info("📅 Retrieved %s events for %s", len(events), date or "today")
        out = {
            "success": True,
            "calendar_id": calendar_id,
            "date": date or "today",
            "count": len(events),
            "events": [
                {
                    "id": ev.get("id"),
                    "title": ev.get("summary", "(no title)"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "location": ev.get("location", ""),
                    "link": ev.get("htmlLink"),
                }
                for ev in events
            ],
        }
        return json.dumps(out, indent=2)
    except Exception as e:
        logger.error("❌ list_events failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})

# ---------------------------------------------------------------------------
# Additional tools: create, update, delete, search events and free/busy
# ---------------------------------------------------------------------------


@mcp.tool()
def create_event(
    calendar_id: str = "primary",
    summary: str = "",
    start: str = "",
    end: str = "",
    description: str = "",
    location: str = "",
    timezone: str = "UTC",
) -> str:
    """Create a new calendar event.

    Args:
        calendar_id: Calendar to add the event to (default "primary").
        summary: Title of the event.
        start: ISO 8601 start datetime (e.g. "2025-07-25T09:30:00Z").
        end: ISO 8601 end datetime.
        description: Optional description.
        location: Optional location.
        timezone: IANA TZ id (default "UTC").
    """
    try:
        service = calendar_auth.service()
        body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start, "timeZone": timezone},
            "end": {"dateTime": end, "timeZone": timezone},
        }
        event = service.events().insert(calendarId=calendar_id, body=body).execute()
        return json.dumps({"success": True, "event": event})
    except Exception as e:
        logger.error("❌ create_event failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def update_event(
    calendar_id: str = "primary",
    event_id: str = "",
    updates_json: str = "{}",
) -> str:
    """Patch fields on an existing event.

    Args:
        calendar_id: Calendar ID.
        event_id: ID of the event to update.
        updates_json: JSON string with the fields to patch, e.g. '{"summary": "New title"}'.
    """
    try:
        updates = json.loads(updates_json or "{}")
        if not event_id:
            raise ValueError("event_id is required")
        service = calendar_auth.service()
        event = (
            service.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=updates)
            .execute()
        )
        return json.dumps({"success": True, "event": event})
    except Exception as e:
        logger.error("❌ update_event failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def delete_event(calendar_id: str = "primary", event_id: str = "") -> str:
    """Delete an event by ID."""
    try:
        if not event_id:
            raise ValueError("event_id is required")
        service = calendar_auth.service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return json.dumps({"success": True})
    except Exception as e:
        logger.error("❌ delete_event failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def search_events(
    calendar_id: str = "primary",
    query: str = "",
    max_results: int = 20,
) -> str:
    """Search events by text query (subject, attendees, etc.)."""
    try:
        service = calendar_auth.service()
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
                timeMin=datetime.now(timezone.utc).isoformat(),
            )
            .execute()
        )
        return json.dumps({"success": True, "events": resp.get("items", [])})
    except Exception as e:
        logger.error("❌ search_events failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_free_busy(
    calendar_id: str = "primary",
    time_min: str = "",
    time_max: str = "",
) -> str:
    """Return busy blocks for the calendar between *time_min* and *time_max* (ISO)."""
    try:
        if not time_min or not time_max:
            now = datetime.now(timezone.utc)
            time_min = time_min or now.isoformat()
            time_max = time_max or (now + timedelta(days=1)).isoformat()

        service = calendar_auth.service()
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": calendar_id}],
        }
        fb = service.freebusy().query(body=body).execute()
        return json.dumps({"success": True, "freebusy": fb})
    except Exception as e:
        logger.error("❌ get_free_busy failed: %s", e)
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_current_time() -> str:
    now = datetime.now(timezone.utc)
    return json.dumps({
        "success": True,
        "now": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
    })


if __name__ == "__main__":
    port = int(os.getenv("CALENDAR_MCP_PORT", "8081"))
    mcp.run("sse", host="0.0.0.0", port=port) 