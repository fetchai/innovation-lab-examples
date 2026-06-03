"""Thin synchronous-style clients for the three helper agents.

We duplicate the wire models here (rather than imports) so this agent is a
deployable unit on its own — uAgents wire compatibility only requires the
field names + types to match the schema published by each helper agent.

Each `call_*` helper uses `ctx.send_and_receive(...)` which awaits the
response inside the current handler. That lets the chat handler stream
intermediate `ChatMessage` progress updates between calls (extract → map →
submit) while still presenting one coherent linear flow to the user.
"""

from __future__ import annotations

from typing import Optional

from uagents import Context, Model


# ---------------------------------------------------------------------------
# greenhouse-extractor wire models (mirror of extractor/agent.py)
# ---------------------------------------------------------------------------


class ExtractJobRequest(Model):
    url: str


class ExtractJobResponse(Model):
    success: bool
    error: Optional[str] = None
    job_json: Optional[str] = None


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


class MapFieldsRequest(Model):
    user_key: str = "me"
    questions_json: str


class MapFieldsResponse(Model):
    success: bool
    error: Optional[str] = None
    result_json: Optional[str] = None


# ---------------------------------------------------------------------------
# submitter-agent wire models (mirror of submitter-agent/agent.py)
# ---------------------------------------------------------------------------


class SubmitApplicationRequest(Model):
    job_json: str
    filled_json: str
    resume_path: str
    dry_run: bool = False


class SubmitApplicationResponse(Model):
    success: bool
    error: Optional[str] = None
    application_id: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    dry_run: bool = False
    missing_required: list[str] = []
    fields_submitted: list[str] = []


# ---------------------------------------------------------------------------
# send_and_receive wrappers
#
# Each wrapper returns the *typed response* or raises ValueError on transport
# failure. Helper-agent business-logic failures (success=False) are passed
# through unchanged so the chat handler can render the helper's own error.
# ---------------------------------------------------------------------------


async def call_extractor(
    ctx: Context, address: str, url: str, timeout: int = 30
) -> ExtractJobResponse:
    if not address:
        raise ValueError("EXTRACTOR_AGENT_ADDRESS is not set")
    resp, status = await ctx.send_and_receive(
        address,
        ExtractJobRequest(url=url),
        response_type=ExtractJobResponse,
        timeout=timeout,
    )
    if not isinstance(resp, ExtractJobResponse):
        raise ValueError(f"Extractor returned unexpected response (status={status})")
    return resp


async def call_get_profile(
    ctx: Context, address: str, user_key: str, timeout: int = 15
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
        raise ValueError(f"Profile agent returned unexpected response (status={status})")
    return resp


async def call_upsert_profile(
    ctx: Context,
    address: str,
    user_key: str,
    profile_json: str,
    timeout: int = 15,
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
        raise ValueError(f"Profile upsert returned unexpected response (status={status})")
    return resp


async def call_map_fields(
    ctx: Context,
    address: str,
    user_key: str,
    questions_json: str,
    timeout: int = 90,
) -> MapFieldsResponse:
    if not address:
        raise ValueError("PROFILE_AGENT_ADDRESS is not set")
    resp, status = await ctx.send_and_receive(
        address,
        MapFieldsRequest(user_key=user_key, questions_json=questions_json),
        response_type=MapFieldsResponse,
        timeout=timeout,
    )
    if not isinstance(resp, MapFieldsResponse):
        raise ValueError(f"MapFields returned unexpected response (status={status})")
    return resp


async def call_submitter(
    ctx: Context,
    address: str,
    job_json: str,
    filled_json: str,
    resume_path: str,
    dry_run: bool,
    timeout: int = 60,
) -> SubmitApplicationResponse:
    if not address:
        raise ValueError("SUBMITTER_AGENT_ADDRESS is not set")
    resp, status = await ctx.send_and_receive(
        address,
        SubmitApplicationRequest(
            job_json=job_json,
            filled_json=filled_json,
            resume_path=resume_path,
            dry_run=dry_run,
        ),
        response_type=SubmitApplicationResponse,
        timeout=timeout,
    )
    if not isinstance(resp, SubmitApplicationResponse):
        raise ValueError(f"Submitter returned unexpected response (status={status})")
    return resp
