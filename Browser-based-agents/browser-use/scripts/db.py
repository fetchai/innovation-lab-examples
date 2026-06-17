"""
Supabase client and database operations.
Uses the Supabase REST API via supabase-py.
Falls back to direct REST calls using the anon key if supabase-py isn't available.
"""

import os
import sys
import json
import httpx
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".llm.env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wnapvpzjwvechlpglrun.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

_client = None


def get_client():
    global _client
    if _client is None:
        try:
            from supabase import create_client
            url = SUPABASE_URL
            key = SUPABASE_KEY
            if not key:
                raise ValueError("SUPABASE_KEY not set")
            _client = create_client(url, key)
        except Exception as e:
            print(f"  [DB] supabase-py init failed ({e}), will use REST fallback")
            _client = "rest"
    return _client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Known columns in the events table
_EVENT_COLUMNS = {
    "id", "source", "slug", "event_url", "title", "description",
    "description_summary", "start_datetime", "end_datetime", "timezone",
    "city", "city_latitude", "city_longitude", "venue", "event_type", "capacity",
    "status", "cv_event", "featured_start_time", "featured_end_time",
    "is_platform_hackathon", "searchable", "approval_required",
    "registration_closed", "enable_chat_apply", "hide_guest_list",
    "show_guest_list_before_approval", "show_location_before_approval",
    "hackathon_public_voting_enabled", "show_hackathon_gallery",
    "hackathon_judging_open", "auto_scoring_enabled", "hosts", "questions",
    "media", "image_url", "llm_extracted",
    "external_url", "external_source", "external_data",
    "platform_created_at",
    "platform_updated_at", "crawled_at", "updated_at",
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
    client = get_client()

    try:
        if client == "rest":
            return _rest_upsert("events", row, "slug")
        result = (
            client.table("events")
            .upsert(row, on_conflict="slug")
            .execute()
        )
        return True
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
    client = get_client()
    try:
        if client == "rest":
            _rest_insert("crawl_log", row)
            return
        client.table("crawl_log").insert(row).execute()
    except Exception as e:
        print(f"  [DB] crawl_log insert failed: {e}")


def _rest_upsert(table: str, row: dict, conflict_col: str) -> bool:
    """Fallback REST upsert when supabase-py is unavailable."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": f"resolution=merge-duplicates,return=minimal",
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
