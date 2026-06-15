"""Orchestrator Agent — single user-facing chat entry for the
job-application workflow.

This agent owns the user's chat surface and routes intents:

- profile management → `profile-agent`
- job applications → `form-filler-agent`

It does NOT carry business logic itself; the helpers do.

Slice 1 (this file): chat handler + intent router + Agentverse reg.
Wired intents: greet, help, show_profile, cancel, smalltalk.
Stubbed intents: edit_profile, upload_resume, switch_resume,
list_resumes, apply. (Each replies with a 'coming soon' note for now.)
"""

import base64
import json
import os
import ssl
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any, Optional
from uuid import uuid4

import certifi

# Patch ssl.create_default_context to use certifi BEFORE aiohttp imports.
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
    MetadataContent,
    ResourceContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.chat.cards import (  # noqa: E402
    create_card_content,
    extract_card_response,
)
from uagents_core.storage import ExternalStorage  # noqa: E402

import asyncio  # noqa: E402
import chat_assets  # noqa: E402
import chat_llm  # noqa: E402
import form_rendering  # noqa: E402
import form_session  # noqa: E402
import intents  # noqa: E402
import payment_proto as payment_mod  # noqa: E402
import profile_fields  # noqa: E402
import rendering  # noqa: E402
import resume_store  # noqa: E402
import session as session_mod  # noqa: E402
from browser_filler import BrowserSession, FillEvent  # noqa: E402
from commands import Command, parse as parse_command  # noqa: E402
from form_session import Session as FormSession, State as FormState  # noqa: E402
from options import match_option  # noqa: E402
from extractor import ExtractionResult, extract as _extract_job  # noqa: E402
from answer_composer import compose_answer  # noqa: E402
from field_mapper import FieldMapper  # noqa: E402
from greenhouse_client import (  # noqa: E402
    SubmitError, build_payload, check_required, parse_response, post_application,
)
from models import (  # noqa: E402
    MapFieldsResult, UserProfile,
)
from profile_store import ContextStore  # noqa: E402
from resume_ingest import ResumeIngestError, ingest_resume  # noqa: E402
from session import ApplyState, OrchestratorSession  # noqa: E402


# Single source of truth: job-application-agent/.env (one level up).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Mirror all agent output to agent.out.log.
import logging as _logging, sys as _sys  # noqa: E402

_log_file = Path(__file__).resolve().parent / "agent.out.log"
_log_fh = open(_log_file, "w", buffering=1, encoding="utf-8")

class _Tee:
    def __init__(self, orig):
        self._orig = orig
    def write(self, data):
        self._orig.write(data)
        _log_fh.write(data)
    def flush(self):
        self._orig.flush()
        _log_fh.flush()
    def __getattr__(self, name):
        return getattr(self._orig, name)

_tee_out = _Tee(_sys.__stdout__)
_tee_err = _Tee(_sys.__stderr__)
_sys.stdout = _tee_out
_sys.stderr = _tee_err

# StreamHandlers cache their stream object at creation time, so replacing
# sys.stdout above doesn't affect them. Patch every existing StreamHandler
# that points at stdout or stderr to use the Tee instead.
def _patch_stream_handlers():
    for _lgr in [_logging.root] + list(_logging.root.manager.loggerDict.values()):
        if not isinstance(_lgr, _logging.Logger):
            continue
        for _h in _lgr.handlers:
            if isinstance(_h, _logging.StreamHandler):
                if _h.stream is _sys.__stdout__:
                    _h.stream = _tee_out
                elif _h.stream is _sys.__stderr__:
                    _h.stream = _tee_err

AGENT_NAME = "job_application_orchestrator"
SEED_PHRASE = os.getenv(
    "ORCHESTRATOR_AGENT_SEED", "orchestrator-agent-user-facing-seed-v1"
)
PORT = int(os.getenv("ORCHESTRATOR_AGENT_PORT", "8014"))

DEFAULT_USER_KEY = os.getenv("DEFAULT_USER_KEY", "me")

DEFAULT_RESUME_PATH = os.getenv("DEFAULT_RESUME_PATH", "")
DEFAULT_DRY_RUN = os.getenv("SUBMITTER_DEFAULT_DRY_RUN", "0").lower() in {"1", "true", "yes"}

LIVE_FILL_MODE = os.getenv("LIVE_FILL_MODE", "headed").strip().lower()
LIVE_FILL_SCREENSHOT_EVERY = int(os.getenv("LIVE_FILL_SCREENSHOT_EVERY", "3"))

ORCHESTRATOR_DIR = Path(__file__).resolve().parent
JOB_AGENT_DIR = ORCHESTRATOR_DIR.parent

ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY")
ASI_ONE_CHAT_MODEL = os.getenv("ASI_ONE_CHAT_MODEL", "asi1")

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_mapper = FieldMapper(asi_api_key=ASI_ONE_API_KEY, asi_model=ASI_ONE_CHAT_MODEL)

_EXTRACT_SYSTEM_PROMPT = """Extract structured profile fields from the resume text below.
Return ONLY a valid JSON object with these keys (omit keys you cannot find):
first_name, middle_name, last_name, preferred_name, email, phone,
address_line_1, address_line_2, city, state, country, zip_code,
linkedin, github, portfolio, twitter, work_authorization,
education (array of objects with keys: university_name, degree, major,
graduation_date, gpa, gpa_scale, degree_level),
experience (array of objects with keys: company_name, job_title, employment_type,
location, work_mode, start_date, end_date, description).
Use null for missing scalar fields. Omit empty arrays. No markdown, no explanation."""


# ---------------------------------------------------------------------------
# Profile wire models (kept for form-filler-agent compatibility)
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

class MapFieldsRequest(Model):
    user_key: str = "me"
    questions_json: str
    profile_json: Optional[str] = None

class MapFieldsResponse(Model):
    success: bool
    error: Optional[str] = None
    result_json: Optional[str] = None

AGENTVERSE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
STORAGE_URL = f"{AGENTVERSE_URL}/v1/storage"


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

# Ensure storage files land in ORCHESTRATOR_DIR regardless of launch directory.
os.chdir(ORCHESTRATOR_DIR)

agent = Agent(
    name=AGENT_NAME,
    seed=SEED_PHRASE,
    port=PORT,
    network="testnet",
    mailbox=True,
    agentverse=AGENTVERSE_URL,
    publish_agent_details=True,
)

# Patch again after Agent() — it creates all its loggers during __init__.
_patch_stream_handlers()


chat_proto = Protocol(spec=chat_protocol_spec)
profile_proto = Protocol(name="profile_agent", version="1.0")


# ---------------------------------------------------------------------------
# Direct profile helpers (replace profile_proxy + network round-trips)
# ---------------------------------------------------------------------------

def _profile_store(ctx: Context) -> ContextStore:
    return ContextStore(ctx.storage)


def _fetch_profile(ctx: Context, user_key: str) -> tuple[bool, Optional[dict], Optional[str]]:
    profile = _profile_store(ctx).get(user_key)
    if profile is None:
        return False, None, None
    return True, profile.model_dump(mode="json"), None


def _upsert_patch(ctx: Context, user_key: str, patch: dict) -> tuple[bool, Optional[str]]:
    try:
        store = _profile_store(ctx)
        existing = store.get(user_key)
        merged = existing.model_dump(mode="json") if existing else {
            "first_name": "", "last_name": "", "email": "",
        }
        merged.update({k: v for k, v in patch.items() if v is not None})
        store.set(user_key, UserProfile.model_validate(merged))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


_TO_MARKDOWN_PROMPT = (
    "Convert the resume text below into clean, well-structured markdown. "
    "Use # for the candidate's name, ## for section headings (Experience, Education, Skills, etc.), "
    "### for job titles / degree names, and bullet points for responsibilities and achievements. "
    "Preserve all information exactly — do not summarise or omit anything. "
    "Output only the markdown, no commentary."
)


def _to_markdown(raw_text: str) -> str:
    """Reformat raw extracted resume text into clean markdown via ASI:One.
    Falls back to the raw text if the API is unavailable or fails."""
    if not ASI_ONE_API_KEY:
        return raw_text
    try:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=ASI_ONE_API_KEY)
        resp = client.chat.completions.create(
            model=ASI_ONE_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _TO_MARKDOWN_PROMPT},
                {"role": "user", "content": raw_text[:6000]},
            ],
            max_tokens=2000,
            temperature=0.0,
        )
        md = (resp.choices[0].message.content or "").strip()
        md = re.sub(r"^```[a-z]*\n?", "", md)
        md = re.sub(r"\n?```$", "", md)
        return md if md else raw_text
    except Exception:  # noqa: BLE001 - best-effort, fall back to raw text
        return raw_text


def _extract_profile_fields(resume_text: str) -> dict:
    if not ASI_ONE_API_KEY:
        return {}
    try:
        from openai import OpenAI
        client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=ASI_ONE_API_KEY)
        resp = client.chat.completions.create(
            model=ASI_ONE_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": resume_text[:6000]},
            ],
            max_tokens=1200,
            temperature=0.0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


_EDU_STR_FIELDS = {"gpa", "gpa_scale", "graduation_date", "degree_level", "degree", "major", "university_name"}
_EXP_STR_FIELDS = {"start_date", "end_date", "employment_type", "work_mode", "location", "job_title", "company_name"}


def _coerce_edu_exp(extracted: dict) -> None:
    """Coerce numeric/non-string fields in education/experience to strings in-place."""
    for entry in extracted.get("education") or []:
        if isinstance(entry, dict):
            for f in _EDU_STR_FIELDS:
                if f in entry and entry[f] is not None and not isinstance(entry[f], str):
                    entry[f] = str(entry[f])
    for entry in extracted.get("experience") or []:
        if isinstance(entry, dict):
            for f in _EXP_STR_FIELDS:
                if f in entry and entry[f] is not None and not isinstance(entry[f], str):
                    entry[f] = str(entry[f])


def _ingest_resume_direct(
    ctx: Context, user_key: str, resume_path: str
) -> tuple[bool, Optional[dict], Optional[str]]:
    try:
        stored_path, text = ingest_resume(resume_path, user_key, DATA_DIR)
    except ResumeIngestError as exc:
        return False, None, str(exc)

    # Reformat raw extracted text into clean markdown so the LLM gets
    # structured context (section headings, bullets) rather than PDF artifacts.
    text = _to_markdown(text)

    extracted = _extract_profile_fields(text)
    _coerce_edu_exp(extracted)
    existing = _profile_store(ctx).get(user_key)
    if existing:
        base = existing.model_dump(mode="json")
        for k, v in extracted.items():
            if v and not base.get(k):
                base[k] = v
        profile = UserProfile.model_validate(base)
    else:
        safe = {k: v for k, v in extracted.items() if v is not None}
        safe.setdefault("first_name", "")
        safe.setdefault("last_name", "")
        safe.setdefault("email", "")
        profile = UserProfile.model_validate(safe)

    profile.resume_path = str(stored_path)
    profile.resume_text = text
    _profile_store(ctx).set(user_key, profile)

    return True, {
        "stored_path": str(stored_path),
        "chars_extracted": len(text),
    }, None


# ---------------------------------------------------------------------------
# Profile protocol handlers (for form-filler-agent compatibility)
# ---------------------------------------------------------------------------

@profile_proto.on_message(model=GetProfileRequest, replies=GetProfileResponse)
async def handle_get_profile(ctx: Context, sender: str, msg: GetProfileRequest):
    profile = _profile_store(ctx).get(msg.user_key)
    if profile is None:
        await ctx.send(sender, GetProfileResponse(success=True, exists=False))
        return
    await ctx.send(sender, GetProfileResponse(
        success=True, exists=True, profile_json=profile.model_dump_json(),
    ))


@profile_proto.on_message(model=UpsertProfileRequest, replies=UpsertProfileResponse)
async def handle_upsert_profile(ctx: Context, sender: str, msg: UpsertProfileRequest):
    try:
        raw = json.loads(msg.profile_json)
    except Exception as exc:  # noqa: BLE001
        await ctx.send(sender, UpsertProfileResponse(success=False, error=str(exc)))
        return
    raw.setdefault("first_name", "")
    raw.setdefault("last_name", "")
    raw.setdefault("email", "")
    try:
        profile = UserProfile.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        await ctx.send(sender, UpsertProfileResponse(success=False, error=str(exc)))
        return
    existing = _profile_store(ctx).get(msg.user_key)
    if existing:
        merged = existing.model_dump(mode="json")
        merged.update({k: v for k, v in profile.model_dump(mode="json").items()
                       if v not in (None, "", {}, [])})
        profile = UserProfile.model_validate(merged)
    _profile_store(ctx).set(msg.user_key, profile)
    await ctx.send(sender, UpsertProfileResponse(success=True))


@profile_proto.on_message(model=IngestResumeRequest, replies=IngestResumeResponse)
async def handle_ingest_resume_msg(ctx: Context, sender: str, msg: IngestResumeRequest):
    ok, info, err = await asyncio.to_thread(_ingest_resume_direct, ctx, msg.user_key, msg.resume_path)
    if not ok:
        await ctx.send(sender, IngestResumeResponse(success=False, error=err))
        return
    await ctx.send(sender, IngestResumeResponse(success=True, **info))


@profile_proto.on_message(model=MapFieldsRequest, replies=MapFieldsResponse)
async def handle_map_fields(ctx: Context, sender: str, msg: MapFieldsRequest):
    profile = _profile_store(ctx).get(msg.user_key)
    if profile is None:
        await ctx.send(sender, MapFieldsResponse(
            success=False, error=f"No profile for user_key={msg.user_key!r}"
        ))
        return
    try:
        questions = json.loads(msg.questions_json)
    except Exception as exc:  # noqa: BLE001
        await ctx.send(sender, MapFieldsResponse(success=False, error=str(exc)))
        return
    result = await asyncio.to_thread(_mapper.map_questions, profile, questions, user_key=msg.user_key)
    await ctx.send(sender, MapFieldsResponse(success=True, result_json=result.model_dump_json()))


_live_browser_sessions: dict[str, BrowserSession] = {}

_STRUCTURED_FIELD_HINTS = {
    "first_name": ["first_name", "given_name", "firstname"],
    "last_name": ["last_name", "family_name", "surname", "lastname"],
    "email": ["email", "e_mail"],
    "phone": ["phone", "telephone", "mobile"],
    "location": ["current_location", "location", "city"],
    "linkedin_url": ["linkedin", "linked_in"],
    "github_url": ["github", "git_hub"],
    "portfolio_url": ["portfolio", "personal_site", "website"],
    "work_authorization": ["work_auth", "authorization", "sponsorship"],
    "gender": ["gender"],
    "race_ethnicity": ["race", "ethnicity"],
    "veteran_status": ["veteran"],
    "disability_status": ["disability"],
}

FF_HELP = (
    "**Application commands**\n"
    "• Paste a Greenhouse URL — start a new application.\n"
    "• `show <name>`              — full value of one field\n"
    "• `show all` / `form`        — re-print the form preview\n"
    "• `answer <name> <value>`    — fill a missing field\n"
    "• `edit <name> <value>`      — change a filled value\n"
    "• `unfill <name>`            — clear a field\n"
    "• `next`                     — show the next missing field's prompt\n"
    "• `submit`                   — dry-run (preview, nothing sent)\n"
    "• `submit live`              — actually post to Greenhouse\n"
    "• `show payload`             — dump the prepared submitter payload\n"
    "• `cancel`                   — discard the active session"
)


# ---------------------------------------------------------------------------
# Chat helpers
# ---------------------------------------------------------------------------


def _msg(text: str, *, end_session: bool = False) -> ChatMessage:
    content: list = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=content,
    )


async def _say(
    ctx: Context, sender: str, text: str, *, end_session: bool = False
) -> None:
    await ctx.send(sender, _msg(text, end_session=end_session))


async def _send_card(
    ctx: Context,
    sender: str,
    payload: Any,
    *,
    caption: str = "",
    drawer_width_px: Optional[int] = 480,
) -> None:
    """Send an interactive card. We pair it with a small text caption in
    the same ChatMessage — without a companion TextContent the platform
    drops the message entirely (verified by trial)."""
    content: list = [TextContent(type="text",
                                 text=caption or "Here's your profile.")]
    content.append(create_card_content(
        payload,
        preferred_drawer_width_px=drawer_width_px,
    ))
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.now(UTC),
        msg_id=uuid4(),
        content=content,
    ))


async def _send_payment_request(ctx: Context, sender: str) -> None:
    """Send a Stripe RequestPayment. ASI:One renders the embedded checkout."""
    await payment_mod.send_payment_request(ctx, sender)


_MY_MENTION_RE = re.compile(r"^\s*@agent1[a-z0-9]{50,}\s*", re.IGNORECASE)

# Phrases that signal the user wants the LLM to *generate* an answer rather
# than supplying the literal text as the field value.
_GENERATION_REQUEST_RE = re.compile(
    r"\b("
    r"can you|could you"
    r"|please\s+(write|draft|answer|generate)"
    r"|answer\s+(this|it)\s+for\s+me"
    r"|write\s+(this|it)\s+for\s+me"
    r"|draft\s+(this|it)\s+for\s+me"
    r"|for\s+me\s+in\s+\d"
    r"|based\s+on\s+my\s+(resume|profile|cv)"
    r"|from\s+my\s+(resume|profile|cv)"
    r"|in\s+\d+[- ]lines?"
    r")\b",
    re.IGNORECASE,
)


def _is_generation_request(text: str) -> bool:
    """Return True when the user's text is an instruction to draft an answer,
    not the literal value they want to set."""
    return bool(_GENERATION_REQUEST_RE.search(text or ""))


def _extract_text(message: ChatMessage) -> str:
    parts: list[str] = []
    for c in message.content:
        text = getattr(c, "text", None)
        if isinstance(text, str) and text:
            parts.append(text)
    raw = "\n".join(parts).strip()
    # Group-chat clients prepend an "@agent1…" mention to whatever the user
    # typed. Strip it so intent classification sees the actual message.
    return _MY_MENTION_RE.sub("", raw).strip()


def _has_attachment(message: ChatMessage) -> bool:
    """True if any content item looks like a non-text resource (image,
    PDF, etc.)."""
    for c in message.content:
        if getattr(c, "type", "") == "resource":
            return True
    return False


def _resource_items(message: ChatMessage) -> list:
    """Return all resource content items regardless of exact type.

    ASI:One sometimes deserializes ResourceContent as a generic object whose
    type field is "resource" but that fails isinstance(c, ResourceContent).
    Accept both forms so downloads don't silently get skipped.
    """
    return [
        c for c in message.content
        if isinstance(c, ResourceContent) or getattr(c, "type", "") == "resource"
    ]


def _has_end_session(message: ChatMessage) -> bool:
    return any(isinstance(c, EndSessionContent) for c in message.content)


def _download_resource(
    ctx: Context, item
) -> Optional[tuple[bytes, str, str]]:
    """Download a ResourceContent attachment. Returns
    (bytes, mime_type, source_filename) or None on failure.

    Mirrors `pdf-summariser-example/chat_proto.py:download_resource` —
    try Agentverse storage first, then fall back to the public `uri`
    that some chat clients embed on `item.resource[0]` (Agentverse
    storage has TTL'd or never held the bytes for this resource_id)."""
    # Debug: full dump of the resource item so we can see what the chat
    # client actually populated (resource_id, resource list, metadata).
    try:
        ctx.logger.info(
            f"ResourceContent dump: {item.model_dump_json(exclude_none=False)}"
        )
    except Exception:  # noqa: BLE001
        ctx.logger.info(f"ResourceContent dump (raw): {item!r}")

    content_bytes: Optional[bytes] = None
    mime_type = "application/octet-stream"

    # resource_id may be a UUID, a string, or buried in a dict if the item
    # deserialized as a generic object rather than a typed ResourceContent.
    raw_resource_id = (
        item.get("resource_id") if isinstance(item, dict)
        else getattr(item, "resource_id", None)
    )
    resource_id_str = str(raw_resource_id) if raw_resource_id is not None else ""

    # 1a) Agentverse external storage — agent identity attestation
    for _storage_kwargs in [
        {"identity": ctx.agent.identity, "storage_url": STORAGE_URL},
        # 1b) API-key bearer token (user-uploaded assets may only be readable
        #     with our registered API key, not the raw agent attestation)
        *(
            [{"api_token": AGENTVERSE_API_KEY, "storage_url": STORAGE_URL}]
            if AGENTVERSE_API_KEY else []
        ),
    ]:
        if not resource_id_str:
            break
        try:
            storage = ExternalStorage(**_storage_kwargs)
            stored = storage.download(resource_id_str)
            mime_type = stored.get("mime_type", mime_type)
            content_b64 = stored.get("contents", "")
            if content_b64:
                content_bytes = base64.b64decode(content_b64)
                break
        except Exception as exc:  # noqa: BLE001
            ctx.logger.info(
                f"storage download failed for {resource_id_str} "
                f"(kwargs={list(_storage_kwargs)}, err={exc})"
            )

    # 2) URI fallback — try with API-key auth first (Agentverse URIs require
    #    it), then unauthenticated (public/catbox URIs).
    if content_bytes is None:
        uri = None
        res_obj = (
            item.get("resource") if isinstance(item, dict)
            else getattr(item, "resource", None)
        )
        candidates = res_obj if isinstance(res_obj, list) else [res_obj]
        for res in candidates:
            uri = getattr(res, "uri", None) if res is not None else None
            if uri:
                break
        if uri:
            import httpx  # local import keeps the top of the file unchanged
            downloaded = False
            auth_variants: list[dict] = []
            if AGENTVERSE_API_KEY:
                auth_variants.append(
                    {"Authorization": f"Bearer {AGENTVERSE_API_KEY}"}
                )
            auth_variants.append({})  # unauthenticated last
            for headers in auth_variants:
                try:
                    resp = httpx.get(uri, timeout=120, headers=headers)
                    resp.raise_for_status()
                    content_bytes = resp.content
                    mime_type = resp.headers.get("content-type", mime_type)
                    downloaded = True
                    break
                except Exception as exc:  # noqa: BLE001
                    ctx.logger.info(
                        f"URI download attempt failed ({uri}, "
                        f"auth={'key' if headers else 'none'}): {exc}"
                    )
            if not downloaded:
                ctx.logger.warning(f"URI download failed for all auth variants ({uri})")
                return None
        else:
            ctx.logger.warning(
                f"resource {resource_id_str}: no storage bytes and no URI"
            )
            return None

    # Try to recover the original filename from the resource metadata
    # (set by chat clients) or fall back to the asset id.
    source_filename = f"resource_{resource_id_str}"
    res_obj = (
        item.get("resource") if isinstance(item, dict)
        else getattr(item, "resource", None)
    )
    candidates = res_obj if isinstance(res_obj, list) else [res_obj]
    for res in candidates:
        if res is None:
            continue
        md = getattr(res, "metadata", None) or {}
        if not isinstance(md, dict):
            continue
        for k in ("filename", "name", "title", "description"):
            v = md.get(k)
            if v:
                source_filename = str(v)
                break
        # Also pick up mime_type from metadata if storage didn't provide one
        if md.get("mime_type") and mime_type == "application/octet-stream":
            mime_type = str(md["mime_type"])
        if source_filename and not source_filename.startswith("resource_"):
            break

    return content_bytes, mime_type, source_filename


def _is_start_session(message: ChatMessage) -> bool:
    for c in message.content:
        if isinstance(c, StartSessionContent):
            return True
    return False


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------


def _extract_card_selection(msg: ChatMessage) -> Optional[dict[str, Any]]:
    """Return the merged card-response selection dict (or None).

    Tries two paths because the chat client may use either:
      1. Standard: a MetadataContent block parsed by `extract_card_response`.
      2. Legacy fallback: the CTA `selection` posted as a JSON blob inside
         a TextContent bubble (documented in the cards README).
    """
    out: dict[str, Any] = {}

    for c in msg.content:
        if isinstance(c, MetadataContent):
            resp = extract_card_response(c)
            if resp and resp.selection:
                out.update(resp.selection)

    if not out:
        stripped = _extract_text(msg).strip()
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                out.update(parsed)

    return out or None


def _coerce_form_value(field: str, raw: Any) -> Any:
    """Lightweight coercion for form-submit values before patching."""
    if raw in (None, "", "null"):
        return None
    if field in ("needs_sponsorship", "requires_visa"):
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"true", "yes", "1", "on"}
    return raw


async def _handle_profile_card_selection(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    selection: dict[str, Any],
) -> None:
    section = str(selection.get("section") or "")
    submitted = bool(selection.get("submitted"))

    # ---- Form submission: persist the patch and re-show the overview ----
    if submitted:
        patch: dict[str, Any] = {}
        for k, v in selection.items():
            if k in ("section", "submitted"):
                continue
            patch[k] = _coerce_form_value(k, v)
        if not patch:
            await _say(ctx, sender, "Nothing to save — try editing a field first.")
            return

        ok, err = _upsert_patch(ctx, sess.user_key, patch)
        if not ok:
            await _say(ctx, sender, rendering.format_error(
                err or "couldn't save those changes"
            ))
            return

        saved = ", ".join(f"`{k}`" for k in patch)
        await _say(ctx, sender, f"✓ Saved updates to {saved}.")
        await _handle_show_profile(ctx, sender, sess)
        return

    # ---- Section click: open the matching form (or fall back to a hint) ----
    form = rendering.build_section_form(section, sess.profile_summary)
    if form is not None:
        await _send_card(ctx, sender, form, caption=f"Editing {section.replace('_', ' ')}.")
        return

    if section == "education":
        edu_list = (sess.profile_summary or {}).get("education") or []
        await _send_card(
            ctx, sender,
            rendering.build_education_overview_card(edu_list),
            caption="Your education entries — click 'Add Education Details' to add one.",
        )
        return

    if section == "experience":
        exp_list = (sess.profile_summary or {}).get("experience") or []
        await _send_card(
            ctx, sender,
            rendering.build_experience_overview_card(exp_list),
            caption="Your experience entries — click 'Add Experience' to add one.",
        )
        return

    if section == "resume":
        await _say(
            ctx, sender,
            "Drop a PDF, DOCX, or TXT in chat and I'll parse and index it as "
            "your active resume.",
        )
        return

    if section == "answers":
        canned = (sess.profile_summary or {}).get("canned_answers") or {}
        if not canned:
            await _say(
                ctx, sender,
                "No saved answers yet — whenever you answer a tricky "
                "application question, I'll remember it for next time.",
            )
            return
        lines = ["**Saved answers:**"]
        for q, a in list(canned.items())[:25]:
            qs = q if len(q) <= 80 else q[:79] + "…"
            as_ = str(a)
            if len(as_) > 60:
                as_ = as_[:59] + "…"
            lines.append(f"• _{qs}_ → `{as_}`")
        if len(canned) > 25:
            lines.append(f"…and {len(canned) - 25} more")
        await _say(ctx, sender, "\n".join(lines))
        return

    await _say(ctx, sender, f"I don't have an editor for `{section}` yet.")


async def _handle_education_action(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    selection: dict[str, Any],
) -> None:
    action = str(selection.get("action") or "")

    _EDU_FIELD_KEYS = frozenset({
        "university_name", "degree", "major", "graduation_date",
        "gpa", "gpa_scale", "degree_level",
    })

    edu_fields = {
        k: v for k, v in selection.items()
        if k in _EDU_FIELD_KEYS and v not in (None, "")
    }
    edit_index: Optional[int] = selection.get("edit_index")

    if action == "edit_education_entry":
        idx = selection.get("index")
        edu_list = list((sess.profile_summary or {}).get("education") or [])
        existing = edu_list[idx] if idx is not None and 0 <= idx < len(edu_list) else None
        await _send_card(
            ctx, sender,
            rendering.build_education_form(entry=existing, edit_index=idx),
            caption="Edit your education details.",
        )
        return

    if action == "delete_education_entry":
        current = list((sess.profile_summary or {}).get("education") or [])
        if edit_index is not None and 0 <= edit_index < len(current):
            current.pop(edit_index)
            ok, err = _upsert_patch(ctx, sess.user_key, {"education": current})
            if not ok:
                await _say(ctx, sender, rendering.format_error(err or "couldn't delete education entry"))
                return
            sess.profile_summary = None
            session_mod.save(ctx.storage, sess)
            await _say(ctx, sender, "✓ Education entry deleted.")
            await _handle_show_profile(ctx, sender, sess)
        return

    if action == "add_another_education":
        if edu_fields:
            current = list((sess.profile_summary or {}).get("education") or [])
            current.append(edu_fields)
            _upsert_patch(ctx, sess.user_key, {"education": current})
            sess.profile_summary = None
            session_mod.save(ctx.storage, sess)
        await _send_card(ctx, sender, rendering.build_education_form(),
                         caption="Fill in your education details.")
        return

    if action == "save_education":
        if not edu_fields:
            await _say(ctx, sender, "Nothing to save — fill in at least one field first.")
            return
        current = list((sess.profile_summary or {}).get("education") or [])
        if edit_index is not None and 0 <= edit_index < len(current):
            current[edit_index] = {**current[edit_index], **edu_fields}
        else:
            current.append(edu_fields)
        ok, err = _upsert_patch(ctx, sess.user_key, {"education": current})
        if not ok:
            await _say(ctx, sender, rendering.format_error(err or "couldn't save education entry"))
            return
        sess.profile_summary = None
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, "✓ Education entry saved.")
        await _handle_show_profile(ctx, sender, sess)
        return


async def _handle_experience_action(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    selection: dict[str, Any],
) -> None:
    action = str(selection.get("action") or "")

    _EXP_FIELD_KEYS = frozenset({
        "company_name", "job_title", "employment_type",
        "location", "work_mode", "start_date", "end_date", "description",
    })

    exp_fields = {
        k: v for k, v in selection.items()
        if k in _EXP_FIELD_KEYS and v not in (None, "")
    }
    edit_index: Optional[int] = selection.get("edit_index")

    if action == "edit_experience_entry":
        idx = selection.get("index")
        exp_list = list((sess.profile_summary or {}).get("experience") or [])
        existing = exp_list[idx] if idx is not None and 0 <= idx < len(exp_list) else None
        await _send_card(
            ctx, sender,
            rendering.build_experience_form(entry=existing, edit_index=idx),
            caption="Edit your experience details.",
        )
        return

    if action == "delete_experience_entry":
        current = list((sess.profile_summary or {}).get("experience") or [])
        if edit_index is not None and 0 <= edit_index < len(current):
            current.pop(edit_index)
            ok, err = _upsert_patch(ctx, sess.user_key, {"experience": current})
            if not ok:
                await _say(ctx, sender, rendering.format_error(err or "couldn't delete experience entry"))
                return
            sess.profile_summary = None
            session_mod.save(ctx.storage, sess)
            await _say(ctx, sender, "✓ Experience entry deleted.")
            await _handle_show_profile(ctx, sender, sess)
        return

    if action == "add_another_experience":
        if exp_fields:
            current = list((sess.profile_summary or {}).get("experience") or [])
            current.append(exp_fields)
            _upsert_patch(ctx, sess.user_key, {"experience": current})
            sess.profile_summary = None
            session_mod.save(ctx.storage, sess)
        await _send_card(ctx, sender, rendering.build_experience_form(),
                         caption="Fill in your experience details.")
        return

    if action == "save_experience":
        if not exp_fields:
            await _say(ctx, sender, "Nothing to save — fill in at least one field first.")
            return
        current = list((sess.profile_summary or {}).get("experience") or [])
        if edit_index is not None and 0 <= edit_index < len(current):
            current[edit_index] = {**current[edit_index], **exp_fields}
        else:
            current.append(exp_fields)
        ok, err = _upsert_patch(ctx, sess.user_key, {"experience": current})
        if not ok:
            await _say(ctx, sender, rendering.format_error(err or "couldn't save experience entry"))
            return
        sess.profile_summary = None
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, "✓ Experience entry saved.")
        await _handle_show_profile(ctx, sender, sess)
        return


async def _handle_show_profile(
    ctx: Context, sender: str, sess: OrchestratorSession
) -> None:
    await _say(ctx, sender, "🔎 Looking up your profile…")
    exists, profile, err = _fetch_profile(ctx, sess.user_key)
    if err:
        await _say(ctx, sender, rendering.format_error(err))
        return

    card = rendering.build_profile_list_card(
        profile if exists else None,
        active_resume=sess.active_resume_version,
        resume_versions=sess.resume_versions,
    )
    caption = (
        "Here's your profile — tap any section to fill in your details."
        if not exists
        else "Here's your profile — tap any section to edit."
    )
    await _send_card(ctx, sender, card, caption=caption)

    # Always update the cache — clear it when profile doesn't exist so
    # section forms don't show stale data from a previous session.
    sess.profile_summary = profile if exists else None
    session_mod.save(ctx.storage, sess)


async def _handle_edit_profile(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    raw_field: str,
    raw_value: str,
) -> None:
    """Apply a single structured-field edit to the user's stored profile.

    Slice 2 covers only the canonical UserProfile fields enumerated in
    `profile_fields.ALL_KNOWN_FIELDS`. Free-form 'canned answer' edits
    (e.g. "remember to answer X with Y") will land in a follow-up commit.
    """
    field = profile_fields.normalise_field(raw_field)
    if field is None:
        await _say(ctx, sender, rendering.format_field_unknown(raw_field or "?"))
        return

    ok, coerced, err = profile_fields.coerce_value(field, raw_value)
    if not ok:
        await _say(ctx, sender, rendering.format_error(err or "couldn't parse value"))
        return

    exists, current, fetch_err = _fetch_profile(ctx, sess.user_key)
    if fetch_err:
        await _say(ctx, sender, rendering.format_error(fetch_err))
        return
    if not exists:
        await _say(
            ctx, sender,
            (
                "I don't have a profile for you yet — drop your resume in "
                "chat first and I'll bootstrap one. Then I can apply this "
                f"edit ({field} → `{coerced}`)."
            ),
        )
        return

    success, upsert_err = _upsert_patch(ctx, sess.user_key, {field: coerced})
    if not success:
        await _say(
            ctx, sender,
            rendering.format_error(upsert_err or "profile save failed"),
        )
        return

    # Invalidate the cached profile snapshot so the next `show my profile`
    # is fresh, and update the in-memory copy for free.
    if isinstance(current, dict):
        current[field] = coerced
        sess.profile_summary = current
        session_mod.save(ctx.storage, sess)

    ctx.logger.info(f"edit_profile: {field}={coerced!r} for {sess.user_key}")
    await _say(
        ctx, sender,
        rendering.format_edit_confirmation(field, str(coerced)),
    )


async def _handle_upload_resume(
    ctx: Context,
    sender: str,
    msg: ChatMessage,
    sess: OrchestratorSession,
    has_attachment: bool = False,
) -> None:
    """Download every ResourceContent attachment, save locally, ingest directly
    (no network hop), and register the version in `sess.resume_versions`."""
    resources = _resource_items(msg)

    # ASI:One uploads files to Cloudinary and embeds the URL as a markdown
    # image link in TextContent rather than sending a ResourceContent.
    # Extract any such URLs and synthesise fake resource items for them.
    if not resources:
        full_text = "\n".join(
            getattr(c, "text", "") for c in msg.content
            if getattr(c, "type", "") == "text"
        )
        url_matches = re.findall(r'!\[([^\]]*)\]\((https?://\S+)\)', full_text)
        if not url_matches:
            # Also try bare URLs to known file CDNs
            url_matches = [
                ("resume", m)
                for m in re.findall(r'https?://\S+', full_text)
                if any(cdn in m for cdn in ("cloudinary.com", "res.cloudinary", "agentverse", "catbox.moe"))
            ]
        for filename, url in url_matches:
            resources.append({"_url": url, "_filename": filename or "resume.pdf", "resource_id": None})

    if not resources:
        await _say(
            ctx, sender,
            "I couldn't access the attached file — please try uploading "
            "your resume again (PDF, DOCX, or TXT).",
        )
        return

    ingested: list[dict] = []
    for item in resources:
        # Inline-URL item synthesised from markdown text above
        if isinstance(item, dict) and item.get("_url"):
            import httpx as _httpx
            try:
                resp = _httpx.get(item["_url"], timeout=60, follow_redirects=True)
                resp.raise_for_status()
                downloaded: tuple = (resp.content, resp.headers.get("content-type", "application/octet-stream"), item["_filename"])
            except Exception as exc:
                ctx.logger.warning(f"inline URL download failed ({item['_url']}): {exc}")
                await _say(ctx, sender, rendering.format_error(f"Couldn't download the file from the link: {exc}"))
                continue
        else:
            downloaded = _download_resource(ctx, item)
        if not downloaded:
            _rid = item.get("resource_id", "?") if isinstance(item, dict) else getattr(item, "resource_id", "?")
            await _say(
                ctx, sender,
                rendering.format_error(f"Couldn't download attachment `{_rid}`."),
            )
            continue
        content_bytes, mime_type, source_filename = downloaded

        existing_names = [v.get("name", "") for v in sess.resume_versions]
        version_name = resume_store.make_version_name(
            source_filename, existing_names
        )

        await _say(
            ctx, sender,
            f"📎 Got `{source_filename}` ({len(content_bytes)//1024} KB). "
            f"Saving as version `{version_name}` and parsing — give me a "
            f"sec…",
        )

        try:
            version_entry = resume_store.save_resume_bytes(
                sess.user_key,
                version_name,
                content_bytes=content_bytes,
                mime_type=mime_type,
                source_filename=source_filename,
            )
        except Exception as exc:  # noqa: BLE001
            await _say(
                ctx, sender,
                rendering.format_error(f"Couldn't save resume to disk: {exc}"),
            )
            continue

        # Parse + RAG-index directly (no network hop).
        success, info, err = await asyncio.to_thread(_ingest_resume_direct, ctx, sess.user_key, version_entry["path"])
        if not success:
            await _say(
                ctx, sender,
                rendering.format_error(
                    f"Saved the file but couldn't index it: {err or 'unknown error'}"
                ),
            )
            continue

        # Register the new version + make it active.
        sess.resume_versions.append(version_entry)
        sess.active_resume_version = version_name
        session_mod.save(ctx.storage, sess)
        ingested.append({**version_entry, "ingest_info": info})

        chars = info.get("chars_extracted") if info else None
        tail = f"{chars} chars extracted" if chars else "parsed"
        await _say(
            ctx, sender,
            (
                f"✅ Resume `{version_name}` is ready ({tail}).\n"
                f"It's now your **active** resume — any application you "
                f"start next will use it."
            ),
        )

    # If there are other versions, gently mention how to switch.
    if ingested and len(sess.resume_versions) > 1:
        others = [
            v["name"] for v in sess.resume_versions
            if v["name"] != sess.active_resume_version
        ]
        await _say(
            ctx, sender,
            f"_You also have these stored: {', '.join(f'`{n}`' for n in others)}. "
            f"Say `switch resume <name>` to flip back._",
        )


async def _handle_list_resumes(
    ctx: Context, sender: str, sess: OrchestratorSession
) -> None:
    if not sess.resume_versions:
        await _say(
            ctx, sender,
            "📭 No resumes stored yet. Drop a PDF/DOCX/TXT in chat and I'll "
            "parse it for you.",
        )
        return

    lines = ["📎 **Stored resumes**"]
    for v in sess.resume_versions:
        marker = "✅" if v.get("name") == sess.active_resume_version else "  "
        when = v.get("ingested_at", "")[:10]
        src = v.get("source_filename") or ""
        lines.append(
            f"{marker} `{v['name']}` — _{src}_  ({when})"
        )
    lines.append("")
    lines.append(
        "Switch with `switch resume <name>`, or drop a new one to add a "
        "version."
    )
    await _say(ctx, sender, "\n".join(lines))


async def _handle_switch_resume(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    requested_name: str,
) -> None:
    target = resume_store.find_version(sess.resume_versions, requested_name)
    if not target:
        await _say(
            ctx, sender,
            (
                f"I don't have a resume version called `{requested_name}`.\n"
                f"Say `list resumes` to see what's stored."
            ),
        )
        return

    sess.active_resume_version = target["name"]
    session_mod.save(ctx.storage, sess)

    # Sync the profile's `resume_path` so form-filler picks the new one.
    exists, _, _ = _fetch_profile(ctx, sess.user_key)
    if exists:
        ok, err = _upsert_patch(ctx, sess.user_key, {"resume_path": target["path"]})
        if not ok:
            ctx.logger.warning(f"switch_resume: profile sync failed: {err}")

    await _say(
        ctx, sender,
        f"✓ Active resume is now `{target['name']}` "
        f"(`{target.get('source_filename', '')}`).",
    )


# ---------------------------------------------------------------------------
# Form-filler helpers (merged from form-filler-agent)
# ---------------------------------------------------------------------------


def _match_structured_attr(field_name: str, label: str) -> Optional[str]:
    blob = f"{field_name} {label}".lower()
    for attr, hints in _STRUCTURED_FIELD_HINTS.items():
        for h in hints:
            if h in blob:
                return attr
    return None


def _existing_resume_path(raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    raw = Path(raw_path).expanduser()
    candidates = [raw] if raw.is_absolute() else [
        JOB_AGENT_DIR / "profile-agent" / raw,
        JOB_AGENT_DIR / raw,
        ORCHESTRATOR_DIR / raw,
        Path.cwd() / raw,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return str(resolved)
    return None


def _load_profile(ctx: Context, user_key: str) -> dict | None:
    _, profile, _ = _fetch_profile(ctx, user_key)
    return profile


def _resolve_resume_path_from_profile(ctx: Context, profile: dict | None) -> str | None:
    selected = _existing_resume_path((profile or {}).get("resume_path"))
    if selected:
        return selected
    return _existing_resume_path(DEFAULT_RESUME_PATH)


def _resolve_resume_path(ctx: Context, user_key: str) -> str | None:
    return _resolve_resume_path_from_profile(ctx, _load_profile(ctx, user_key))


def _save_edit_to_profile(ctx: Context, user_key: str, *, label: str, field_name: str, value: str) -> None:
    attr = _match_structured_attr(field_name, label)
    if attr:
        _upsert_patch(ctx, user_key, {attr: value})
    else:
        _, profile, _ = _fetch_profile(ctx, user_key)
        canned = dict((profile or {}).get("canned_answers") or {})
        canned[(label or field_name).strip()] = value
        _upsert_patch(ctx, user_key, {"canned_answers": canned})


async def _close_browser_session(sender: str) -> None:
    bs = _live_browser_sessions.pop(sender, None)
    if bs is not None:
        try:
            await bs.close()
        except Exception:  # noqa: BLE001
            pass


async def _send_screenshot(ctx: Context, sender: str, png_bytes: bytes, caption: Optional[str]) -> bool:
    public_url = chat_assets.upload_public_image(png_bytes, filename="form-preview.png",
                                                  mime_type="image/png", logger=ctx.logger)
    if public_url:
        try:
            await ctx.send(sender, chat_assets.make_markdown_image_message(public_url, caption=caption))
            return True
        except Exception:  # noqa: BLE001
            pass
    uploaded = chat_assets.upload_image(png_bytes, name_prefix="form-fill", mime_type="image/png",
                                         grant_to_address=sender, logger=ctx.logger)
    if uploaded:
        asset_id, asset_uri = uploaded
        if caption:
            await _say(ctx, sender, caption)
        try:
            await ctx.send(sender, chat_assets.make_image_message(asset_id, asset_uri))
            return True
        except Exception:  # noqa: BLE001
            pass
    if caption:
        await _say(ctx, sender, caption)
    return False


async def _handle_fill_event(ctx: Context, sender: str, event: FillEvent) -> bool:
    if event.kind in {"started", "field_filled", "field_skipped"}:
        ctx.logger.info(f"live-fill: {event.kind} {event.field_name or ''} {event.message or ''}")
        return False
    if event.kind in {"screenshot", "done"}:
        if not event.screenshot_png:
            return False
        caption = ("📸 " + event.message) if event.message else None
        return await _send_screenshot(ctx, sender, event.screenshot_png, caption)
    if event.kind == "error":
        await _say(ctx, sender, f"⚠️ live-fill: {event.error}")
    return False


async def _run_live_fill(ctx: Context, sender: str, sess: FormSession, application_url: str, *,
                         profile_snapshot: dict | None = None) -> bool:
    headed = LIVE_FILL_MODE == "headed"
    mode_note = (
        "I'll pop a Chrome window on your machine so you can watch / edit the form directly, "
        "and stream screenshots into chat too." if headed
        else "I'll stream screenshots of the real Greenhouse page into the chat."
    )
    await _say(ctx, sender, f"🎬 Opening the real Greenhouse form. {mode_note}")
    await _close_browser_session(sender)
    orch = session_mod.load(ctx.storage, sender)
    _active_ver = next(
        (v for v in orch.resume_versions if v.get("name") == orch.active_resume_version),
        None,
    )
    _resume_filename = (_active_ver or {}).get("source_filename") or None
    bs = BrowserSession(application_url, headless=not headed, resume_path=sess.resume_path,
                        resume_filename=_resume_filename)
    try:
        await bs.open()
    except Exception as exc:  # noqa: BLE001
        await _say(ctx, sender, f"⚠️ Couldn't open the live form ({exc}). Showing text instead.")
        return False
    _live_browser_sessions[sender] = bs

    if profile_snapshot:
        discovered = await bs.discover_profile_fillables(
            profile_snapshot,
            known_names={fld.get("name") for q in sess.questions for fld in (q.get("fields") or []) if fld.get("name")},
        )
        if discovered:
            for item in discovered:
                name = item["name"]
                if not sess.field_meta(name):
                    sess.questions.append({
                        "label": item["label"], "required": item["required"],
                        "description": "Detected from the live Greenhouse form.",
                        "fields": [{"name": name, "type": item["ftype"], "required": item["required"],
                                    "label": None, "values": item.get("options") or []}],
                    })
                if item.get("value") not in (None, "", []):
                    sess.set_field(name, item["value"], source=item.get("source") or "profile",
                                   confidence=float(item.get("confidence") or 0.0))
                elif item.get("required") and name not in sess.missing_required:
                    sess.missing_required.append(name)

    fillables = []
    for f in sess.filled:
        ftype = (f.get("ftype") or "").lower()
        enriched = dict(f)
        meta = sess.field_meta(f.get("name")) or {}
        enriched["options"] = meta.get("values") or meta.get("options") or []
        enriched["ftype"] = ftype or meta.get("type") or ""
        if ftype in {"input_file", "file", "attachment"}:
            fillables.insert(0, enriched)
        else:
            fillables.append(enriched)

    streamed_any = False
    try:
        async for event in bs.initial_fill(fillables, screenshot_every_n_fields=LIVE_FILL_SCREENSHOT_EVERY):
            if await _handle_fill_event(ctx, sender, event):
                streamed_any = True
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"live-fill: initial_fill failed: {exc}")

    # EEO demographic fields (Gender, Hispanic/Latino, Veteran Status,
    # Disability Status) are not returned by the Greenhouse API and are
    # sometimes missed by discover_profile_fillables when their select
    # elements have opaque name attributes.  Fill them directly by label.
    if profile_snapshot:
        try:
            eeo_results = await bs.fill_eeo_fields(profile_snapshot)
            for lbl, ok, detail in eeo_results:
                ctx.logger.info(f"eeo-fill: {lbl!r} ok={ok} {detail}")
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(f"eeo-fill failed: {exc}")

    if headed:
        await _say(ctx, sender, "_Chrome stays open — scroll, edit, or double-check anything. Say `submit` when ready._")
    return streamed_any


async def _apply_field_edit(ctx: Context, sender: str, sess: FormSession, name: str, value: str, kind: str) -> None:
    if not sess.field_meta(name):
        await _say(ctx, sender, f"Hmm, no field called `{name}` on this form. Try `show all` to see names.")
        return
    meta = sess.field_meta(name) or {}
    opts = meta.get("values") or meta.get("options") or []
    resolved = value
    if isinstance(opts, list) and opts:
        match = match_option(value, opts)
        if match:
            resolved = match["value"] or match["label"]
            if resolved != value:
                ctx.logger.info(f"option-snap: {name!r} {value!r} → {resolved!r}")
    q = sess.question_for(name)
    label = (q or {}).get("label") or ""
    sess.set_field(name, resolved, source="user", confidence=1.0)
    sess.user_edits.append({"name": name, "label": label, "value": resolved, "kind": kind})
    form_session.save(ctx.storage, sess)
    orch_sess = session_mod.load(ctx.storage, sender)
    _save_edit_to_profile(ctx, orch_sess.user_key or DEFAULT_USER_KEY,
                          label=label, field_name=name, value=resolved)
    bs = _live_browser_sessions.get(sender)
    if bs is not None and bs.is_open:
        try:
            ok, png, detail = await bs.apply_edit(name, resolved, ftype=meta.get("type") or "",
                                                    options=opts)
            if ok and png is not None:
                await _send_screenshot(ctx, sender, png, caption=f"📸 Updated `{name}` → `{resolved}`")
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(f"live-fill apply_edit failed: {exc}")
    tail = ("All required fields filled — say `submit` when ready."
            if not sess.missing_required
            else f"Still missing: {', '.join(sess.missing_required)}.")
    await _say(ctx, sender, f"Got it — set `{name}` to `{resolved}`. {tail}")


def _run_submission_sync(job_json: str, filled_json: str, resume_path: str, dry_run: bool, resume_filename: str = "") -> dict:
    """Synchronous core of the submission — run via asyncio.to_thread."""
    try:
        job = json.loads(job_json)
        filled = json.loads(filled_json)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc), "dry_run": dry_run,
                "missing_required": [], "fields_submitted": []}

    board_token = job.get("board_token")
    job_id = job.get("job_id")
    if not board_token or not job_id:
        return {"success": False, "error": "job_json missing board_token / job_id",
                "dry_run": dry_run, "missing_required": [], "fields_submitted": []}

    questions = job.get("questions") or []
    filled_fields = filled.get("filled") or []
    have_resume = bool(resume_path) and Path(resume_path).is_file()

    missing = check_required(questions, filled_fields, have_resume=have_resume)
    if missing:
        return {"success": False, "error": f"Missing required field(s): {', '.join(missing)}",
                "missing_required": missing, "fields_submitted": [], "dry_run": dry_run}

    text_fields, file_field_names = build_payload(filled_fields, questions=questions)
    resume_field = file_field_names[0] if file_field_names else "resume"
    submitted_names = sorted({name for name, _ in text_fields})

    if dry_run or DEFAULT_DRY_RUN:
        return {"success": True, "dry_run": True, "fields_submitted": submitted_names,
                "missing_required": [], "response_body": json.dumps({
                    "url": f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}",
                    "text_fields": text_fields, "resume_field": resume_field,
                    "resume_path": resume_path}, indent=2)}

    if not have_resume:
        return {"success": False, "error": f"Resume file not found at {resume_path!r}",
                "dry_run": False, "missing_required": [], "fields_submitted": []}

    try:
        resp = post_application(board_token, str(job_id), text_fields,
                                resume_path=resume_path, resume_field_name=resume_field,
                                resume_filename=resume_filename or None)
    except SubmitError as exc:
        return {"success": False, "error": str(exc), "dry_run": False,
                "missing_required": [], "fields_submitted": []}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"HTTP error: {exc}", "dry_run": False,
                "missing_required": [], "fields_submitted": []}

    application_id, body_text = parse_response(resp)
    ok = 200 <= resp.status_code < 300
    return {"success": ok, "dry_run": False,
            "application_id": application_id if ok else None,
            "response_status": resp.status_code,
            "response_body": body_text[:2000],
            "fields_submitted": submitted_names if ok else [],
            "missing_required": [],
            "error": None if ok else f"Greenhouse returned HTTP {resp.status_code}"}


async def _do_submit(ctx: Context, sender: str, sess: FormSession, *, dry_run: bool) -> None:
    if sess.missing_required:
        await _say(ctx, sender, f"⚠️ Still need: {', '.join(sess.missing_required)}. Use `answer <name> <value>`.")
        return
    if not sess.job_json:
        await _say(ctx, sender, "No active application — paste a Greenhouse URL to start.")
        return
    sess.state = FormState.SUBMITTING
    form_session.save(ctx.storage, sess)
    await _say(ctx, sender, f"📤 Submitting ({'dry-run' if dry_run else 'live'}) to Greenhouse...")
    filled_payload = {
        "filled": [{"name": f.get("name"), "label": f.get("label", ""), "value": f.get("value"),
                    "source": f.get("source", "user"), "confidence": f.get("confidence", 1.0)}
                   for f in sess.filled if (f.get("ftype") or "").lower() not in {"input_file", "file", "attachment"}],
        "missing_required": sess.missing_required,
    }
    try:
        # Use the original source filename so Greenhouse shows a clean name.
        orch_sess = session_mod.load(ctx.storage, sender)
        active_ver = next(
            (v for v in orch_sess.resume_versions if v.get("name") == orch_sess.active_resume_version),
            None,
        )
        resume_filename = (active_ver or {}).get("source_filename") or ""
        resp = await asyncio.to_thread(
            _run_submission_sync, sess.job_json, json.dumps(filled_payload),
            sess.resume_path or "", dry_run, resume_filename,
        )
    except Exception as exc:  # noqa: BLE001
        sess.state = FormState.REVIEWING
        form_session.save(ctx.storage, sess)
        await _say(ctx, sender, f"❌ Submission failed: {exc}")
        return
    sess.last_submission = resp
    success = resp.get("success", False)
    is_dry = resp.get("dry_run", dry_run)
    if success and not is_dry:
        sess.state = FormState.DONE
        await _close_browser_session(sender)
        orch_sess = session_mod.load(ctx.storage, sender)
        orch_sess.apply_state = ApplyState.DONE
        orch_sess.apply_job_url = None
        session_mod.save(ctx.storage, orch_sess)
    else:
        sess.state = FormState.REVIEWING
    form_session.save(ctx.storage, sess)
    await _say(ctx, sender,
               form_rendering.format_submission_result(
                   dry_run=is_dry, success=success, error=resp.get("error"),
                   application_id=resp.get("application_id"),
                   status_code=resp.get("response_status"),
                   fields_submitted=resp.get("fields_submitted", []),
                   missing_required=resp.get("missing_required", [])),
               end_session=(success and not is_dry))


async def _ff_llm_handle(ctx: Context, sender: str, sess: FormSession, user_text: str) -> None:
    interp = chat_llm.interpret(user_text, chat_llm.build_session_context(sess))
    ctx.logger.info(f"FF-LLM intent={interp.intent!r} field={interp.field!r}")
    if interp.reply:
        await _say(ctx, sender, interp.reply)
    intent = interp.intent
    if intent in {"greet", "smalltalk", "noop", "status"}:
        return
    if intent == "help":
        await _say(ctx, sender, FF_HELP)
        return
    if intent == "show_all":
        await _say(ctx, sender, form_rendering.format_form_panel(sess))
        return
    if intent == "show":
        if interp.field:
            await _say(ctx, sender, form_rendering.format_field_detail(sess, interp.field))
        return
    if intent == "show_payload":
        body = (sess.last_submission or {}).get("response_body")
        if not body:
            await _say(ctx, sender, "Run `submit` (dry-run) first to see the payload.")
        else:
            snippet = body if len(body) <= 1800 else body[:1800] + "\n…(truncated)"
            await _say(ctx, sender, f"```json\n{snippet}\n```")
        return
    if intent == "next":
        await _say(ctx, sender, form_rendering.format_next_missing(sess))
        return
    if intent in {"answer", "edit"}:
        if interp.field and interp.value is not None:
            if _is_generation_request(interp.value):
                target = interp.field if sess.field_meta(interp.field) else None
                await _ff_compose_draft(ctx, sender, sess, target)
            else:
                await _apply_field_edit(ctx, sender, sess, interp.field, interp.value, intent)
        return
    if intent == "unfill":
        if interp.field:
            if not sess.field_meta(interp.field):
                await _say(ctx, sender, f"No field `{interp.field}` on this form.")
                return
            sess.clear_field(interp.field)
            form_session.save(ctx.storage, sess)
            await _say(ctx, sender, f"Cleared `{interp.field}`.")
        return
    if intent == "compose":
        await _ff_compose_draft(ctx, sender, sess, interp.field)
        return
    if intent in {"submit", "submit_live"}:
        await _do_submit(ctx, sender, sess, dry_run=(intent == "submit"))
        return


def _build_profile_context(profile_obj) -> str:
    """Build a text summary from structured profile fields for use when
    resume_text is absent or to supplement it with job-specific context."""
    parts: list[str] = []
    name_parts = filter(None, [profile_obj.first_name, profile_obj.last_name])
    full_name = " ".join(name_parts)
    if full_name:
        parts.append(f"Candidate: {full_name}")
    if profile_obj.work_authorization:
        parts.append(f"Work authorization: {profile_obj.work_authorization}")
    if profile_obj.experience:
        parts.append("\nWork experience:")
        for exp in profile_obj.experience[:4]:
            line = f"- {exp.job_title or 'Role'} at {exp.company_name or 'Company'}"
            if exp.start_date:
                line += f" ({exp.start_date}–{exp.end_date or 'present'})"
            if exp.description:
                line += f"\n  {exp.description[:300]}"
            parts.append(line)
    if profile_obj.education:
        parts.append("\nEducation:")
        for edu in profile_obj.education[:3]:
            parts.append(f"- {edu.degree or ''} {edu.major or ''} — {edu.university_name or ''} ({edu.graduation_date or ''})")
    return "\n".join(parts)


async def _ff_compose_draft(ctx: Context, sender: str, sess: FormSession, requested_field: Optional[str]) -> None:
    name = requested_field
    if not name:
        for fname in sess.missing_required or []:
            meta = sess.field_meta(fname) or {}
            if (meta.get("type") or "").lower() in {"textarea", "input_text"}:
                name = fname
                break
        if not name and sess.missing_required:
            name = sess.missing_required[0]
    if not name or not sess.field_meta(name):
        await _say(ctx, sender, "Tell me which question to draft — `show all` lists field names.")
        return
    meta = sess.field_meta(name) or {}

    # Find the full question object so we have the label + description.
    question: Optional[dict] = None
    for q in (sess.questions or []):
        for f in (q.get("fields") or []):
            if f.get("name") == name:
                question = dict(q)
                question["fields"] = [f]
                break
        if question:
            break
    if not question:
        question = {"label": meta.get("label", name), "description": meta.get("description"),
                    "required": True, "fields": [meta]}

    orch_sess = session_mod.load(ctx.storage, sender)
    user_key = orch_sess.user_key or DEFAULT_USER_KEY
    profile_obj = _profile_store(ctx).get(user_key)
    if profile_obj is None:
        await _say(ctx, sender, "❌ No profile found — set up your profile first.")
        return

    if not _mapper.asi_api_key:
        await _say(ctx, sender, "❌ No ASI:One API key configured — cannot draft answers.")
        return

    # Build the richest context available: resume text + structured profile.
    # This lets the LLM draft answers even when resume_text is absent.
    context_parts: list[str] = []
    if profile_obj.resume_text:
        context_parts.append(profile_obj.resume_text[:3500])
    profile_ctx = _build_profile_context(profile_obj)
    if profile_ctx:
        context_parts.append(profile_ctx)
    context_text = "\n\n".join(context_parts)
    if not context_text:
        await _say(ctx, sender,
                   "❌ No resume or profile data to draft from. Upload your resume first.")
        return

    # Inject job role / company into the question label so the LLM can tailor
    # the answer (e.g. "Why Anthropic?" with "[Role: ML Engineer at Anthropic]").
    question_label = question.get("label") or name
    if sess.job_title or sess.job_company:
        job_ctx = sess.job_title or ""
        if sess.job_company:
            job_ctx = f"{job_ctx} at {sess.job_company}".lstrip(" at ")
        question_label = f"{question_label}  [Role: {job_ctx}]"

    await _say(ctx, sender, f"✍️ Drafting an answer for `{name}`…")
    try:
        draft = await asyncio.to_thread(
            compose_answer,
            question_label=question_label,
            question_desc=question.get("description"),
            resume_text=context_text,
            asi_api_key=_mapper.asi_api_key,
            asi_model=_mapper.asi_model,
        )
    except Exception as exc:  # noqa: BLE001
        await _say(ctx, sender, f"❌ Draft failed: {exc}")
        return
    if not draft:
        await _say(ctx, sender,
                   f"Couldn't generate a draft — try `answer {name} <your text>` to set it manually.")
        return
    await _say(ctx, sender, f"**Draft for `{name}`:**\n\n{draft}\n\nReply `answer {name} <edits>` to save.")


async def _handle_review_command(ctx: Context, sender: str, sess: FormSession, cmd: Command) -> None:
    if cmd.kind == "greet":
        await _ff_llm_handle(ctx, sender, sess, cmd.raw)
        return
    if cmd.kind == "show_all":
        await _say(ctx, sender, form_rendering.format_form_panel(sess))
        return
    if cmd.kind == "show":
        await _say(ctx, sender, form_rendering.format_field_detail(sess, cmd.field_name or ""))
        return
    if cmd.kind == "show_payload":
        body = (sess.last_submission or {}).get("response_body")
        if not body:
            await _say(ctx, sender, "Run `submit` (dry-run) first.")
            return
        snippet = body if len(body) <= 1800 else body[:1800] + "\n…(truncated)"
        await _say(ctx, sender, f"```json\n{snippet}\n```")
        return
    if cmd.kind == "next":
        await _say(ctx, sender, form_rendering.format_next_missing(sess))
        return
    if cmd.kind in {"answer", "edit"}:
        name = cmd.field_name or ""
        value = cmd.value or ""
        if not name or not value:
            await _say(ctx, sender, "Try `answer first_name Aditya`.")
            return
        # If the "value" is an instruction asking the LLM to draft an answer
        # (e.g. "can you answer this in 2 lines based on my profile"), redirect
        # to compose mode. Use the field name when it exists on the form;
        # otherwise fall back to the next missing field (covers "answer this
        # for me…" where field_name="this" is not a real field).
        if _is_generation_request(value):
            target = name if sess.field_meta(name) else None
            await _ff_compose_draft(ctx, sender, sess, target)
            return
        await _apply_field_edit(ctx, sender, sess, name, value, cmd.kind)
        return
    if cmd.kind == "unfill":
        name = cmd.field_name or ""
        if not sess.field_meta(name):
            await _say(ctx, sender, f"No field named `{name}` in this form.")
            return
        sess.clear_field(name)
        form_session.save(ctx.storage, sess)
        await _say(ctx, sender, f"✓ Cleared `{name}`.")
        return
    if cmd.kind in {"submit", "submit_live"}:
        await _do_submit(ctx, sender, sess, dry_run=(cmd.kind == "submit"))
        return
    await _ff_llm_handle(ctx, sender, sess, cmd.raw)


async def _start_application(ctx: Context, sender: str, url: str) -> None:
    sess = FormSession(user_address=sender, state=FormState.EXTRACTING)
    form_session.save(ctx.storage, sess)
    await _say(ctx, sender, f"✓ Fetching job info from\n  {url}")
    try:
        ext: ExtractionResult = await asyncio.to_thread(_extract_job, url)
    except Exception as exc:  # noqa: BLE001
        form_session.clear(ctx.storage, sender)
        await _say(ctx, sender, f"❌ Extraction failed: {exc}")
        return
    if not ext.success or not ext.job:
        form_session.clear(ctx.storage, sender)
        await _say(ctx, sender, f"❌ Extractor error: {ext.error or 'no job returned'}")
        return
    try:
        job = ext.job.model_dump()
        ext_job_json = ext.job.model_dump_json()
    except Exception as exc:  # noqa: BLE001
        form_session.clear(ctx.storage, sender)
        await _say(ctx, sender, f"❌ Could not serialise extractor result: {exc}")
        return
    sess.job_json = ext_job_json
    sess.job_title = job.get("title")
    sess.job_company = job.get("company")
    sess.job_location = job.get("location")
    sess.board_token = job.get("board_token")
    sess.job_id = str(job.get("job_id")) if job.get("job_id") is not None else None
    sess.questions = job.get("questions") or []
    sess.state = FormState.MAPPING
    form_session.save(ctx.storage, sess)
    await _say(ctx, sender, form_rendering.format_job_summary(sess))
    await _say(ctx, sender, "🔍 Pulling your profile and mapping fields…")

    orch_sess = session_mod.load(ctx.storage, sender)
    user_key = orch_sess.user_key or DEFAULT_USER_KEY
    profile_obj = _profile_store(ctx).get(user_key)
    if profile_obj is None:
        sess.state = FormState.IDLE
        form_session.save(ctx.storage, sess)
        hint = "\n\nSet up your profile first — upload your resume or fill in your details."
        await _say(ctx, sender, f"❌ No profile found.{hint}")
        return
    try:
        map_result = await asyncio.to_thread(_mapper.map_questions, profile_obj, sess.questions, user_key=user_key)
        result = json.loads(map_result.model_dump_json())
    except Exception as exc:  # noqa: BLE001
        sess.state = FormState.IDLE
        form_session.save(ctx.storage, sess)
        await _say(ctx, sender, f"❌ Field mapping failed: {exc}")
        return

    sess.filled = []
    for f in (result.get("filled") or []):
        name = f.get("name")
        value = f.get("value")
        meta_for = sess.field_meta(name) if name else None
        opts = (meta_for or {}).get("values") or (meta_for or {}).get("options") or []
        if isinstance(opts, list) and opts and value not in (None, "") and not isinstance(value, list):
            m = match_option(value, opts)
            if m:
                snapped = m["value"] or m["label"]
                if snapped != value:
                    ctx.logger.info(f"option-snap (initial): {name!r} {value!r} → {snapped!r}")
                    value = snapped
        sess.set_field(name, value, source=f.get("source") or "?", confidence=float(f.get("confidence") or 0.0))

    flagged = list(result.get("missing_required") or [])
    filled_names = {f.get("name") for f in sess.filled if f.get("value") not in (None, "", [])}
    derived: list[str] = []
    for q in sess.questions:
        if not q.get("required"):
            continue
        for f in q.get("fields") or []:
            fname = f.get("name")
            if fname and fname not in filled_names and fname not in derived:
                derived.append(fname)
    sess.missing_required = []
    for n in flagged + derived:
        if n not in sess.missing_required:
            sess.missing_required.append(n)

    profile_snapshot = _load_profile(ctx, user_key)
    sess.resume_path = _resolve_resume_path_from_profile(ctx, profile_snapshot)

    if sess.resume_path:
        file_field_name = None
        for q in sess.questions:
            for f in q.get("fields") or []:
                if (f.get("type") or "").lower() in {"input_file", "file", "attachment"}:
                    file_field_name = f.get("name")
                    break
            if file_field_name:
                break
        if file_field_name:
            sess.set_field(file_field_name, sess.resume_path, source="file", confidence=1.0)

    sess.state = FormState.REVIEWING
    form_session.save(ctx.storage, sess)

    await _say(ctx, sender, form_rendering.format_form_panel(sess))

    if LIVE_FILL_MODE != "off" and sess.job_json:
        try:
            job_obj = json.loads(sess.job_json)
            app_url = job_obj.get("application_url") or url
        except Exception:  # noqa: BLE001
            app_url = url
        await _run_live_fill(ctx, sender, sess, app_url, profile_snapshot=profile_snapshot)
        # Save after live fill — it discovers EEO/extra fields and updates
        # missing_required in-memory, but the session was saved before this
        # call so those changes would otherwise be lost on the next message.
        form_session.save(ctx.storage, sess)


async def _handle_form_turn(ctx: Context, sender: str, msg: ChatMessage, user_text: str) -> None:
    """Dispatch a user turn that arrived while apply_state == APPLYING."""
    cmd = parse_command(user_text)
    if cmd.kind == "help":
        await _say(ctx, sender, FF_HELP)
        return
    sess = form_session.load(ctx.storage, sender)
    if sess.state in (FormState.EXTRACTING, FormState.MAPPING, FormState.SUBMITTING):
        await _say(ctx, sender, f"⏳ Still working on the {sess.state.value} step — hang tight.")
        return
    if sess.state in (FormState.IDLE, FormState.DONE):
        await _ff_llm_handle(ctx, sender, sess, user_text)
        return
    await _handle_review_command(ctx, sender, sess, cmd)


async def _start_apply(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    job_url: str,
) -> None:
    """Begin an application: extract and fill directly."""
    sess.apply_state = ApplyState.APPLYING
    sess.apply_job_url = job_url
    session_mod.save(ctx.storage, sess)
    await _start_application(ctx, sender, job_url)


async def _handle_stub(
    ctx: Context, sender: str, intent: str, note: str
) -> None:
    """Placeholder for intents we have planned but not implemented yet."""
    await _say(
        ctx, sender,
        f"🚧 `{intent}` isn't wired up yet — {note}\n\n"
        f"For now, you can say `show my profile`, `help`, or paste a "
        f"Greenhouse URL.",
    )


async def _handle_cancel(
    ctx: Context, sender: str, sess: OrchestratorSession
) -> None:
    if sess.apply_state == ApplyState.APPLYING:
        form_session.clear(ctx.storage, sender)
        await _close_browser_session(sender)

    was_payment_pending = sess.apply_state == ApplyState.PAYMENT_PENDING
    sess.apply_state = ApplyState.IDLE
    sess.apply_job_url = None
    session_mod.save(ctx.storage, sess)
    if was_payment_pending:
        await _say(
            ctx, sender,
            "✓ Cancelled the pending application — no charge.",
        )
    else:
        await _say(
            ctx, sender,
            "✓ Cleared. What would you like to do next?",
        )


# ---------------------------------------------------------------------------
# Payment integration
# ---------------------------------------------------------------------------


async def _on_payment_complete(ctx: Context, user_address: str) -> None:
    """Wired into payment_proto.set_callbacks. Picks up the URL we
    parked at apply-time and resumes the apply handoff."""
    sess = session_mod.load(ctx.storage, user_address)
    parked_url = sess.apply_job_url
    if not parked_url:
        await _say(
            ctx, user_address,
            "✓ Payment received. I lost track of the job URL — please "
            "paste it again to start the application.",
        )
        sess.apply_state = ApplyState.IDLE
        session_mod.save(ctx.storage, sess)
        return

    await _say(
        ctx, user_address,
        "✓ Payment confirmed. Starting your application now…",
    )
    # _start_apply resets apply_state to APPLYING + apply_job_url.
    sess.apply_state = ApplyState.IDLE
    sess.apply_job_url = None
    session_mod.save(ctx.storage, sess)
    await _start_apply(ctx, user_address, sess, parked_url)


async def _on_payment_failed(
    ctx: Context, user_address: str, reason: str
) -> None:
    """Clear the parked URL and tell the user what happened."""
    sess = session_mod.load(ctx.storage, user_address)
    sess.apply_state = ApplyState.IDLE
    sess.apply_job_url = None
    session_mod.save(ctx.storage, sess)

    if reason.startswith("buyer_cancelled"):
        msg = "Payment cancelled — no charge, no application started."
    elif reason.startswith("buyer_rejected"):
        msg = (
            "You rejected the payment. Paste the URL again whenever you "
            "want to retry."
        )
    else:
        msg = (
            "⚠️ Payment couldn't be verified. No application was started "
            "and no charge was made. Paste the URL again to retry."
        )
    await _say(ctx, user_address, msg)


async def _request_payment_for_apply(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    job_url: str,
) -> None:
    """Park the URL on the session, then send the visible payment card."""
    sess.apply_state = ApplyState.PAYMENT_PENDING
    sess.apply_job_url = job_url
    session_mod.save(ctx.storage, sess)
    try:
        await _send_payment_request(ctx, sender)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"failed to send payment card: {exc}")
        sess.apply_state = ApplyState.IDLE
        sess.apply_job_url = None
        session_mod.save(ctx.storage, sess)
        await _say(
            ctx, sender,
            rendering.format_error(
                "Couldn't initiate payment — try again in a moment."
            ),
        )
        return


# ---------------------------------------------------------------------------
# Chat protocol
# ---------------------------------------------------------------------------


async def _handle_chat_impl(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Inner handler — called by handle_chat() which always sends the
    MetadataContent attachment advertisement after this returns."""
    user_text = _extract_text(msg)
    hot_apply_url = intents.find_greenhouse_url(user_text)

    if (
        hot_apply_url
        and payment_mod.gate_active()
    ):
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id
            ),
        )
        sess = session_mod.load(ctx.storage, sender)
        sess.user_key = sess.user_key or DEFAULT_USER_KEY
        sess.apply_state = ApplyState.PAYMENT_PENDING
        sess.apply_job_url = hot_apply_url
        session_mod.save(ctx.storage, sess)
        try:
            await _send_payment_request(ctx, sender)
        except Exception as exc:  # noqa: BLE001
            ctx.logger.error(f"failed to send payment card: {exc}")
            sess.apply_state = ApplyState.IDLE
            sess.apply_job_url = None
            session_mod.save(ctx.storage, sess)
            await _say(
                ctx, sender,
                rendering.format_error(
                    "Couldn't initiate payment — try again in a moment."
                ),
            )
            return
        ctx.logger.info(
            f"Payment-first Greenhouse apply queued for {sender}: "
            f"{hot_apply_url}"
        )
        return

    # ACK first so the user's client knows we received their message.
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id
        ),
    )

    sess = session_mod.load(ctx.storage, sender)
    sess.user_key = sess.user_key or DEFAULT_USER_KEY

    # Card-response intercept: profile list-card click or section-form
    # submission both arrive as MetadataContent and short-circuit the
    # regular intent classifier.
    card_selection = _extract_card_selection(msg)
    if card_selection is not None and card_selection.get("action") in (
        "add_another_education", "save_education",
        "edit_education_entry", "delete_education_entry",
    ):
        await _handle_education_action(ctx, sender, sess, card_selection)
        return
    if card_selection is not None and card_selection.get("action") in (
        "add_another_experience", "save_experience",
        "edit_experience_entry", "delete_experience_entry",
    ):
        await _handle_experience_action(ctx, sender, sess, card_selection)
        return
    if card_selection is not None and ("section" in card_selection or
                                        card_selection.get("action") == "edit_profile"):
        await _handle_profile_card_selection(ctx, sender, sess, card_selection)
        return

    if _is_start_session(msg):
        if not _extract_text(msg):
            await _say(ctx, sender, rendering.WELCOME)
            session_mod.save(ctx.storage, sess)
            return

    has_attachment = _has_attachment(msg)

    # Debug: log the content-type mix on every inbound so we can see what
    # the chat client actually sent (TextContent / ResourceContent / etc).
    ctx.logger.info(
        f"Inbound content types: {[type(c).__name__ for c in msg.content]}"
    )

    ctx.logger.info(
        f"Chat from {sender}: text={user_text!r} attachment={has_attachment} "
        f"apply_state={sess.apply_state.value}"
    )

    # Classify once per turn. The result is reused below for the
    # apply-state passthrough decision *and* the main dispatch — avoids
    # a duplicate ASI:One call.
    interp = intents.interpret(user_text, has_attachment=has_attachment)
    ctx.logger.info(
        f"Intent={interp.intent!r} field={interp.field!r} value={interp.value!r}"
    )

    # Meta verbs always run through the main dispatch (so the user can
    # cancel/show profile/start a new apply mid-flow). Everything else
    # is forwarded to form-filler verbatim while we're applying.
    APPLY_META_VERBS = {
        "cancel", "show_profile", "apply", "list_resumes",
        "switch_resume", "upload_resume",
    }
    if (
        sess.apply_state == ApplyState.APPLYING
        and not has_attachment
        and interp.intent not in APPLY_META_VERBS
    ):
        await _handle_form_turn(ctx, sender, msg, user_text)
        return

    # Conversational LLM reply (warm tone). Skip:
    #   - while waiting on a payment (don't bury the wallet prompt)
    #   - on `upload_resume`: the handler sends its own progress message
    #   - on `greet`: the greet block below sends interp.reply itself to
    #     avoid a duplicate for returning users
    #   Note: `apply` was previously excluded here to avoid burying an
    #   inline payment card, but the payment-gate path returns early above
    #   (lines 2017-2050) so by this point payment is never in play.
    if (
        interp.reply
        and sess.apply_state != ApplyState.PAYMENT_PENDING
        and interp.intent not in {"upload_resume", "greet"}
    ):
        await _say(ctx, sender, interp.reply)

    if interp.intent == "greet":
        # New user: show the full welcome panel.
        # Returning user: use the LLM's warm reply (already in interp.reply).
        if not sess.profile_summary:
            await _say(ctx, sender, rendering.WELCOME)
        elif interp.reply:
            await _say(ctx, sender, interp.reply)
        return

    if interp.intent == "help":
        await _say(ctx, sender, rendering.HELP)
        return

    if interp.intent == "show_profile":
        await _handle_show_profile(ctx, sender, sess)
        return

    if interp.intent == "cancel":
        await _handle_cancel(ctx, sender, sess)
        return

    if interp.intent == "edit_profile":
        if not interp.field or interp.value in (None, ""):
            await _say(
                ctx, sender,
                "Tell me which field and value to set, e.g. "
                "*\"my phone is +1-555-1234\"* or *\"set work auth to US Citizen\"*.",
            )
            return
        await _handle_edit_profile(ctx, sender, sess, interp.field, interp.value)
        return

    if interp.intent == "upload_resume":
        await _handle_upload_resume(ctx, sender, msg, sess, has_attachment=has_attachment)
        return

    if interp.intent == "switch_resume":
        if not interp.value:
            await _say(
                ctx, sender,
                "Tell me which version, e.g. *\"switch resume base\"*. "
                "Say `list resumes` to see what's stored.",
            )
            return
        await _handle_switch_resume(ctx, sender, sess, str(interp.value))
        return

    if interp.intent == "list_resumes":
        await _handle_list_resumes(ctx, sender, sess)
        return

    if interp.intent == "apply":
        if not interp.value:
            await _say(
                ctx, sender,
                "Paste the Greenhouse application URL and I'll start filling "
                "the form.",
            )
            return
        url = str(interp.value)

        # Already applying? Tear down the old session before starting the
        # new one so form-filler doesn't stack URLs.
        if sess.apply_state == ApplyState.APPLYING:
            form_session.clear(ctx.storage, sender)
            await _close_browser_session(sender)
            await _say(
                ctx, sender,
                "_Cancelling the current application and starting the new "
                "one…_",
            )
            sess.apply_state = ApplyState.IDLE
            sess.apply_job_url = None
            session_mod.save(ctx.storage, sess)

        # Already waiting on a payment? Re-park the (possibly new) URL but
        # don't re-send a RequestPayment — the user still has an open one.
        if sess.apply_state == ApplyState.PAYMENT_PENDING:
            sess.apply_job_url = url
            session_mod.save(ctx.storage, sess)
            await _say(
                ctx, sender,
                "You still have a pending payment request. Use the payment "
                "card above, or say `cancel` to abort.",
            )
            return

        if payment_mod.gate_active():
            await _request_payment_for_apply(ctx, sender, sess, url)
            return

        await _start_apply(ctx, sender, sess, url)
        return

    # smalltalk / noop — reply was already sent above; nothing more to do.


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    # The attachment advertisement (MetadataContent) must be sent on every
    # turn so the client can deliver files as ResourceContent.  We send it
    # AFTER responding rather than first, so the platform's native
    # "Putting together a response…" spinner stays visible while we process.
    try:
        await _handle_chat_impl(ctx, sender, msg)
    finally:
        await ctx.send(sender, ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[MetadataContent(type="metadata", metadata={"attachments": "true"})],
        ))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(
    ctx: Context, sender: str, msg: ChatAcknowledgement
) -> None:
    # Nothing to do; logging only.
    ctx.logger.debug(f"ack from {sender} for {msg.acknowledged_msg_id}")


# ---------------------------------------------------------------------------
# Agent lifecycle
# ---------------------------------------------------------------------------


README = """
# Orchestrator Agent

The single user-facing chat entry for the job-application workflow.

- Manage your resume + structured profile by chatting in plain English.
- Paste a Greenhouse URL to start an application — the agent hands off
  into a co-agent that drives the form fill with full visibility.
- Every answer you give during an application is remembered so the next
  application has more pre-filled.
"""


# Wire payment callbacks once, before startup events run.
payment_mod.set_callbacks(
    on_complete=_on_payment_complete,
    on_failed=_on_payment_failed,
)
payment_mod.set_agent_wallet(agent.wallet)


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(
        f"Agent starting: {ctx.agent.name} at {ctx.agent.address}"
    )
    ctx.logger.info(f"default_dry_run={DEFAULT_DRY_RUN}")
    if payment_mod.gate_active():
        ctx.logger.info(
            f"Payment gate ACTIVE — {payment_mod.amount_usd()} per apply via Stripe"
        )
    elif payment_mod.is_enabled():
        ctx.logger.warning(
            "PAYMENT_ENABLED=true but STRIPE_SECRET_KEY is missing; "
            "payment gate is INACTIVE."
        )
    else:
        ctx.logger.info("Payment gate disabled (PAYMENT_ENABLED=false)")

    # Agentverse publication is handled by the Agent constructor. That
    # keeps the published profile in sync with both chat and seller
    # payment manifests; publishing this agent as chat-only makes ASI:One
    # render RequestPayment messages as plain text instead of inline cards.


agent.include(chat_proto, publish_manifest=True)
agent.include(profile_proto, publish_manifest=True)
agent.include(payment_mod.payment_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
