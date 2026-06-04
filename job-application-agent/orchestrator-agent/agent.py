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

import os
import ssl
from datetime import UTC, datetime
from pathlib import Path
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
from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.utils.registration import (  # noqa: E402
    RegistrationRequestCredentials,
    register_chat_agent,
)

import intents  # noqa: E402
import profile_fields  # noqa: E402
import profile_proxy  # noqa: E402
import rendering  # noqa: E402
import session as session_mod  # noqa: E402
from session import ApplyState, OrchestratorSession  # noqa: E402


load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


AGENT_NAME = "job_application_orchestrator"
SEED_PHRASE = os.getenv(
    "ORCHESTRATOR_AGENT_SEED", "orchestrator-agent-user-facing-seed-v1"
)
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
PORT = int(os.getenv("ORCHESTRATOR_AGENT_PORT", "8014"))

PROFILE_ADDR = os.getenv("PROFILE_AGENT_ADDRESS", "")
FORM_FILLER_ADDR = os.getenv("FORM_FILLER_AGENT_ADDRESS", "")
DEFAULT_USER_KEY = os.getenv("DEFAULT_USER_KEY", "me")

PROFILE_TIMEOUT = int(os.getenv("PROFILE_TIMEOUT", "30"))


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

agent = Agent(name=AGENT_NAME, seed=SEED_PHRASE, port=PORT, mailbox=True)
chat_proto = Protocol(spec=chat_protocol_spec)


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


def _extract_text(message: ChatMessage) -> str:
    parts: list[str] = []
    for c in message.content:
        text = getattr(c, "text", None)
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n".join(parts).strip()


def _has_attachment(message: ChatMessage) -> bool:
    """True if any content item looks like a non-text resource (image,
    PDF, etc.)."""
    for c in message.content:
        if getattr(c, "type", "") == "resource":
            return True
    return False


def _is_start_session(message: ChatMessage) -> bool:
    for c in message.content:
        if isinstance(c, StartSessionContent):
            return True
    return False


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------


async def _handle_show_profile(
    ctx: Context, sender: str, sess: OrchestratorSession
) -> None:
    if not PROFILE_ADDR:
        await _say(
            ctx, sender,
            rendering.format_error(
                "I'm not configured to talk to the profile agent yet. "
                "Set PROFILE_AGENT_ADDRESS in orchestrator-agent/.env and "
                "restart me."
            ),
        )
        return

    await _say(ctx, sender, "🔎 Looking up your profile…")
    exists, profile, err = await profile_proxy.fetch_profile(
        ctx, PROFILE_ADDR, sess.user_key
    )
    if err:
        await _say(ctx, sender, rendering.format_error(err))
        return

    panel = rendering.format_profile_summary(
        profile if exists else None,
        active_resume=sess.active_resume_version,
        resume_versions=sess.resume_versions,
    )
    await _say(ctx, sender, panel)

    if exists and profile is not None:
        sess.profile_summary = profile
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
    if not PROFILE_ADDR:
        await _say(
            ctx, sender,
            rendering.format_error(
                "Profile agent not configured — set PROFILE_AGENT_ADDRESS "
                "in orchestrator-agent/.env."
            ),
        )
        return

    field = profile_fields.normalise_field(raw_field)
    if field is None:
        await _say(ctx, sender, rendering.format_field_unknown(raw_field or "?"))
        return

    ok, coerced, err = profile_fields.coerce_value(field, raw_value)
    if not ok:
        await _say(ctx, sender, rendering.format_error(err or "couldn't parse value"))
        return

    # Read-merge-write requires a valid existing profile (UserProfile has
    # required first_name/last_name/email). If there's no profile yet, the
    # user has to bootstrap via resume upload first — clear redirect.
    exists, current, fetch_err = await profile_proxy.fetch_profile(
        ctx, PROFILE_ADDR, sess.user_key
    )
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

    success, upsert_err = await profile_proxy.upsert_profile_patch(
        ctx, PROFILE_ADDR, sess.user_key, {field: coerced}
    )
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
    if sess.apply_state == ApplyState.APPLYING and FORM_FILLER_ADDR:
        # Forward a cancel to the form-filler so it tears down its state.
        try:
            await ctx.send(FORM_FILLER_ADDR, _msg("cancel"))
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(f"cancel forward failed: {exc}")

    sess.apply_state = ApplyState.IDLE
    sess.apply_job_url = None
    session_mod.save(ctx.storage, sess)
    await _say(ctx, sender, "✓ Cleared. What would you like to do next?")


# ---------------------------------------------------------------------------
# Chat protocol
# ---------------------------------------------------------------------------


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    # ACK first so the user's client knows we received their message.
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id
        ),
    )

    sess = session_mod.load(ctx.storage, sender)
    sess.user_key = sess.user_key or DEFAULT_USER_KEY

    if _is_start_session(msg) and not _extract_text(msg):
        await _say(ctx, sender, rendering.WELCOME)
        session_mod.save(ctx.storage, sess)
        return

    user_text = _extract_text(msg)
    has_attachment = _has_attachment(msg)

    ctx.logger.info(
        f"Chat from {sender}: text={user_text!r} attachment={has_attachment}"
    )

    interp = intents.interpret(user_text, has_attachment=has_attachment)
    ctx.logger.info(
        f"Intent={interp.intent!r} field={interp.field!r} value={interp.value!r}"
    )

    # Always send the LLM's reply first when present (warm conversational tone).
    if interp.reply:
        await _say(ctx, sender, interp.reply)

    if interp.intent == "greet":
        # Greet reply already sent; if this is the very first message in the
        # session, follow with the welcome panel to onboard them properly.
        if not sess.profile_summary:
            await _say(ctx, sender, rendering.WELCOME)
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
        await _handle_stub(
            ctx, sender, "upload_resume",
            "attaching a resume in chat is coming in the next commit.",
        )
        return

    if interp.intent == "switch_resume":
        await _handle_stub(
            ctx, sender, "switch_resume",
            "resume versioning is coming in a follow-up commit.",
        )
        return

    if interp.intent == "list_resumes":
        await _handle_stub(
            ctx, sender, "list_resumes",
            "resume versioning is coming in a follow-up commit.",
        )
        return

    if interp.intent == "apply":
        await _handle_stub(
            ctx, sender, "apply",
            "the apply handoff into form-filler is coming next.",
        )
        return

    # smalltalk / noop — reply was already sent above; nothing more to do.


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


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(
        f"Agent starting: {ctx.agent.name} at {ctx.agent.address}"
    )
    ctx.logger.info(
        f"Helpers: profile={PROFILE_ADDR or '(unset)'} "
        f"form_filler={FORM_FILLER_ADDR or '(unset)'}"
    )
    for label, val in [
        ("PROFILE_AGENT_ADDRESS", PROFILE_ADDR),
        ("FORM_FILLER_AGENT_ADDRESS", FORM_FILLER_ADDR),
    ]:
        if not val:
            ctx.logger.warning(
                f"{label} is not set — set it in orchestrator-agent/.env"
            )

    if not AGENTVERSE_API_KEY:
        ctx.logger.warning(
            "AGENTVERSE_API_KEY not set — skipping Agentverse registration"
        )
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
                "User-facing job-application orchestrator. Manage your "
                "resume + profile, then paste a Greenhouse URL to apply."
            ),
        )
        ctx.logger.info("Registered with Agentverse")
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Failed to register with Agentverse: {exc}")


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
