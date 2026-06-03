"""Form-Filler Agent — the user-facing entry point.

The user pastes a Greenhouse URL in chat. The agent calls the extractor,
profile, and submitter helpers via `ctx.send_and_receive`, streaming
intermediate `ChatMessage` updates between calls so the user watches the
form fill in real time. The user can edit values, supply missing fields,
and explicitly type `submit` to send (`submit live` to actually post —
plain `submit` runs a safe dry-run).

Per-user session state is persisted in `ctx.storage` (see `session.py`).
"""

import asyncio
import json
import os
import ssl
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import certifi

# Force Playwright to use the user's persistent browser cache (not whatever
# transient $PLAYWRIGHT_BROWSERS_PATH a parent shell may have leaked in).
_user_pw_cache = os.path.expanduser("~/Library/Caches/ms-playwright")
if os.path.isdir(_user_pw_cache):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _user_pw_cache
else:
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)

# python.org Python on macOS ships without a usable system cert bundle, which
# breaks the agent's mailbox websocket. Patch ssl.create_default_context to
# trust certifi BEFORE aiohttp is imported. Same pattern as the helper agents.
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
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.utils.registration import (  # noqa: E402
    RegistrationRequestCredentials,
    register_chat_agent,
)

import chat_assets  # noqa: E402
import chat_llm  # noqa: E402
import clients  # noqa: E402
import rendering  # noqa: E402
import session as session_mod  # noqa: E402
from browser_filler import FillEvent, live_fill  # noqa: E402
from commands import Command, parse as parse_command  # noqa: E402
from session import Session, State  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


AGENT_NAME = "job_application_form_filler"
SEED_PHRASE = os.getenv("FORM_FILLER_AGENT_SEED", "form-filler-agent-user-facing-seed-v1")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
PORT = int(os.getenv("FORM_FILLER_AGENT_PORT", "8013"))

EXTRACTOR_ADDR = os.getenv("EXTRACTOR_AGENT_ADDRESS", "")
PROFILE_ADDR = os.getenv("PROFILE_AGENT_ADDRESS", "")
SUBMITTER_ADDR = os.getenv("SUBMITTER_AGENT_ADDRESS", "")
DEFAULT_USER_KEY = os.getenv("DEFAULT_USER_KEY", "me")
DEFAULT_RESUME_PATH = os.getenv("DEFAULT_RESUME_PATH", "")

EXTRACTOR_TIMEOUT = int(os.getenv("EXTRACTOR_TIMEOUT", "30"))
PROFILE_TIMEOUT = int(os.getenv("PROFILE_TIMEOUT", "90"))
SUBMITTER_TIMEOUT = int(os.getenv("SUBMITTER_TIMEOUT", "60"))

# Live form-fill (Playwright). Modes:
#   off    — skip the browser entirely; chat just shows the text panel.
#   chat   — headless Chromium, screenshots streamed to the chat.
#   headed — visible Chromium on the user's machine AND screenshots in chat.
LIVE_FILL_MODE = os.getenv("LIVE_FILL_MODE", "headed").strip().lower()
LIVE_FILL_SCREENSHOT_EVERY = int(os.getenv("LIVE_FILL_SCREENSHOT_EVERY", "3"))


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


async def _say(ctx: Context, sender: str, text: str, *, end_session: bool = False) -> None:
    await ctx.send(sender, _msg(text, end_session=end_session))


# ---------------------------------------------------------------------------
# Welcome / help text
# ---------------------------------------------------------------------------


WELCOME = (
    "Hey 👋 paste a Greenhouse job link and I'll fill it out for you live — "
    "you'll see every field before anything gets submitted. Need a hand? "
    "Just ask."
)

HELP = (
    "**Commands**\n"
    "• Paste a Greenhouse URL — start a new application.\n"
    "• `show <name>`              — full value of one field\n"
    "• `show all` / `form`        — re-print the form preview\n"
    "• `answer <name> <value>`    — fill a missing field\n"
    "• `edit <name> <value>`      — change a filled value\n"
    "• `unfill <name>`            — clear a field\n"
    "• `next`                     — show the next missing field's prompt\n"
    "• `submit`                   — dry-run (preview the payload, nothing sent)\n"
    "• `submit live`              — actually post to Greenhouse\n"
    "• `show payload`             — dump the prepared submitter payload\n"
    "• `cancel`                   — discard the active session"
)


# ---------------------------------------------------------------------------
# Profile save-back: persist user edits back to the profile so the next
# application reuses them.
# ---------------------------------------------------------------------------


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


def _match_structured_attr(field_name: str, label: str) -> Optional[str]:
    blob = f"{field_name} {label}".lower()
    for attr, hints in _STRUCTURED_FIELD_HINTS.items():
        for h in hints:
            if h in blob:
                return attr
    return None


async def _save_edit_to_profile(
    ctx: Context, *, label: str, field_name: str, value: str
) -> None:
    """Best-effort save-back: store the user's answer in the profile so a
    future application can reuse it. Failures are logged but don't surface to
    the user — the in-session form edit already succeeded."""
    if not PROFILE_ADDR:
        return
    try:
        get_resp = await clients.call_get_profile(
            ctx, PROFILE_ADDR, DEFAULT_USER_KEY, timeout=15
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"save-back: GetProfile failed: {exc}")
        return

    profile: dict = {}
    if get_resp.success and get_resp.profile_json:
        try:
            profile = json.loads(get_resp.profile_json)
        except Exception:  # noqa: BLE001
            profile = {}

    attr = _match_structured_attr(field_name, label)
    if attr:
        profile[attr] = value
        ctx.logger.info(f"save-back: setting profile.{attr}")
    else:
        canned = profile.get("canned_answers") or {}
        # Key on the question label (human-readable). Fall back to field_name.
        key = (label or field_name).strip()
        canned[key] = value
        profile["canned_answers"] = canned
        ctx.logger.info(f"save-back: storing canned_answers[{key!r}]")

    try:
        await clients.call_upsert_profile(
            ctx, PROFILE_ADDR, DEFAULT_USER_KEY, json.dumps(profile), timeout=15
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"save-back: UpsertProfile failed: {exc}")


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


async def _start_application(ctx: Context, sender: str, url: str) -> None:
    sess = Session(user_address=sender, state=State.EXTRACTING)
    session_mod.save(ctx.storage, sess)

    await _say(ctx, sender, f"✓ Fetching job info from\n  {url}")

    try:
        ext = await clients.call_extractor(
            ctx, EXTRACTOR_ADDR, url, timeout=EXTRACTOR_TIMEOUT
        )
    except Exception as exc:  # noqa: BLE001
        session_mod.clear(ctx.storage, sender)
        await _say(ctx, sender, f"❌ Couldn't reach the extractor: {exc}")
        return

    if not ext.success or not ext.job_json:
        session_mod.clear(ctx.storage, sender)
        await _say(ctx, sender, f"❌ Extractor error: {ext.error or 'no job_json returned'}")
        return

    try:
        job = json.loads(ext.job_json)
    except Exception as exc:  # noqa: BLE001
        session_mod.clear(ctx.storage, sender)
        await _say(ctx, sender, f"❌ Could not parse extractor response: {exc}")
        return

    sess.job_json = ext.job_json
    sess.job_title = job.get("title")
    sess.job_company = job.get("company")
    sess.job_location = job.get("location")
    sess.board_token = job.get("board_token")
    sess.job_id = str(job.get("job_id")) if job.get("job_id") is not None else None
    sess.questions = job.get("questions") or []
    sess.state = State.MAPPING
    session_mod.save(ctx.storage, sess)

    await _say(ctx, sender, rendering.format_job_summary(sess))
    await _say(ctx, sender, "🔍 Pulling your profile and mapping fields (this uses RAG + ASI:One)...")

    # Map fields via the profile agent.
    try:
        map_resp = await clients.call_map_fields(
            ctx,
            PROFILE_ADDR,
            DEFAULT_USER_KEY,
            json.dumps(sess.questions),
            timeout=PROFILE_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        sess.state = State.IDLE
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, f"❌ Couldn't reach the profile agent: {exc}")
        return

    if not map_resp.success or not map_resp.result_json:
        sess.state = State.IDLE
        session_mod.save(ctx.storage, sess)
        hint = ""
        if map_resp.error and "No profile" in map_resp.error:
            hint = (
                "\n\nIt looks like you haven't set up a profile yet. "
                "Talk to the **Profile Agent** first to save your resume + "
                "name/email/etc., then come back here."
            )
        await _say(ctx, sender, f"❌ MapFields failed: {map_resp.error or 'unknown'}{hint}")
        return

    try:
        result = json.loads(map_resp.result_json)
    except Exception as exc:  # noqa: BLE001
        sess.state = State.IDLE
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, f"❌ Could not parse MapFields result: {exc}")
        return

    # Hydrate session.filled and missing_required from the result.
    sess.filled = []
    for f in (result.get("filled") or []):
        sess.set_field(
            f.get("name"),
            f.get("value"),
            source=f.get("source") or "?",
            confidence=float(f.get("confidence") or 0.0),
        )

    # `missing_required`: union of (a) what the profile agent flagged and
    # (b) any required question we still don't have a non-empty value for.
    flagged = list(result.get("missing_required") or [])
    filled_names = {
        f.get("name") for f in sess.filled
        if f.get("value") not in (None, "", [])
    }
    derived: list[str] = []
    for q in sess.questions:
        if not q.get("required"):
            continue
        for f in q.get("fields") or []:
            fname = f.get("name")
            if not fname or fname in filled_names:
                continue
            if fname not in derived:
                derived.append(fname)
    # Combine, preserving order; flagged first.
    sess.missing_required = []
    for n in flagged + derived:
        if n not in sess.missing_required:
            sess.missing_required.append(n)

    # Resume path: prefer env override, otherwise read the profile agent's
    # stored resume_path field for this user.
    if DEFAULT_RESUME_PATH:
        sess.resume_path = DEFAULT_RESUME_PATH
    else:
        # The profile agent stores resume_path on the UserProfile; fetch it now.
        try:
            prof_resp = await clients.call_get_profile(
                ctx, PROFILE_ADDR, DEFAULT_USER_KEY, timeout=15
            )
            if prof_resp.success and prof_resp.profile_json:
                prof = json.loads(prof_resp.profile_json)
                sess.resume_path = prof.get("resume_path")
        except Exception as exc:  # noqa: BLE001
            ctx.logger.warning(f"Could not load profile to read resume_path: {exc}")

    # Show the resume as a "filled" file field for visibility, if there is one.
    if sess.resume_path:
        file_field_name = None
        for q in sess.questions:
            for f in q.get("fields") or []:
                if (f.get("type") or "").lower() in {"input_file", "file"}:
                    file_field_name = f.get("name")
                    break
            if file_field_name:
                break
        if file_field_name:
            sess.set_field(
                file_field_name,
                Path(sess.resume_path).name,
                source="file",
                confidence=1.0,
            )

    # ---- Live form fill (Playwright) ------------------------------------
    # Pre-`REVIEWING` step: drive the real Greenhouse page in Chromium so
    # the user actually sees the form populate. Failures fall back to the
    # text panel.
    live_fill_succeeded = False
    if LIVE_FILL_MODE != "off":
        application_url = (
            job.get("job_board_url")
            or job.get("apply_url")
            or job.get("url")
            or url
        )
        if application_url:
            live_fill_succeeded = await _run_live_fill(
                ctx, sender, sess, application_url
            )

    sess.state = State.REVIEWING
    session_mod.save(ctx.storage, sess)

    # If the live-fill streamed screenshots, that IS the form preview — we
    # just add a compact one-liner under it so the user knows the score and
    # what's left. Only fall back to the full text panel if Playwright was
    # disabled or the live-fill itself failed.
    if live_fill_succeeded:
        await _say(ctx, sender, rendering.format_panel_compact(sess))
    else:
        await _say(ctx, sender, rendering.format_panel(sess))
        await _say(
            ctx, sender,
            rendering.format_commands_hint(
                have_missing=bool(sess.missing_required)
            ),
        )


async def _run_live_fill(
    ctx: Context, sender: str, sess: Session, application_url: str
) -> bool:
    """Stream the actual Greenhouse form filling into the chat as a sequence
    of text + screenshot ChatMessages. Best-effort: returns True if at least
    one screenshot was streamed (so the caller can skip the verbose text
    fallback), False otherwise."""
    headed = LIVE_FILL_MODE == "headed"
    mode_note = (
        "I'll also pop a Chrome window on your machine so you can watch / "
        "interact directly."
        if headed
        else "I'll stream screenshots into the chat as it fills."
    )

    await _say(
        ctx, sender,
        f"🎬 Opening the real Greenhouse form so you can see it fill. {mode_note}",
    )

    streamed_any = False

    # Build the list the browser filler iterates. Skip file fields here —
    # they're attached separately using sess.resume_path.
    fillables = []
    for f in sess.filled:
        ftype = (f.get("ftype") or "").lower()
        if ftype in {"input_file", "file"}:
            # Insert the file field FIRST so users see the attach early.
            fillables.insert(0, f)
        else:
            fillables.append(f)

    try:
        async for event in live_fill(
            application_url,
            fillables,
            resume_path=sess.resume_path,
            headless=not headed,
            screenshot_every_n_fields=LIVE_FILL_SCREENSHOT_EVERY,
        ):
            sent_image = await _handle_fill_event(ctx, sender, event)
            if sent_image:
                streamed_any = True
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"live fill failed: {exc}")
        await _say(
            ctx, sender,
            f"⚠️ Couldn't render the live form: {exc}. The form is still "
            "filled out behind the scenes — I'll show it as text instead.",
        )
        return False

    return streamed_any


async def _handle_fill_event(ctx: Context, sender: str, event: FillEvent) -> bool:
    """Translate one `FillEvent` into a chat message (text and/or screenshot).
    Returns True if a screenshot was actually delivered to chat — used by
    the caller to decide whether to fall back to the verbose text panel."""
    if event.kind == "started":
        ctx.logger.info(f"live-fill: {event.message}")
        return False

    if event.kind == "field_filled":
        ctx.logger.info(f"live-fill: filled {event.field_name!r} ({event.message})")
        return False

    if event.kind == "field_skipped":
        ctx.logger.info(
            f"live-fill: skipped {event.field_name!r} ({event.message})"
        )
        return False

    if event.kind in {"screenshot", "done"}:
        if not event.screenshot_png:
            return False

        caption = ("📸 " + event.message) if event.message else None
        uploaded = chat_assets.upload_image(
            event.screenshot_png,
            name_prefix="form-fill",
            mime_type="image/png",
            grant_to_address=sender,
        )
        if uploaded:
            asset_id, asset_uri = uploaded
            try:
                await ctx.send(
                    sender,
                    chat_assets.make_image_message(
                        asset_id, asset_uri, caption=caption
                    ),
                )
                return True
            except Exception as exc:  # noqa: BLE001
                ctx.logger.warning(f"failed to send image message: {exc}")
        # Fallback: just send the caption text so user knows progress.
        if caption:
            await _say(ctx, sender, caption)
        return False

    if event.kind == "error":
        await _say(ctx, sender, f"⚠️ live-fill: {event.error}")
        return False

    return False


# ---------------------------------------------------------------------------
# REVIEWING-state command handlers
# ---------------------------------------------------------------------------


async def _handle_review_command(
    ctx: Context, sender: str, sess: Session, cmd: Command
) -> None:
    if cmd.kind == "greet":
        # Route greetings through the LLM so they feel chatty + contextual.
        await _llm_handle(ctx, sender, sess, cmd.raw)
        return

    if cmd.kind == "show_all":
        await _say(ctx, sender, rendering.format_panel(sess))
        return

    if cmd.kind == "show":
        name = cmd.field_name or ""
        await _say(ctx, sender, rendering.format_field_detail(sess, name))
        return

    if cmd.kind == "show_payload":
        last = sess.last_submission or {}
        body = last.get("response_body")
        if not body:
            await _say(
                ctx, sender,
                "No prepared payload yet — run `submit` (dry-run) first.",
            )
            return
        snippet = body
        if len(snippet) > 1800:
            snippet = snippet[:1800] + "\n…(truncated)"
        await _say(ctx, sender, f"```json\n{snippet}\n```")
        return

    if cmd.kind == "next":
        await _say(ctx, sender, rendering.format_next_missing(sess))
        return

    if cmd.kind in {"answer", "edit"}:
        name = cmd.field_name or ""
        value = cmd.value or ""
        if not name or not value:
            await _say(ctx, sender, "Try something like `answer first_name Aditya`.")
            return
        await _apply_field_edit(ctx, sender, sess, name, value, cmd.kind)
        return

    if cmd.kind == "unfill":
        name = cmd.field_name or ""
        if not sess.field_meta(name):
            await _say(ctx, sender, f"No field named `{name}` in this form.")
            return
        sess.clear_field(name)
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, f"✓ Cleared `{name}`.")
        return

    if cmd.kind in {"submit", "submit_live"}:
        await _do_submit(ctx, sender, sess, dry_run=(cmd.kind == "submit"))
        return

    if cmd.kind == "cancel":
        session_mod.clear(ctx.storage, sender)
        await _say(ctx, sender, "✓ Session cancelled.", end_session=True)
        return

    # Unknown command in REVIEWING state — hand off to the LLM interpreter
    # so the agent reads as a chat partner rather than a CLI.
    await _llm_handle(ctx, sender, sess, cmd.raw)


async def _llm_handle(
    ctx: Context, sender: str, sess: Session, user_text: str
) -> None:
    """Run the user message through the LLM intent interpreter, send the
    conversational reply, and dispatch the matched intent (if actionable).

    Keeps every reply short and chat-shaped — never dumps the whole panel
    unless the user asked for it.
    """
    interp = chat_llm.interpret(user_text, chat_llm.build_session_context(sess))
    ctx.logger.info(
        f"LLM intent={interp.intent!r} field={interp.field!r} "
        f"value={(interp.value or '')[:60]!r}"
    )

    # Always send the conversational reply first so the message feels human.
    if interp.reply:
        await _say(ctx, sender, interp.reply)

    intent = interp.intent

    if intent in {"greet", "smalltalk", "noop", "status"}:
        return

    if intent == "help":
        await _say(ctx, sender, HELP)
        return

    if intent == "cancel":
        session_mod.clear(ctx.storage, sender)
        return

    if intent == "show_all":
        await _say(ctx, sender, rendering.format_panel(sess))
        return

    if intent == "show":
        if not interp.field:
            return
        await _say(ctx, sender, rendering.format_field_detail(sess, interp.field))
        return

    if intent == "show_payload":
        last = sess.last_submission or {}
        body = last.get("response_body")
        if not body:
            await _say(
                ctx, sender,
                "No payload to show yet — run `submit` (dry-run) first.",
            )
            return
        snippet = body if len(body) <= 1800 else (body[:1800] + "\n…(truncated)")
        await _say(ctx, sender, f"```json\n{snippet}\n```")
        return

    if intent == "next":
        await _say(ctx, sender, rendering.format_next_missing(sess))
        return

    if intent in {"answer", "edit"}:
        if not interp.field or interp.value is None:
            return
        await _apply_field_edit(ctx, sender, sess, interp.field, interp.value, intent)
        return

    if intent == "unfill":
        if not interp.field:
            return
        if not sess.field_meta(interp.field):
            await _say(ctx, sender, f"There's no field called `{interp.field}` on this form.")
            return
        sess.clear_field(interp.field)
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, f"Cleared `{interp.field}`.")
        return

    if intent in {"submit", "submit_live"}:
        await _do_submit(ctx, sender, sess, dry_run=(intent == "submit"))
        return


async def _apply_field_edit(
    ctx: Context, sender: str, sess: Session, name: str, value: str, kind: str
) -> None:
    """Set a single field (answer or edit), persist, and save back to the
    profile. Used by both the LLM intent dispatcher and the deterministic
    `answer`/`edit` commands."""
    if not sess.field_meta(name):
        await _say(
            ctx, sender,
            f"Hmm, I couldn't find a field called `{name}` on this form. "
            f"Try `show all` to see the field names.",
        )
        return

    # Normalise against select option labels → values when possible.
    meta = sess.field_meta(name) or {}
    opts = meta.get("values") or meta.get("options") or []
    resolved = value
    if isinstance(opts, list) and opts:
        lower = value.lower().strip()
        for o in opts:
            if isinstance(o, dict):
                label = str(o.get("label") or "").lower()
                val = str(o.get("value") or "")
                if label == lower or val.lower() == lower:
                    resolved = val
                    break

    q = sess.question_for(name)
    label = (q or {}).get("label") or ""
    sess.set_field(name, resolved, source="user", confidence=1.0)
    sess.user_edits.append(
        {"name": name, "label": label, "value": resolved, "kind": kind}
    )
    session_mod.save(ctx.storage, sess)

    await _save_edit_to_profile(ctx, label=label, field_name=name, value=resolved)

    tail = (
        "All required fields are filled — say `submit` whenever you're ready."
        if not sess.missing_required
        else f"Still missing: {', '.join(sess.missing_required)}."
    )
    await _say(ctx, sender, f"Got it — set `{name}` to `{resolved}`. {tail}")


async def _do_submit(
    ctx: Context, sender: str, sess: Session, *, dry_run: bool
) -> None:
    if sess.missing_required:
        await _say(
            ctx, sender,
            "⚠️ Cannot submit yet — these required field(s) still need a value:\n"
            f"  {', '.join(sess.missing_required)}\n"
            "Use `answer <name> <value>` or `next` to fill them.",
        )
        return

    if not sess.job_json:
        await _say(ctx, sender, "No active application — paste a Greenhouse URL to start.")
        return

    if not dry_run and not sess.resume_path:
        await _say(
            ctx, sender,
            "⚠️ No resume on file. Set `DEFAULT_RESUME_PATH` or ingest a resume "
            "via the Profile Agent before submitting live.",
        )
        return

    sess.state = State.SUBMITTING
    session_mod.save(ctx.storage, sess)

    label = "dry-run" if dry_run else "live"
    await _say(ctx, sender, f"📤 Submitting ({label}) to Greenhouse...")

    filled_payload = {
        "filled": [
            {
                "name": f.get("name"),
                "label": f.get("label", ""),
                "value": f.get("value"),
                "source": f.get("source", "user"),
                "confidence": f.get("confidence", 1.0),
            }
            for f in sess.filled
            # File fields are passed via resume_path, not in filled_json.
            if (f.get("ftype") or "").lower() not in {"input_file", "file"}
        ],
        "missing_required": sess.missing_required,
    }

    try:
        resp = await clients.call_submitter(
            ctx,
            SUBMITTER_ADDR,
            job_json=sess.job_json,
            filled_json=json.dumps(filled_payload),
            resume_path=sess.resume_path or "",
            dry_run=dry_run,
            timeout=SUBMITTER_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        sess.state = State.REVIEWING
        session_mod.save(ctx.storage, sess)
        await _say(ctx, sender, f"❌ Couldn't reach the submitter: {exc}")
        return

    sess.last_submission = {
        "dry_run": resp.dry_run,
        "success": resp.success,
        "application_id": resp.application_id,
        "response_status": resp.response_status,
        "response_body": resp.response_body,
        "error": resp.error,
        "fields_submitted": resp.fields_submitted,
        "missing_required": resp.missing_required,
    }

    if resp.success and not resp.dry_run:
        sess.state = State.DONE
    else:
        sess.state = State.REVIEWING  # let user retry / inspect
    session_mod.save(ctx.storage, sess)

    await _say(
        ctx, sender,
        rendering.format_submission_result(
            dry_run=resp.dry_run,
            success=resp.success,
            error=resp.error,
            application_id=resp.application_id,
            status_code=resp.response_status,
            fields_submitted=resp.fields_submitted,
            missing_required=resp.missing_required,
        ),
        end_session=(resp.success and not resp.dry_run),
    )


# ---------------------------------------------------------------------------
# Chat protocol handler — the front door
# ---------------------------------------------------------------------------


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    # 1. Ack FIRST per protocol contract.
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id),
    )

    # 2. On the opening message of a session, tell ASI:One we support
    #    attachments (in case we add resume-upload support later).
    if any(isinstance(c, StartSessionContent) for c in msg.content):
        await ctx.send(
            sender,
            ChatMessage(
                msg_id=uuid4(),
                timestamp=datetime.now(UTC),
                content=[MetadataContent(type="metadata", metadata={"attachments": "true"})],
            ),
        )

    text = "".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    ).strip()

    if not text:
        return  # StartSession-only ping

    cmd = parse_command(text)
    ctx.logger.info(f"Chat from {sender}: kind={cmd.kind} text={text[:200]!r}")

    if cmd.kind == "help":
        await _say(ctx, sender, HELP)
        return

    if cmd.kind == "cancel":
        session_mod.clear(ctx.storage, sender)
        await _say(ctx, sender, "✓ Session cleared.", end_session=True)
        return

    if cmd.kind == "apply":
        await _start_application(ctx, sender, cmd.url or "")
        return

    # Anything else: route by session state.
    sess = session_mod.load(ctx.storage, sender)

    if sess.state in (State.EXTRACTING, State.MAPPING, State.SUBMITTING):
        await _say(
            ctx, sender,
            f"⏳ Still working on the {sess.state.value} step — hang tight.",
        )
        return

    if sess.state in (State.IDLE, State.DONE):
        # No active application — anything other than a URL is small talk.
        await _llm_handle(ctx, sender, sess, text)
        return

    # REVIEWING
    await _handle_review_command(ctx, sender, sess, cmd)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Ack from {sender} for {msg.acknowledged_msg_id}")


agent.include(chat_proto, publish_manifest=True)


# ---------------------------------------------------------------------------
# Agentverse registration
# ---------------------------------------------------------------------------


README = """# Job Application Form-Filler

![tag:user-facing](https://img.shields.io/badge/user--facing-3D8BD3)
![tag:greenhouse](https://img.shields.io/badge/greenhouse-3D8BD3)
![tag:form-filler](https://img.shields.io/badge/form--filler-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

User-facing chat agent that turns a Greenhouse job link into a filled
application form right in the chat. Watch each field populate from your
saved profile (with RAG + ASI:One for free-text questions), edit any value,
fill in anything missing, then explicitly type `submit` when you're ready.

The agent orchestrates three helper agents (extractor, profile, submitter)
but only YOU decide when the application gets sent.
"""


@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    ctx.logger.info(
        f"Helpers: extractor={EXTRACTOR_ADDR or '(unset)'} "
        f"profile={PROFILE_ADDR or '(unset)'} "
        f"submitter={SUBMITTER_ADDR or '(unset)'}"
    )
    ctx.logger.info(
        f"Live form fill: mode={LIVE_FILL_MODE} "
        f"screenshot_every={LIVE_FILL_SCREENSHOT_EVERY}"
    )
    for label, val in [
        ("EXTRACTOR_AGENT_ADDRESS", EXTRACTOR_ADDR),
        ("PROFILE_AGENT_ADDRESS", PROFILE_ADDR),
        ("SUBMITTER_AGENT_ADDRESS", SUBMITTER_ADDR),
    ]:
        if not val:
            ctx.logger.warning(
                f"{label} is not set — set it in form-filler-agent/.env"
            )

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
                "User-facing job-application chat agent. Paste a Greenhouse "
                "job URL and watch the form fill in real time — every value "
                "is visible, every value is editable, and you decide when to "
                "submit."
            ),
        )
        ctx.logger.info("Registered with Agentverse")
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Failed to register with Agentverse: {exc}")


if __name__ == "__main__":
    agent.run()
