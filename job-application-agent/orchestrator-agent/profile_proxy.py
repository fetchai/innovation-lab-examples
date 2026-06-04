"""High-level helpers on top of clients.py.

Encapsulates the JSON-encoding dance the profile-agent uses for its
`profile_json` payloads so the rest of the orchestrator never sees raw
JSON strings.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from uagents import Context

import clients


async def fetch_profile(
    ctx: Context, profile_addr: str, user_key: str
) -> tuple[bool, Optional[dict[str, Any]], Optional[str]]:
    """Return (exists, profile_dict_or_None, error_or_None)."""
    try:
        resp = await clients.call_get_profile(ctx, profile_addr, user_key)
    except Exception as exc:  # noqa: BLE001
        return False, None, f"transport error: {exc}"

    if not resp.success:
        return False, None, resp.error or "profile-agent reported failure"

    if not resp.exists or not resp.profile_json:
        return False, None, None

    try:
        profile = json.loads(resp.profile_json)
    except Exception as exc:  # noqa: BLE001
        return False, None, f"could not decode profile_json: {exc}"

    return True, profile, None


async def upsert_profile_patch(
    ctx: Context,
    profile_addr: str,
    user_key: str,
    patch: dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """Read-modify-write: fetch the current profile (or start from {}),
    apply `patch` (shallow merge), write back. Returns (success, error)."""
    exists, current, err = await fetch_profile(ctx, profile_addr, user_key)
    if err and not exists:
        # Surface only hard transport/decode errors; "no profile yet" is OK.
        if not err.startswith("(none)"):
            ctx.logger.warning(f"upsert_profile_patch: read failed: {err}")

    merged = dict(current or {})
    for k, v in patch.items():
        merged[k] = v

    try:
        resp = await clients.call_upsert_profile(
            ctx, profile_addr, user_key, json.dumps(merged)
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"transport error: {exc}"

    if not resp.success:
        return False, resp.error or "profile-agent reported upsert failure"
    return True, None


async def ingest_resume(
    ctx: Context,
    profile_addr: str,
    user_key: str,
    resume_path: str,
    timeout: int = 120,
) -> tuple[bool, Optional[clients.IngestResumeResponse], Optional[str]]:
    """Tell the profile-agent to parse + index a resume file on disk.
    Returns (success, full_response_or_None, error_or_None)."""
    try:
        resp = await clients.call_ingest_resume(
            ctx, profile_addr, user_key, resume_path, timeout=timeout
        )
    except Exception as exc:  # noqa: BLE001
        return False, None, f"transport error: {exc}"

    if not resp.success:
        return False, resp, resp.error or "profile-agent reported ingest failure"
    return True, resp, None
