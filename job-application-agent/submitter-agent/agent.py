"""Submitter Agent.

Helper agent (not user-facing) that takes a structured Greenhouse `JobInfo`
+ a `MapFieldsResult` from the profile agent + a resume file path, and POSTs
the application to Greenhouse's public board API.

Three interfaces:

1. **Typed agent-to-agent protocol** (`submitter_agent` v1.0)
   - `SubmitApplicationRequest` -> `SubmitApplicationResponse`

2. **REST** for manual demos / postman:
   - POST /submit  body: SubmitApplicationRequest fields
   - GET  /health

3. **Chat protocol** for ASI:One discoverability — the primary client is the
   orchestrator, but humans can ask `help`, `address`, or `dry-run` here.
"""

import json
import os
import re
import ssl
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import certifi

# python.org Python on macOS ships without a usable system cert bundle, which
# breaks the agent's mailbox websocket. Patch ssl.create_default_context to
# trust certifi BEFORE aiohttp is imported. Same pattern as the other agents.
_orig_create_default_context = ssl.create_default_context


def _create_default_context_with_certifi(*args, **kwargs):
    ctx = _orig_create_default_context(*args, **kwargs)
    try:
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        pass
    return ctx


ssl.create_default_context = _create_default_context_with_certifi
ssl._create_default_https_context = _create_default_context_with_certifi

from dotenv import load_dotenv  # noqa: E402
from uagents import Agent, Context, Model, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.utils.registration import (  # noqa: E402
    RegistrationRequestCredentials,
    register_chat_agent,
)

from greenhouse_client import (  # noqa: E402
    SubmitError,
    build_payload,
    check_required,
    parse_response,
    post_application,
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

AGENT_NAME = "greenhouse_submitter_agent"
SEED_PHRASE = os.getenv("SUBMITTER_AGENT_SEED", "submitter-agent-helper-seed-v1")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
PORT = int(os.getenv("SUBMITTER_AGENT_PORT", "8012"))
DEFAULT_DRY_RUN = os.getenv("SUBMITTER_DEFAULT_DRY_RUN", "0").lower() in {"1", "true", "yes"}


# ---------------------------------------------------------------------------
# Wire models (JSON-encoded payloads for rich nested structures)
# ---------------------------------------------------------------------------


class SubmitApplicationRequest(Model):
    job_json: str  # JSON-encoded extractor.JobInfo
    filled_json: str  # JSON-encoded profile_agent.MapFieldsResult
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


class HealthResponse(Model):
    status: str
    agent_address: str
    default_dry_run: bool


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

agent = Agent(name=AGENT_NAME, seed=SEED_PHRASE, port=PORT, mailbox=True)
submitter_proto = Protocol(name="submitter_agent", version="1.0")
chat_proto = Protocol(spec=chat_protocol_spec)


# ---------------------------------------------------------------------------
# Core logic (shared by the typed handler and the REST handler)
# ---------------------------------------------------------------------------


def _run_submission(
    ctx: Context, req: SubmitApplicationRequest
) -> SubmitApplicationResponse:
    try:
        job = json.loads(req.job_json)
    except Exception as exc:  # noqa: BLE001
        return SubmitApplicationResponse(success=False, error=f"Invalid job_json: {exc}")

    try:
        filled = json.loads(req.filled_json)
    except Exception as exc:  # noqa: BLE001
        return SubmitApplicationResponse(success=False, error=f"Invalid filled_json: {exc}")

    board_token = job.get("board_token")
    job_id = job.get("job_id")
    if not board_token or not job_id:
        return SubmitApplicationResponse(
            success=False, error="job_json missing board_token / job_id"
        )

    questions = job.get("questions") or []
    filled_fields = filled.get("filled") or []
    have_resume = bool(req.resume_path) and Path(req.resume_path).is_file()

    missing = check_required(questions, filled_fields, have_resume=have_resume)
    if missing:
        ctx.logger.warning(
            f"Refusing to submit — required field(s) missing: {missing}"
        )
        return SubmitApplicationResponse(
            success=False,
            error=f"Missing required field(s): {', '.join(missing)}",
            missing_required=missing,
            dry_run=req.dry_run,
        )

    text_fields, file_field_names = build_payload(filled_fields, questions=questions)
    resume_field = file_field_names[0] if file_field_names else "resume"
    submitted_names = sorted({name for name, _ in text_fields})

    if req.dry_run or DEFAULT_DRY_RUN:
        ctx.logger.info(
            f"[dry-run] would POST to board={board_token} job_id={job_id} "
            f"fields={submitted_names} resume={req.resume_path!r} "
            f"resume_field={resume_field!r}"
        )
        return SubmitApplicationResponse(
            success=True,
            dry_run=True,
            fields_submitted=submitted_names,
            response_body=json.dumps(
                {
                    "url": f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}",
                    "text_fields": text_fields,
                    "resume_field": resume_field,
                    "resume_path": req.resume_path,
                },
                indent=2,
            ),
        )

    if not have_resume:
        return SubmitApplicationResponse(
            success=False,
            error=f"Resume file not found at {req.resume_path!r}",
        )

    try:
        resp = post_application(
            board_token,
            str(job_id),
            text_fields,
            resume_path=req.resume_path,
            resume_field_name=resume_field,
        )
    except SubmitError as exc:
        return SubmitApplicationResponse(success=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return SubmitApplicationResponse(
            success=False, error=f"HTTP error posting application: {exc}"
        )

    application_id, body_text = parse_response(resp)
    ok = 200 <= resp.status_code < 300
    if not ok:
        ctx.logger.error(
            f"Greenhouse submission failed: status={resp.status_code} body={body_text[:300]}"
        )
        return SubmitApplicationResponse(
            success=False,
            error=f"Greenhouse returned HTTP {resp.status_code}",
            response_status=resp.status_code,
            response_body=body_text[:2000],
            fields_submitted=submitted_names,
        )

    ctx.logger.info(
        f"Submitted to board={board_token} job_id={job_id} -> "
        f"status={resp.status_code} application_id={application_id}"
    )
    return SubmitApplicationResponse(
        success=True,
        application_id=application_id,
        response_status=resp.status_code,
        response_body=body_text[:2000],
        fields_submitted=submitted_names,
    )


# ---------------------------------------------------------------------------
# Typed protocol handler
# ---------------------------------------------------------------------------


@submitter_proto.on_message(
    model=SubmitApplicationRequest, replies=SubmitApplicationResponse
)
async def handle_submit(ctx: Context, sender: str, msg: SubmitApplicationRequest):
    ctx.logger.info(
        f"Submit request from {sender} dry_run={msg.dry_run} resume={msg.resume_path!r}"
    )
    response = _run_submission(ctx, msg)
    await ctx.send(sender, response)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@agent.on_rest_post("/submit", SubmitApplicationRequest, SubmitApplicationResponse)
async def rest_submit(ctx: Context, req: SubmitApplicationRequest) -> SubmitApplicationResponse:
    ctx.logger.info(f"[REST] submit dry_run={req.dry_run}")
    return _run_submission(ctx, req)


@agent.on_rest_get("/health", HealthResponse)
async def rest_health(_ctx: Context) -> HealthResponse:
    return HealthResponse(
        status="ok",
        agent_address=str(agent.address),
        default_dry_run=DEFAULT_DRY_RUN,
    )


# ---------------------------------------------------------------------------
# Chat protocol (for ASI:One discoverability)
# ---------------------------------------------------------------------------


def _make_chat(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text), EndSessionContent(type="end-session")],
    )


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id),
    )
    text = "".join(item.text for item in msg.content if isinstance(item, TextContent)).strip()
    cmd = text.lower()

    if not text or re.search(r"\bhelp\b", cmd):
        await ctx.send(
            sender,
            _make_chat(
                "I am the Greenhouse submitter helper agent.\n"
                "I am driven by the job-application orchestrator, not directly by humans.\n"
                "Commands:\n"
                "  help      - this message\n"
                "  address   - my agent address\n"
                "  dry-run   - report whether dry-run is the default\n"
            ),
        )
        return

    if "address" in cmd:
        await ctx.send(sender, _make_chat(str(agent.address)))
        return

    if "dry" in cmd:
        await ctx.send(
            sender,
            _make_chat(
                f"default_dry_run={DEFAULT_DRY_RUN}. Callers can override per-request."
            ),
        )
        return

    await ctx.send(sender, _make_chat("Unknown command. Try `help`."))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Ack from {sender} for {msg.acknowledged_msg_id}")


agent.include(submitter_proto, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)


README = """# Greenhouse Submitter Agent

![tag:helper](https://img.shields.io/badge/helper-3D8BD3)
![tag:submitter](https://img.shields.io/badge/submitter-3D8BD3)
![tag:greenhouse](https://img.shields.io/badge/greenhouse-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

Internal helper agent for the job-application workflow. Takes a structured
Greenhouse `JobInfo` + a `MapFieldsResult` from the profile agent + a resume
path, and POSTs the application to Greenhouse's public board API.

Send a `SubmitApplicationRequest`; set `dry_run=true` to validate and inspect
the prepared payload without actually posting.
"""


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    ctx.logger.info(f"default_dry_run={DEFAULT_DRY_RUN}")
    if not AGENTVERSE_API_KEY:
        ctx.logger.warning("AGENTVERSE_API_KEY not set - skipping Agentverse registration")
        return

    try:
        register_chat_agent(
            AGENT_NAME,
            agent._endpoints[0].url,
            active=True,
            credentials=RegistrationRequestCredentials(
                agentverse_api_key=AGENTVERSE_API_KEY,
                agent_seed_phrase=SEED_PHRASE,
            ),
            readme=README,
            description=(
                "Helper agent that submits a prepared Greenhouse application "
                "(structured job info + filled fields + resume) to the public "
                "Greenhouse board API."
            ),
        )
        ctx.logger.info("Registered with Agentverse")
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Failed to register with Agentverse: {exc}")


if __name__ == "__main__":
    agent.run()
