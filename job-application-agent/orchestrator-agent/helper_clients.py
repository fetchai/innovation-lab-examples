"""Network clients for the remaining helper agents (extractor + submitter).

Profile calls are handled directly via profile_store / field_mapper in the
merged orchestrator — no network hop needed.
"""

from __future__ import annotations

from typing import Optional

from uagents import Context, Model


class ExtractJobRequest(Model):
    url: str


class ExtractJobResponse(Model):
    success: bool
    error: Optional[str] = None
    job_json: Optional[str] = None


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
