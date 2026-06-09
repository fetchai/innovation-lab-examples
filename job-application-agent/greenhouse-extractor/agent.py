"""Greenhouse Job Extractor uAgent.

A helper agent (not user-facing) that other agents can call to turn a
Greenhouse job URL into a structured posting + application form schema.

Two interfaces are exposed:

1. Typed agent-to-agent protocol (preferred for other uAgents):
     send `ExtractJobRequest(url=...)` -> receive `ExtractJobResponse`.

2. Chat protocol (for ASI:One or any chat-capable client):
     send a `ChatMessage` whose text contains a Greenhouse URL ->
     receive the extracted JSON as a `ChatMessage` reply.
"""

import json
import os
import re
import ssl
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional
from uuid import uuid4

import certifi

# python.org's Python on macOS ships without a usable system cert bundle, which
# breaks the agent's mailbox websocket. Make the default SSL context also trust
# certifi so aiohttp can verify agentverse.ai. Must run before agent.run().
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

from extractor import ExtractionResult, extract  # noqa: E402

# Load env: repo-root → job-application-agent common → agent-specific (each overrides previous).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

AGENT_NAME = "greenhouse_job_extractor"
SEED_PHRASE = os.getenv("GREENHOUSE_EXTRACTOR_SEED", "greenhouse-extractor-helper-agent-seed")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
PORT = int(os.getenv("GREENHOUSE_EXTRACTOR_PORT", "8010"))

URL_REGEX = re.compile(r"https?://[^\s]+greenhouse\.io[^\s]*", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Agent-to-agent message models
# ---------------------------------------------------------------------------


class ExtractJobRequest(Model):
    url: str


class ExtractJobResponse(Model):
    """Wire response. `job_json` is the JSON-encoded `extractor.JobInfo` dump.

    JSON-as-string is used (instead of a nested model or `dict`) because
    uagents builds its message schema with pydantic v1 internals, which can't
    introspect nested pydantic v2 BaseModel fields or `Any`. Receivers can
    rehydrate with `JobInfo.model_validate_json(msg.job_json)`.
    """

    success: bool
    error: Optional[str] = None
    job_json: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

agent = Agent(
    name=AGENT_NAME,
    seed=SEED_PHRASE,
    port=PORT,
    mailbox=True,
)

extractor_proto = Protocol(name="greenhouse_extractor", version="1.0")
chat_proto = Protocol(spec=chat_protocol_spec)


# ---------------------------------------------------------------------------
# Typed protocol handler
# ---------------------------------------------------------------------------


@extractor_proto.on_message(model=ExtractJobRequest, replies=ExtractJobResponse)
async def handle_extract(ctx: Context, sender: str, msg: ExtractJobRequest):
    ctx.logger.info(f"Extract request from {sender}: {msg.url}")
    result: ExtractionResult = extract(msg.url)
    await ctx.send(
        sender,
        ExtractJobResponse(
            success=result.success,
            error=result.error,
            job_json=result.job.model_dump_json() if result.job else None,
        ),
    )


# ---------------------------------------------------------------------------
# Chat protocol handler (URL-in-text in, JSON-out)
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

    text = "".join(item.text for item in msg.content if isinstance(item, TextContent))
    ctx.logger.info(f"Chat request from {sender}: {text[:200]}")

    match = URL_REGEX.search(text)
    if not match:
        await ctx.send(
            sender,
            _make_chat(
                "Please send a Greenhouse job URL "
                "(e.g. https://boards.greenhouse.io/<company>/jobs/<id>)."
            ),
        )
        return

    result = extract(match.group(0))
    payload = result.model_dump()
    await ctx.send(sender, _make_chat(json.dumps(payload, indent=2)))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Ack from {sender} for {msg.acknowledged_msg_id}")


agent.include(extractor_proto, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)


README = """# Greenhouse Job Extractor

![tag:helper](https://img.shields.io/badge/helper-3D8BD3)
![tag:greenhouse](https://img.shields.io/badge/greenhouse-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

Internal helper agent. Give it a Greenhouse job URL, get back structured job
info and the application form schema (fields + question types + required flags).

Other agents can call this by sending an `ExtractJobRequest(url=...)` and
receiving an `ExtractJobResponse`. ASI:One / chat clients can just paste the
URL into a chat message and will receive the JSON back.
"""


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")

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
                "Helper agent that converts a Greenhouse job URL into a structured "
                "job posting and application form schema."
            ),
        )
        ctx.logger.info("Registered with Agentverse")
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Failed to register with Agentverse: {exc}")


if __name__ == "__main__":
    agent.run()
