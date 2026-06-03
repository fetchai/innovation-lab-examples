"""Profile Agent.

Helper agent (not user-facing) that stores a user's resume + structured
profile fields, indexes the resume for RAG, and maps Greenhouse-style
application questions to pre-filled values for other agents.

Three interfaces exposed:

1. **Typed agent-to-agent protocol** (`profile_agent` v1.0)
   - `GetProfileRequest` -> `GetProfileResponse(profile_json)`
   - `UpsertProfileRequest(profile_json)` -> `UpsertProfileResponse`
   - `IngestResumeRequest(resume_path)` -> `IngestResumeResponse`
   - `MapFieldsRequest(questions_json)` -> `MapFieldsResponse(filled_json, missing)`

2. **REST** for one-time setup / inspection from a shell:
   - POST /profile      body: {"user_key": "me", "profile_json": "{...}"}
   - GET  /profile      returns the "me" profile
   - POST /resume       body: {"user_key": "me", "resume_path": "/abs/path.pdf"}
   - GET  /health

3. **Chat protocol** (so the agent is discoverable on ASI:One and humans can
   inspect what's stored): basic `show profile` / `whoami` style commands.
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
# trust certifi BEFORE aiohttp is imported. (Same pattern as the extractor.)
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

from field_mapper import FieldMapper  # noqa: E402
from models import DEFAULT_USER_KEY, UserProfile  # noqa: E402
from profile_store import ContextStore  # noqa: E402
from rag import ResumeRAG  # noqa: E402
from resume_ingest import (  # noqa: E402
    ResumeIngestError,
    chunk_text,
    ingest_resume,
    stats as resume_stats,
)

# Load secrets from repo-root .env (two levels up).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

AGENT_NAME = "user_profile_agent"
SEED_PHRASE = os.getenv("PROFILE_AGENT_SEED", "profile-agent-helper-seed-v1")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
PORT = int(os.getenv("PROFILE_AGENT_PORT", "8011"))

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Module-level RAG/mapper singletons - the embedding model loads lazily on first use.
rag = ResumeRAG(DATA_DIR)
mapper = FieldMapper(rag=rag, asi_api_key=ASI_ONE_API_KEY)


# ---------------------------------------------------------------------------
# Wire models (JSON-encoded payloads to dodge uagents' pydantic-v1 schema
# limitations on nested models / Any). Receivers rehydrate with
# `UserProfile.model_validate_json` / `MapFieldsResult.model_validate_json`.
# ---------------------------------------------------------------------------


class GetProfileRequest(Model):
    user_key: str = DEFAULT_USER_KEY


class GetProfileResponse(Model):
    success: bool
    exists: bool = False
    error: Optional[str] = None
    profile_json: Optional[str] = None


class UpsertProfileRequest(Model):
    user_key: str = DEFAULT_USER_KEY
    profile_json: str  # JSON of UserProfile


class UpsertProfileResponse(Model):
    success: bool
    error: Optional[str] = None


class IngestResumeRequest(Model):
    user_key: str = DEFAULT_USER_KEY
    resume_path: str  # absolute path to the user's PDF/DOCX/TXT


class IngestResumeResponse(Model):
    success: bool
    error: Optional[str] = None
    stored_path: Optional[str] = None
    chars_extracted: Optional[int] = None
    chunks_indexed: Optional[int] = None


class MapFieldsRequest(Model):
    user_key: str = DEFAULT_USER_KEY
    questions_json: str  # JSON-encoded list of Greenhouse JobQuestion dicts


class MapFieldsResponse(Model):
    success: bool
    error: Optional[str] = None
    result_json: Optional[str] = None  # MapFieldsResult.model_dump_json()


# REST-only bodies (handler signatures need a request model for POSTs).
class HealthResponse(Model):
    status: str
    agent_address: str
    indexed_users: int


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

agent = Agent(name=AGENT_NAME, seed=SEED_PHRASE, port=PORT, mailbox=True)

profile_proto = Protocol(name="profile_agent", version="1.0")
chat_proto = Protocol(spec=chat_protocol_spec)


def _store(ctx: Context) -> ContextStore:
    return ContextStore(ctx.storage)


# ---------------------------------------------------------------------------
# Typed protocol handlers
# ---------------------------------------------------------------------------


@profile_proto.on_message(model=GetProfileRequest, replies=GetProfileResponse)
async def handle_get_profile(ctx: Context, sender: str, msg: GetProfileRequest):
    ctx.logger.info(f"GetProfile from {sender} user_key={msg.user_key}")
    profile = _store(ctx).get(msg.user_key)
    if profile is None:
        await ctx.send(sender, GetProfileResponse(success=True, exists=False))
        return
    await ctx.send(
        sender,
        GetProfileResponse(success=True, exists=True, profile_json=profile.model_dump_json()),
    )


@profile_proto.on_message(model=UpsertProfileRequest, replies=UpsertProfileResponse)
async def handle_upsert_profile(ctx: Context, sender: str, msg: UpsertProfileRequest):
    ctx.logger.info(f"UpsertProfile from {sender} user_key={msg.user_key}")
    try:
        profile = UserProfile.model_validate_json(msg.profile_json)
    except Exception as exc:  # noqa: BLE001
        await ctx.send(sender, UpsertProfileResponse(success=False, error=f"Invalid profile JSON: {exc}"))
        return

    # Merge with existing rather than overwriting silently.
    existing = _store(ctx).get(msg.user_key)
    if existing:
        merged = existing.model_dump()
        merged.update({k: v for k, v in profile.model_dump().items() if v not in (None, "", {}, [])})
        profile = UserProfile.model_validate(merged)

    _store(ctx).set(msg.user_key, profile)
    await ctx.send(sender, UpsertProfileResponse(success=True))


@profile_proto.on_message(model=IngestResumeRequest, replies=IngestResumeResponse)
async def handle_ingest_resume(ctx: Context, sender: str, msg: IngestResumeRequest):
    ctx.logger.info(f"IngestResume from {sender} user_key={msg.user_key} path={msg.resume_path}")
    try:
        stored_path, text = ingest_resume(msg.resume_path, msg.user_key, DATA_DIR)
    except ResumeIngestError as exc:
        await ctx.send(sender, IngestResumeResponse(success=False, error=str(exc)))
        return

    chunks = chunk_text(text)
    try:
        indexed = rag.index(msg.user_key, chunks)
    except Exception as exc:  # noqa: BLE001 - RAG is best-effort
        ctx.logger.warning(f"RAG indexing failed: {exc}")
        indexed = 0

    # Update the stored profile with resume metadata.
    profile = _store(ctx).get(msg.user_key) or UserProfile(
        first_name="", last_name="", email=""  # placeholders until user upserts profile
    )
    profile.resume_path = str(stored_path)
    profile.resume_text = text
    profile.resume_indexed = indexed > 0
    _store(ctx).set(msg.user_key, profile)

    await ctx.send(
        sender,
        IngestResumeResponse(
            success=True,
            stored_path=str(stored_path),
            chars_extracted=len(text),
            chunks_indexed=indexed,
        ),
    )


@profile_proto.on_message(model=MapFieldsRequest, replies=MapFieldsResponse)
async def handle_map_fields(ctx: Context, sender: str, msg: MapFieldsRequest):
    ctx.logger.info(f"MapFields from {sender} user_key={msg.user_key}")
    profile = _store(ctx).get(msg.user_key)
    if profile is None:
        await ctx.send(
            sender,
            MapFieldsResponse(success=False, error=f"No profile stored for user_key={msg.user_key!r}"),
        )
        return

    try:
        questions = json.loads(msg.questions_json)
        if not isinstance(questions, list):
            raise ValueError("questions_json must be a JSON array")
    except Exception as exc:  # noqa: BLE001
        await ctx.send(sender, MapFieldsResponse(success=False, error=f"Invalid questions JSON: {exc}"))
        return

    result = mapper.map_questions(profile, questions, user_key=msg.user_key)
    await ctx.send(sender, MapFieldsResponse(success=True, result_json=result.model_dump_json()))


# ---------------------------------------------------------------------------
# REST endpoints (for one-time setup from a terminal / Postman)
# ---------------------------------------------------------------------------


@agent.on_rest_post("/profile", UpsertProfileRequest, UpsertProfileResponse)
async def rest_upsert_profile(ctx: Context, req: UpsertProfileRequest) -> UpsertProfileResponse:
    try:
        profile = UserProfile.model_validate_json(req.profile_json)
    except Exception as exc:  # noqa: BLE001
        return UpsertProfileResponse(success=False, error=f"Invalid profile JSON: {exc}")

    existing = _store(ctx).get(req.user_key)
    if existing:
        merged = existing.model_dump()
        merged.update({k: v for k, v in profile.model_dump().items() if v not in (None, "", {}, [])})
        profile = UserProfile.model_validate(merged)

    _store(ctx).set(req.user_key, profile)
    ctx.logger.info(f"[REST] profile upserted for {req.user_key}")
    return UpsertProfileResponse(success=True)


@agent.on_rest_get("/profile", GetProfileResponse)
async def rest_get_profile(ctx: Context) -> GetProfileResponse:
    profile = _store(ctx).get(DEFAULT_USER_KEY)
    if profile is None:
        return GetProfileResponse(success=True, exists=False)
    return GetProfileResponse(success=True, exists=True, profile_json=profile.model_dump_json())


@agent.on_rest_post("/resume", IngestResumeRequest, IngestResumeResponse)
async def rest_ingest_resume(ctx: Context, req: IngestResumeRequest) -> IngestResumeResponse:
    try:
        stored_path, text = ingest_resume(req.resume_path, req.user_key, DATA_DIR)
    except ResumeIngestError as exc:
        return IngestResumeResponse(success=False, error=str(exc))

    chunks = chunk_text(text)
    try:
        indexed = rag.index(req.user_key, chunks)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"RAG indexing failed: {exc}")
        indexed = 0

    profile = _store(ctx).get(req.user_key) or UserProfile(first_name="", last_name="", email="")
    profile.resume_path = str(stored_path)
    profile.resume_text = text
    profile.resume_indexed = indexed > 0
    _store(ctx).set(req.user_key, profile)

    ctx.logger.info(
        f"[REST] resume ingested for {req.user_key}: {resume_stats(stored_path)} chunks={indexed}"
    )
    return IngestResumeResponse(
        success=True,
        stored_path=str(stored_path),
        chars_extracted=len(text),
        chunks_indexed=indexed,
    )


@agent.on_rest_get("/health", HealthResponse)
async def rest_health(ctx: Context) -> HealthResponse:
    return HealthResponse(
        status="ok",
        agent_address=str(agent.address),
        indexed_users=1 if rag.has_index(DEFAULT_USER_KEY) else 0,
    )


# ---------------------------------------------------------------------------
# Chat protocol (for ASI:One inspection)
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

    if not text:
        await ctx.send(sender, _make_chat("Send `show profile`, `whoami`, or `help`."))
        return

    if re.search(r"\bhelp\b", cmd):
        await ctx.send(
            sender,
            _make_chat(
                "I am a profile helper agent for the job-application workflow.\n"
                "Commands:\n"
                "  show profile  - dump the stored profile JSON\n"
                "  whoami        - your name + email + resume status\n"
                "  help          - this message\n\n"
                "Use the REST endpoints to set up your profile / resume."
            ),
        )
        return

    if "show profile" in cmd or cmd == "profile":
        profile = _store(ctx).get(DEFAULT_USER_KEY)
        if profile is None:
            await ctx.send(sender, _make_chat("No profile stored yet. POST /profile to set one up."))
            return
        await ctx.send(sender, _make_chat(profile.model_dump_json(indent=2)))
        return

    if "whoami" in cmd:
        profile = _store(ctx).get(DEFAULT_USER_KEY)
        if profile is None:
            await ctx.send(sender, _make_chat("No profile yet."))
            return
        line = (
            f"{profile.first_name} {profile.last_name} <{profile.email}> | "
            f"resume: {'indexed' if profile.resume_indexed else ('on disk' if profile.resume_path else 'none')}"
        )
        await ctx.send(sender, _make_chat(line))
        return

    await ctx.send(sender, _make_chat("Unknown command. Try `help`."))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Ack from {sender} for {msg.acknowledged_msg_id}")


agent.include(profile_proto, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)


README = """# User Profile Agent

![tag:helper](https://img.shields.io/badge/helper-3D8BD3)
![tag:profile](https://img.shields.io/badge/profile-3D8BD3)
![tag:rag](https://img.shields.io/badge/rag-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

Internal helper agent for the job-application workflow. Stores the user's
resume + structured profile fields and maps Greenhouse application questions
to pre-filled values using a RAG pipeline (Qdrant + FastEmbed) plus ASI:One
for free-text composition.

Agent-to-agent: send `GetProfileRequest`, `UpsertProfileRequest`,
`IngestResumeRequest`, or `MapFieldsRequest`.
"""


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    ctx.logger.info(f"Data dir: {DATA_DIR}")
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
                "Helper agent that stores a user's resume + profile, indexes the "
                "resume for RAG, and pre-fills Greenhouse application form fields."
            ),
        )
        ctx.logger.info("Registered with Agentverse")
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Failed to register with Agentverse: {exc}")


if __name__ == "__main__":
    agent.run()
