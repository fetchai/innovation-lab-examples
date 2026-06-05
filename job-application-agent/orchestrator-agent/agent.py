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
from uagents import Agent, Context, Protocol  # noqa: E402
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

import intents  # noqa: E402
import payment_proto as payment_mod  # noqa: E402
import profile_fields  # noqa: E402
import profile_proxy  # noqa: E402
import rendering  # noqa: E402
import resume_store  # noqa: E402
import session as session_mod  # noqa: E402
from session import ApplyState, OrchestratorSession  # noqa: E402


load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


AGENT_NAME = "job_application_orchestrator"
SEED_PHRASE = os.getenv(
    "ORCHESTRATOR_AGENT_SEED", "orchestrator-agent-user-facing-seed-v1"
)
PORT = int(os.getenv("ORCHESTRATOR_AGENT_PORT", "8014"))

PROFILE_ADDR = os.getenv("PROFILE_AGENT_ADDRESS", "")
FORM_FILLER_ADDR = os.getenv("FORM_FILLER_AGENT_ADDRESS", "")
DEFAULT_USER_KEY = os.getenv("DEFAULT_USER_KEY", "me")

PROFILE_TIMEOUT = int(os.getenv("PROFILE_TIMEOUT", "30"))
INGEST_TIMEOUT = int(os.getenv("INGEST_TIMEOUT", "120"))

AGENTVERSE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai")
STORAGE_URL = f"{AGENTVERSE_URL}/v1/storage"


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

agent = Agent(
    name=AGENT_NAME,
    seed=SEED_PHRASE,
    port=PORT,
    network="testnet",
    mailbox=True,
    agentverse=AGENTVERSE_URL,
    publish_agent_details=True,
)
chat_proto = Protocol(spec=chat_protocol_spec)


# Apply proxy state. The orchestrator forwards a user's chat messages
# into form-filler-agent's session and relays form-filler's replies
# back. Form-filler keys sessions by sender, so all proxied applications
# share *one* form-filler session at a time.
_active_apply_user: Optional[str] = None


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


_MY_MENTION_RE = re.compile(r"^\s*@agent1[a-z0-9]{50,}\s*", re.IGNORECASE)


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


def _resource_items(message: ChatMessage) -> list[ResourceContent]:
    return [c for c in message.content if isinstance(c, ResourceContent)]


def _has_end_session(message: ChatMessage) -> bool:
    return any(isinstance(c, EndSessionContent) for c in message.content)


def _download_resource(
    ctx: Context, item: ResourceContent
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

    # 1) Agentverse external storage
    try:
        storage = ExternalStorage(
            identity=ctx.agent.identity, storage_url=STORAGE_URL
        )
        stored = storage.download(str(item.resource_id))
        mime_type = stored.get("mime_type", mime_type)
        content_b64 = stored.get("contents", "")
        if content_b64:
            content_bytes = base64.b64decode(content_b64)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.info(
            f"storage download failed for {item.resource_id} ({exc}); "
            f"trying URI fallback"
        )

    # 2) Public URI fallback. `item.resource` may be a single Resource
    # object (current chat clients) or a list of them (older protocol).
    if content_bytes is None:
        uri = None
        res_obj = getattr(item, "resource", None)
        candidates = res_obj if isinstance(res_obj, list) else [res_obj]
        for res in candidates:
            uri = getattr(res, "uri", None) if res is not None else None
            if uri:
                break
        if uri:
            try:
                import httpx  # local import keeps the top of the file unchanged
                resp = httpx.get(uri, timeout=120)
                resp.raise_for_status()
                content_bytes = resp.content
                mime_type = resp.headers.get("content-type", mime_type)
            except Exception as exc:  # noqa: BLE001
                ctx.logger.warning(f"URI download failed ({uri}): {exc}")
                return None
        else:
            ctx.logger.warning(
                f"resource {item.resource_id}: no storage bytes and no URI"
            )
            return None

    # Try to recover the original filename from the resource metadata
    # (set by chat clients) or fall back to the asset id.
    source_filename = f"resource_{item.resource_id}"
    res_obj = getattr(item, "resource", None)
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

    if not PROFILE_ADDR:
        await _say(ctx, sender, rendering.format_error(
            "Profile agent not configured (PROFILE_AGENT_ADDRESS missing)."
        ))
        return

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

        ok, err = await profile_proxy.upsert_profile_patch(
            ctx, PROFILE_ADDR, sess.user_key, patch
        )
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

    card = rendering.build_profile_list_card(
        profile if exists else None,
        active_resume=sess.active_resume_version,
        resume_versions=sess.resume_versions,
    )
    await _send_card(ctx, sender, card, caption="Here's your profile — tap any section to edit.")

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


async def _handle_upload_resume(
    ctx: Context,
    sender: str,
    msg: ChatMessage,
    sess: OrchestratorSession,
) -> None:
    """Download every ResourceContent attachment on the message, save the
    bytes locally, call profile-agent.IngestResume on each, and register
    the version in `sess.resume_versions`. Also flips the new version to
    `active_resume_version` and (when there's an existing profile) syncs
    `profile.resume_path` so the form-filler picks it up automatically."""
    if not PROFILE_ADDR:
        await _say(
            ctx, sender,
            rendering.format_error(
                "Profile agent not configured — set PROFILE_AGENT_ADDRESS "
                "in orchestrator-agent/.env."
            ),
        )
        return

    resources = _resource_items(msg)
    if not resources:
        await _say(
            ctx, sender,
            "Drop a PDF, DOCX, or TXT resume in chat and I'll parse it.",
        )
        return

    ingested: list[dict] = []
    for item in resources:
        downloaded = _download_resource(ctx, item)
        if not downloaded:
            await _say(
                ctx, sender,
                rendering.format_error(
                    f"Couldn't download attachment `{item.resource_id}`."
                ),
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

        # Hand the saved path to the profile-agent for parsing + RAG indexing.
        success, resp, err = await profile_proxy.ingest_resume(
            ctx,
            PROFILE_ADDR,
            sess.user_key,
            version_entry["path"],
            timeout=INGEST_TIMEOUT,
        )
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
        ingested.append({**version_entry, "ingest_response": resp})

        chunks = resp.chunks_indexed if resp else None
        chars = resp.chars_extracted if resp else None
        details = []
        if chars:
            details.append(f"{chars} chars extracted")
        if chunks:
            details.append(f"{chunks} chunks indexed")
        tail = " · ".join(details) if details else "indexed"
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

    # Sync the profile's `resume_path` so form-filler picks the new one
    # automatically. Best-effort: if the profile doesn't exist yet, skip.
    exists, _, _ = await profile_proxy.fetch_profile(
        ctx, PROFILE_ADDR, sess.user_key
    )
    if exists and PROFILE_ADDR:
        ok, err = await profile_proxy.upsert_profile_patch(
            ctx, PROFILE_ADDR, sess.user_key,
            {"resume_path": target["path"]},
        )
        if not ok:
            ctx.logger.warning(f"switch_resume: profile sync failed: {err}")

    await _say(
        ctx, sender,
        f"✓ Active resume is now `{target['name']}` "
        f"(`{target.get('source_filename', '')}`).",
    )


# ---------------------------------------------------------------------------
# Apply proxy
# ---------------------------------------------------------------------------


async def _forward_to_form_filler(ctx: Context, text: str) -> bool:
    """Send a plain TextContent message to the form-filler agent. Returns
    True on success."""
    if not FORM_FILLER_ADDR:
        return False
    try:
        await ctx.send(FORM_FILLER_ADDR, _msg(text))
        return True
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"forward to form-filler failed: {exc}")
        return False


async def _start_apply(
    ctx: Context,
    sender: str,
    sess: OrchestratorSession,
    job_url: str,
) -> None:
    """Begin an application: hand the URL off to form-filler-agent and
    register `sender` as the active proxied user."""
    global _active_apply_user
    if not FORM_FILLER_ADDR:
        await _say(
            ctx, sender,
            rendering.format_error(
                "Form-filler agent not configured — set "
                "FORM_FILLER_AGENT_ADDRESS in orchestrator-agent/.env."
            ),
        )
        return

    sess.apply_state = ApplyState.APPLYING
    sess.apply_job_url = job_url
    session_mod.save(ctx.storage, sess)
    _active_apply_user = sender

    sent = await _forward_to_form_filler(ctx, job_url)
    if not sent:
        sess.apply_state = ApplyState.IDLE
        sess.apply_job_url = None
        session_mod.save(ctx.storage, sess)
        _active_apply_user = None
        await _say(
            ctx, sender,
            rendering.format_error("Couldn't reach the form-filler agent."),
        )


async def _forward_user_followup(
    ctx: Context, sender: str, user_text: str
) -> None:
    """While an application is in flight, plain-text user turns get
    forwarded verbatim to form-filler."""
    global _active_apply_user
    _active_apply_user = sender  # refresh in case of agent restart
    sent = await _forward_to_form_filler(ctx, user_text)
    if not sent:
        await _say(
            ctx, sender,
            rendering.format_error(
                "Lost the connection to the form-filler agent — say "
                "`cancel` to reset."
            ),
        )


async def _relay_from_form_filler(ctx: Context, msg: ChatMessage) -> None:
    """An inbound ChatMessage from FORM_FILLER_ADDR. Relay its content
    to whichever user is currently applying.

    ResourceContent attachments are permission-scoped to the
    orchestrator's identity by ExternalStorage, so the user's chat
    client can't download them. Strip them out and surface a short text
    note instead. (Form-filler's screenshots are already delivered as
    catbox markdown inside TextContent in the happy path, so dropping
    these is usually a no-op.)"""
    global _active_apply_user
    if not _active_apply_user:
        ctx.logger.warning(
            "received form-filler reply but no active apply user; dropping"
        )
        return

    relayed_content: list = []
    dropped = 0
    for c in msg.content:
        if isinstance(c, ResourceContent):
            dropped += 1
            continue
        relayed_content.append(c)
    if dropped:
        ctx.logger.info(
            f"relay: stripped {dropped} ResourceContent item(s) from "
            f"form-filler"
        )
        relayed_content.append(TextContent(
            type="text",
            text=(
                f"_(form-filler sent {dropped} attachment(s) I can't relay "
                f"through; the inline screenshots above are still up to "
                f"date.)_"
            ),
        ))

    if not relayed_content:
        ctx.logger.warning(
            "relay: nothing to forward after filtering; skipping send"
        )
    else:
        relayed = ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=relayed_content,
        )
        try:
            await ctx.send(_active_apply_user, relayed)
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(
                f"relay to {_active_apply_user} failed: {exc}"
            )

    if _has_end_session(msg):
        sess = session_mod.load(ctx.storage, _active_apply_user)
        sess.apply_state = ApplyState.DONE
        sess.apply_job_url = None
        session_mod.save(ctx.storage, sess)
        _active_apply_user = None


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
    global _active_apply_user
    if sess.apply_state == ApplyState.APPLYING and FORM_FILLER_ADDR:
        await _forward_to_form_filler(ctx, "cancel")

    was_payment_pending = sess.apply_state == ApplyState.PAYMENT_PENDING
    sess.apply_state = ApplyState.IDLE
    sess.apply_job_url = None
    session_mod.save(ctx.storage, sess)
    if _active_apply_user == sender:
        _active_apply_user = None

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
    """Park the URL on the session, then send a RequestPayment. The
    matching CommitPayment will be handled by payment_proto and (on
    verify success) call back into `_on_payment_complete` which
    invokes `_start_apply`."""
    sess.apply_state = ApplyState.PAYMENT_PENDING
    sess.apply_job_url = job_url
    session_mod.save(ctx.storage, sess)
    try:
        await payment_mod.request_payment_from_user(ctx, sender)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"failed to send RequestPayment: {exc}")
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
    # No TextContent before or after the RequestPayment. The official
    # doc's pattern (innovationlab.fetch.ai/.../fet-image-agent-payment-protocol)
    # is: ACK → request_payment_from_user → return. Any extra bubble in
    # the same turn blocks the inline payment card render.


# ---------------------------------------------------------------------------
# Chat protocol
# ---------------------------------------------------------------------------


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    user_text = _extract_text(msg)
    hot_apply_url = intents.find_greenhouse_url(user_text)

    # ASI:One's native payment renderer is extremely timing-sensitive:
    # the RequestPayment must be the first thing the chat turn emits. For
    # a pasted Greenhouse URL, bypass all normal bookkeeping until the
    # payment envelope is already on the wire.
    if (
        hot_apply_url
        and sender != FORM_FILLER_ADDR
        and payment_mod.gate_active()
    ):
        try:
            await payment_mod.request_payment_from_user(ctx, sender)
        except Exception as exc:  # noqa: BLE001
            ctx.logger.error(f"failed to send RequestPayment: {exc}")
            await ctx.send(
                sender,
                ChatAcknowledgement(
                    timestamp=datetime.now(UTC),
                    acknowledged_msg_id=msg.msg_id,
                ),
            )
            await _say(
                ctx, sender,
                rendering.format_error(
                    "Couldn't initiate payment — try again in a moment."
                ),
            )
            return

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

    # Inbound from the form-filler agent: relay verbatim to the active
    # applying user. Never run intent classification on these.
    if FORM_FILLER_ADDR and sender == FORM_FILLER_ADDR:
        await _relay_from_form_filler(ctx, msg)
        return

    sess = session_mod.load(ctx.storage, sender)
    sess.user_key = sess.user_key or DEFAULT_USER_KEY

    # Card-response intercept: profile list-card click or section-form
    # submission both arrive as MetadataContent and short-circuit the
    # regular intent classifier.
    card_selection = _extract_card_selection(msg)
    if card_selection is not None and "section" in card_selection:
        await _handle_profile_card_selection(ctx, sender, sess, card_selection)
        return

    if _is_start_session(msg):
        # Advertise attachment support. Without this the chat client
        # uploads files as MetadataContent stubs (or skips them entirely)
        # instead of as ResourceContent, so `_handle_upload_resume` never
        # sees any bytes to ingest.
        await ctx.send(sender, ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid4(),
            content=[MetadataContent(type="metadata",
                                     metadata={"attachments": "true"})],
        ))
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
        await _forward_user_followup(ctx, sender, user_text)
        return

    # Conversational LLM reply (warm tone). Skip:
    #   - while waiting on a payment (don't bury the wallet prompt)
    #   - on `apply` intent (sending a TextContent bubble between the ACK
    #     and the RequestPayment causes the chat client to skip rendering
    #     the inline payment card — matches duffel-agent's pattern of
    #     going ACK → RequestPayment with no intervening text).
    if (
        interp.reply
        and sess.apply_state != ApplyState.PAYMENT_PENDING
        and interp.intent != "apply"
    ):
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
        await _handle_upload_resume(ctx, sender, msg, sess)
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
            if FORM_FILLER_ADDR:
                await _forward_to_form_filler(ctx, "cancel")
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
                "💳 You still have a pending payment request. Confirm or "
                "reject it in your wallet — I'll start as soon as that "
                "settles. (Or say `cancel` to abort.)",
            )
            return

        if payment_mod.gate_active():
            await _request_payment_for_apply(ctx, sender, sess, url)
            return

        await _start_apply(ctx, sender, sess, url)
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
    ctx.logger.info(
        f"Helpers: profile={PROFILE_ADDR or '(unset)'} "
        f"form_filler={FORM_FILLER_ADDR or '(unset)'}"
    )
    if payment_mod.gate_active():
        net = "testnet" if payment_mod.use_testnet() else "mainnet"
        ctx.logger.info(
            f"Payment gate ACTIVE — {payment_mod.amount_fet()} FET per apply "
            f"({net}), recipient={payment_mod.recipient_fet_address(ctx)}"
        )
    elif payment_mod.is_enabled():
        ctx.logger.warning(
            "PAYMENT_ENABLED=true but the agent wallet wasn't wired; "
            "payment gate is INACTIVE."
        )
    else:
        ctx.logger.info("Payment gate disabled (PAYMENT_ENABLED=false)")
    for label, val in [
        ("PROFILE_AGENT_ADDRESS", PROFILE_ADDR),
        ("FORM_FILLER_AGENT_ADDRESS", FORM_FILLER_ADDR),
    ]:
        if not val:
            ctx.logger.warning(
                f"{label} is not set — set it in orchestrator-agent/.env"
            )

    # Agentverse publication is handled by the Agent constructor. That
    # keeps the published profile in sync with both chat and seller
    # payment manifests; publishing this agent as chat-only makes ASI:One
    # render RequestPayment messages as plain text instead of inline cards.


agent.include(chat_proto, publish_manifest=True)
agent.include(payment_mod.payment_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
