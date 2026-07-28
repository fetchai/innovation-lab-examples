"""
Supabase client and database operations.
Uses the Supabase REST API via supabase-py.
Falls back to direct REST calls using the anon key if supabase-py isn't available.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://wnapvpzjwvechlpglrun.supabase.co"
)
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
# SUPABASE_KEY above is the `anon` key — fine for tables like `events` that
# are meant to be publicly readable/writable. Tables holding per-user data
# (e.g. hackathon_profiles, which includes plaintext platform passwords) are
# locked down with RLS to service_role only, so they need this separate key
# instead. Get it from Supabase dashboard > Settings > API > service_role,
# and NEVER expose it to a browser/client — server-side use only.
SUPABASE_SERVICE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
)

_client: object = None
_service_client: object = None


_DB_RETRIES = 5
_DB_RETRY_BASE = 5  # seconds; doubles each attempt


def get_client(force_new: bool = False):
    global _client
    if _client is None or force_new:
        try:
            from supabase import create_client

            if not SUPABASE_KEY:
                raise ValueError("SUPABASE_KEY not set")
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"  [DB] supabase-py init failed ({e}), will use REST fallback")
            _client = "rest"
    return _client


def get_service_client(force_new: bool = False):
    """
    Client authenticated with the service_role key, which bypasses RLS.
    Use ONLY for tables that are intentionally locked down to service_role
    (e.g. hackathon_profiles) — never for anything a browser/client will
    also need to reach, and never share this key outside the backend.
    """
    global _service_client
    if _service_client is None or force_new:
        from supabase import create_client

        if not SUPABASE_SERVICE_KEY:
            raise ValueError(
                "SUPABASE_SERVICE_KEY not set — required for per-user tables "
                "like hackathon_profiles. Get it from Supabase dashboard > "
                "Settings > API > service_role, and add it to .env (never commit it)."
            )
        _service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _service_client


def _with_retry(fn, label: str):
    """Call fn(), retrying on network/DNS errors with exponential backoff."""
    delay = _DB_RETRY_BASE
    for attempt in range(1, _DB_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            is_network = any(
                k in str(e)
                for k in (
                    "nodename",
                    "Name or service",
                    "Connection",
                    "timeout",
                    "Errno 8",
                    "Errno 110",
                )
            )
            if is_network and attempt < _DB_RETRIES:
                print(
                    f"  [DB] {label} network error (attempt {attempt}/{_DB_RETRIES}), retrying in {delay}s: {e}"
                )
                time.sleep(delay)
                delay = min(delay * 2, 120)
                get_client(force_new=True)  # reset connection
            else:
                raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Known columns in the events table
_EVENT_COLUMNS = {
    "id",
    "source",
    "slug",
    "event_url",
    "title",
    "description",
    "description_summary",
    "start_datetime",
    "end_datetime",
    "timezone",
    "city",
    "city_latitude",
    "city_longitude",
    "venue",
    "event_type",
    "capacity",
    "status",
    "cv_event",
    "featured_start_time",
    "featured_end_time",
    "is_platform_hackathon",
    "searchable",
    "approval_required",
    "registration_closed",
    "enable_chat_apply",
    "hide_guest_list",
    "show_guest_list_before_approval",
    "show_location_before_approval",
    "hackathon_public_voting_enabled",
    "show_hackathon_gallery",
    "hackathon_judging_open",
    "auto_scoring_enabled",
    "hosts",
    "questions",
    "media",
    "image_url",
    "llm_extracted",
    "external_url",
    "external_source",
    "external_data",
    "platform_created_at",
    "platform_updated_at",
    "crawled_at",
    "updated_at",
}


def _build_event_row(event: dict[str, Any]) -> dict[str, Any]:
    """
    Map a raw event dict to the events table columns.
    Any unrecognised fields are folded into llm_extracted JSONB.
    """
    row: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    for k, v in event.items():
        if k in _EVENT_COLUMNS:
            row[k] = v
        else:
            extras[k] = v

    # Merge extras into llm_extracted
    existing_llm = row.get("llm_extracted") or {}
    if isinstance(existing_llm, str):
        try:
            existing_llm = json.loads(existing_llm)
        except Exception:
            existing_llm = {}
    existing_llm.update(extras)
    if existing_llm:
        row["llm_extracted"] = existing_llm

    # Coerce empty strings to None for timestamp columns
    _TIMESTAMP_COLS = {
        "start_datetime",
        "end_datetime",
        "platform_created_at",
        "platform_updated_at",
        "featured_start_time",
        "featured_end_time",
        "crawled_at",
        "updated_at",
    }
    for col in _TIMESTAMP_COLS:
        if col in row and row[col] == "":
            row[col] = None

    # Serialise JSONB fields
    for col in ("hosts", "questions", "media", "llm_extracted", "external_data"):
        if col in row and isinstance(row[col], (dict, list)):
            row[col] = json.dumps(row[col])

    row["updated_at"] = _now_iso()
    row.setdefault("crawled_at", _now_iso())
    return row


def upsert_event(event: dict[str, Any]) -> bool:
    """
    Upsert an event row. Conflict target is 'slug'.
    Returns True on success, False on error.
    """
    if not event.get("slug"):
        print("  [DB] skipping event with no slug")
        return False

    row = _build_event_row(event)

    try:

        def _do():
            c = get_client()
            if c == "rest":
                return _rest_upsert("events", row, "slug")
            c.table("events").upsert(row, on_conflict="slug").execute()
            return True

        return _with_retry(_do, f"upsert {event.get('slug')}")
    except Exception as e:
        print(f"  [DB] upsert failed for slug={event.get('slug')}: {e}")
        return False


def log_crawl(
    source: str,
    url: str,
    status: str,
    event_slug: str | None = None,
    error_msg: str | None = None,
) -> None:
    """Write a row to crawl_log."""
    row = {
        "source": source,
        "url": url,
        "status": status,
        "event_slug": event_slug,
        "error_msg": error_msg,
        "crawled_at": _now_iso(),
    }
    try:

        def _do():
            c = get_client()
            if c == "rest":
                _rest_insert("crawl_log", row)
            else:
                c.table("crawl_log").insert(row).execute()

        _with_retry(_do, "crawl_log insert")
    except Exception as e:
        print(f"  [DB] crawl_log insert failed: {e}")


def _rest_upsert(table: str, row: dict, conflict_col: str) -> bool:
    """Fallback REST upsert when supabase-py is unavailable."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        json=row,
        headers=headers,
        timeout=15,
    )
    if resp.status_code not in (200, 201, 204):
        print(f"  [DB] REST upsert error {resp.status_code}: {resp.text[:200]}")
        return False
    return True


def fetch_uncrawled_events(
    batch_size: int = 100,
    offset: int = 0,
    source_filter: str | None = None,
    event_source_filter: str | None = None,
) -> list[dict]:
    """
    Return events that have an external_url but no external_data yet.
    source_filter      — filters by external_source (which platform hosts the event)
    event_source_filter — filters by source (which crawler ingested the event, e.g. 'mlh')
    """
    try:

        def _do():
            c = get_client()
            q = (
                c.table("events")
                .select(
                    "id, slug, external_url, external_source, start_datetime, title"
                )
                .is_("external_data", "null")
                .not_.is_("external_url", "null")
                .order("start_datetime", desc=True)
                .range(offset, offset + batch_size - 1)
            )
            if source_filter:
                q = q.eq("external_source", source_filter)
            if event_source_filter:
                q = q.eq("source", event_source_filter)
            return q.execute().data or []

        return _with_retry(_do, "fetch_uncrawled_events")
    except Exception as e:
        print(f"  [DB] fetch_uncrawled_events failed: {e}")
        return []


def count_uncrawled_events(
    source_filter: str | None = None,
    event_source_filter: str | None = None,
) -> int:
    """Return count of events with external_url but no external_data."""
    try:

        def _do():
            c = get_client()
            q = (
                c.table("events")
                .select("id", count="exact")
                .is_("external_data", "null")
                .not_.is_("external_url", "null")
            )
            if source_filter:
                q = q.eq("external_source", source_filter)
            if event_source_filter:
                q = q.eq("source", event_source_filter)
            return q.execute().count or 0

        return _with_retry(_do, "count_uncrawled_events")
    except Exception as e:
        print(f"  [DB] count_uncrawled_events failed: {e}")
        return 0


def update_external_data(slug: str, external_data: dict, error: bool = False) -> bool:
    """Patch just the external_data (and updated_at) on an existing event row."""
    payload = {
        "external_data": json.dumps(external_data),
        "updated_at": _now_iso(),
    }
    try:

        def _do():
            get_client().table("events").update(payload).eq("slug", slug).execute()
            return True

        return _with_retry(_do, f"update_external_data {slug}")
    except Exception as e:
        print(f"  [DB] update_external_data failed for {slug}: {e}")
        return False


def _rest_insert(table: str, row: dict) -> None:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    httpx.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        json=row,
        headers=headers,
        timeout=10,
    )
