"""Wire-model duplicates + `ctx.send_and_receive` wrappers for the
profile-agent and form-filler-agent.

The model field names + types are byte-identical to the helper agents'
own definitions; uAgents only requires that for wire compatibility (the
docstrings can differ, unlike the form-filler-agent's earlier extractor
collision — those types are not used here).
"""

from __future__ import annotations

from typing import Optional

from uagents import Context, Model


# ---------------------------------------------------------------------------
# profile-agent wire models (mirror of profile-agent/agent.py)
# ---------------------------------------------------------------------------


class GetProfileRequest(Model):
    user_key: str = "me"


class GetProfileResponse(Model):
    success: bool
    exists: bool = False
    error: Optional[str] = None
    profile_json: Optional[str] = None


class UpsertProfileRequest(Model):
    user_key: str = "me"
    profile_json: str


class UpsertProfileResponse(Model):
    success: bool
    error: Optional[str] = None


class IngestResumeRequest(Model):
    user_key: str = "me"
    resume_path: str


class IngestResumeResponse(Model):
    success: bool
    error: Optional[str] = None
    stored_path: Optional[str] = None
    chars_extracted: Optional[int] = None
    chunks_indexed: Optional[int] = None


# ---------------------------------------------------------------------------
# send_and_receive wrappers
# ---------------------------------------------------------------------------


async def call_get_profile(
    ctx: Context, address: str, user_key: str, timeout: int = 30
) -> GetProfileResponse:
    if not address:
        raise ValueError("PROFILE_AGENT_ADDRESS is not set")
    resp, status = await ctx.send_and_receive(
        address,
        GetProfileRequest(user_key=user_key),
        response_type=GetProfileResponse,
        timeout=timeout,
    )
    if not isinstance(resp, GetProfileResponse):
        raise ValueError(
            f"Profile agent returned unexpected response (status={status})"
        )
    return resp


async def call_upsert_profile(
    ctx: Context,
    address: str,
    user_key: str,
    profile_json: str,
    timeout: int = 30,
) -> UpsertProfileResponse:
    if not address:
        raise ValueError("PROFILE_AGENT_ADDRESS is not set")
    resp, status = await ctx.send_and_receive(
        address,
        UpsertProfileRequest(user_key=user_key, profile_json=profile_json),
        response_type=UpsertProfileResponse,
        timeout=timeout,
    )
    if not isinstance(resp, UpsertProfileResponse):
        raise ValueError(
            f"Profile upsert returned unexpected response (status={status})"
        )
    return resp


async def call_ingest_resume(
    ctx: Context,
    address: str,
    user_key: str,
    resume_path: str,
    timeout: int = 120,
) -> IngestResumeResponse:
    if not address:
        raise ValueError("PROFILE_AGENT_ADDRESS is not set")
    resp, status = await ctx.send_and_receive(
        address,
        IngestResumeRequest(user_key=user_key, resume_path=resume_path),
        response_type=IngestResumeResponse,
        timeout=timeout,
    )
    if not isinstance(resp, IngestResumeResponse):
        raise ValueError(
            f"Profile ingest returned unexpected response (status={status})"
        )
    return resp
