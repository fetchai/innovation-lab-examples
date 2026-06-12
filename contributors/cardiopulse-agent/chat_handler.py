"""
Chat protocol handler.

Drives the 3-phase cardio fitness test through ASI:One chat:
  1. Resting baseline (2 minutes)
  2. Orthostatic challenge (30 seconds)
  3. Paced breathing (30 seconds)
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

import chart as chart_module
import coach as coach_module
import history
import image_host
import scoring
import session_state

chat_proto = Protocol(spec=chat_protocol_spec)


WELCOME = (
    "Hi! I'm a Cardio Fitness Test agent. "
    "In about 3 minutes I can estimate your cardiovascular age from your "
    "heart rate using your Garmin watch.\n\n"
    "**Before we start:**\n"
    "1. Wear your Garmin watch.\n"
    "2. Enable Broadcast Heart Rate on the watch "
    "(Settings → Health and Wellness → Wrist Heart Rate → Broadcast Heart Rate → Start).\n"
    "3. Sit somewhere quiet.\n\n"
    "**Tell me your age** (e.g. `age 25`), then say `start test`.\n\n"
    "_You can also just say `age 25, start test` to do both at once._"
)

# Per-session state. Each ASI:One conversation has its own session id.
# Keys: session id (str). Values: dict with the user's age (or None until set)
# and a flag for whether a test is currently running.
SESSIONS: dict[str, dict] = {}

BASELINE_SEC = 120
ORTHOSTATIC_SEC = 30
BREATHING_SEC = 30


def _new_session() -> dict:
    return {"age": None, "running": False}


def _text(text: str, end_session: bool = False) -> ChatMessage:
    content: list = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


def _parse_age(text: str) -> int | None:
    """Pull a plausible age out of a free-text message."""
    match = re.search(r"\b(\d{2})\b", text)
    if not match:
        return None
    age = int(match.group(1))
    if 10 <= age <= 100:
        return age
    return None


def _strip_mention(text: str) -> str:
    """Remove a leading @<agent-address> mention so keyword matching still works.

    ASI:One main chat requires explicit @<address> mentions to force-route a
    message to a specific agent. The mention shouldn't change how we interpret
    the rest of the text.
    """
    return re.sub(r"^@\S+\s*", "", text).strip()


async def _run_test(ctx: Context, sender: str, session_id: str) -> None:
    """Run the 3-phase test and report results."""

    sess = SESSIONS.setdefault(session_id, _new_session())

    # Prevent overlapping tests within the same session.
    if sess["running"]:
        await ctx.send(
            sender,
            _text("A test is already in progress in this session. Hold tight."),
        )
        return

    # Age is required for scoring — refuse to guess.
    if sess["age"] is None:
        await ctx.send(
            sender,
            _text(
                "I need your age before I can score the test. "
                "Reply with something like `age 27`, then say `start test`."
            ),
        )
        return

    if not session_state.is_streaming():
        await ctx.send(
            sender,
            _text(
                "I'm not receiving any heart rate data yet. "
                "Make sure your Garmin watch is on and Broadcast Heart Rate is "
                "active (Settings → Health and Wellness → Wrist Heart Rate → "
                "Broadcast Heart Rate → Start). Keep that broadcast screen open, "
                "then say `start test` again."
            ),
        )
        return

    sess["running"] = True
    try:
        age = sess["age"]
        ctx.logger.info(f"Starting test for session {session_id}, age={age}")

        await ctx.send(
            sender,
            _text(
                f"Connected. Latest BPM: {session_state.latest_bpm()}.\n\n"
                "**Phase 1 — Resting baseline (2 minutes)**\n"
                "Sit calmly, breathe normally, keep your wrist still."
            ),
        )

        baseline_start = time.time()
        await asyncio.sleep(BASELINE_SEC / 2)
        await ctx.send(
            sender,
            _text(
                "Halfway through baseline. Keep sitting calmly. "
                f"Current BPM: {session_state.latest_bpm()}."
            ),
        )
        await asyncio.sleep(BASELINE_SEC / 2)
        baseline_end = time.time()

        await ctx.send(
            sender,
            _text(
                "**Phase 2 — Stand up (30 seconds)**\n"
                "Stand up now and stay still. Don't move your arms."
            ),
        )
        ortho_start = time.time()
        await asyncio.sleep(ORTHOSTATIC_SEC)
        ortho_end = time.time()

        await ctx.send(
            sender,
            _text(
                "**Phase 3 — Paced breathing (30 seconds)**\n"
                "Breathe in for 5 seconds, out for 5 seconds. "
                "Three full breath cycles."
            ),
        )
        breath_start = time.time()
        await asyncio.sleep(BREATHING_SEC)
        breath_end = time.time()

        baseline = session_state.bpm_in_window(baseline_start, baseline_end)
        ortho = session_state.bpm_in_window(ortho_start, ortho_end)
        breath = session_state.bpm_in_window(breath_start, breath_end)

        # Pull timestamped series for the chart (separate from the BPM-only
        # arrays the scorer wants).
        baseline_series = session_state.bpm_series_in_window(
            baseline_start, baseline_end
        )
        ortho_series = session_state.bpm_series_in_window(ortho_start, ortho_end)
        breath_series = session_state.bpm_series_in_window(breath_start, breath_end)

        ctx.logger.info(
            f"Samples collected: baseline={len(baseline)}, "
            f"ortho={len(ortho)}, breath={len(breath)}"
        )

        try:
            result = scoring.compute(
                age=age,
                baseline_bpm=baseline,
                orthostatic_bpm=ortho,
                breathing_bpm=breath,
            )
        except ValueError as e:
            await ctx.send(
                sender,
                _text(
                    f"Couldn't score the test: {e}\n\n"
                    "This usually means the watch broadcast stopped mid-test. "
                    "Re-enable HR broadcast on the watch and try again."
                ),
            )
            return

        # Build EVERYTHING first, then deliver ONE consolidated message.
        # ASI:One's main chat merges and re-renders multiple agent messages
        # into a jumbled blob; a single message stays intact. Charts go to
        # Imgur and come back as public URLs that render as markdown images.

        # Chart 1: this test's HR timeline.
        chart_md = ""
        try:
            png_bytes = chart_module.build_png_bytes(
                baseline_samples=baseline_series,
                orthostatic_samples=ortho_series,
                breathing_samples=breath_series,
                result=result,
            )
            if png_bytes:
                url = image_host.upload_image(png_bytes)
                if url:
                    chart_md = (
                        f"\n\n![Your HR timeline]({url})\n"
                        "_Your heart rate across the three phases: resting "
                        "baseline, standing, paced breathing._"
                    )
                    ctx.logger.info(f"Test chart posted: {url}")
                else:
                    ctx.logger.warning("Chart skipped — image upload failed.")
        except Exception as e:
            ctx.logger.warning(f"Chart generation failed: {e}")

        # Coaching paragraph, with trend context from THIS USER's history only.
        coach_text = ""
        try:
            prev = history.previous(sender)
            coach_text = coach_module.coach(result, previous=prev)
        except Exception as e:
            ctx.logger.warning(f"Coach paragraph failed: {e}")

        # Persist this test under the sender's key so future trend
        # comparisons never mix different users' tests.
        try:
            history.append(result, sender)
        except Exception as e:
            ctx.logger.warning(f"History append failed: {e}")

        # Chart 2: trend across this user's tests (needs 2+ on file).
        trend_md = ""
        try:
            records = history.recent(limit=10, sender=sender)
            if len(records) >= 2:
                trend_bytes = chart_module.build_trend_png_bytes(records)
                if trend_bytes:
                    trend_url = image_host.upload_image(trend_bytes)
                    if trend_url:
                        trend_md = (
                            f"\n\n![Your trend]({trend_url})\n"
                            f"_Cardio Fitness Age and Resting HR across your "
                            f"last {len(records)} tests._"
                        )
                        ctx.logger.info(f"Trend chart posted: {trend_url}")
        except Exception as e:
            ctx.logger.warning(f"Trend chart failed: {e}")

        # Assemble and send as ONE message.
        final = scoring.format_result(result)
        final += chart_md
        if coach_text:
            final += f"\n\n**Coach's read**\n{coach_text}"
        final += trend_md

        await ctx.send(sender, _text(final))
        ctx.logger.info(f"History updated. {history.count()} test(s) on file.")
    finally:
        sess["running"] = False


async def _handle_text(ctx: Context, sender: str, session_id: str, text: str) -> None:
    sess = SESSIONS.setdefault(session_id, _new_session())

    # Strip any @<agent-address> prefix so keyword matching works whether the
    # user is in Manual Test (no mention) or ASI:One main chat (mention required).
    cleaned = _strip_mention(text)
    lower = cleaned.lower().strip()

    has_age_keyword = "age" in lower
    has_start = "start" in lower and "test" in lower

    if has_age_keyword:
        age = _parse_age(cleaned)
        if age is not None:
            sess["age"] = age
            if has_start:
                # Combined "age N, start test" — set age and immediately kick off.
                await ctx.send(
                    sender,
                    _text(f"Got it — age {age}. Starting the test now."),
                )
                await _run_test(ctx, sender, session_id)
                return
            await ctx.send(
                sender,
                _text(f"Got it — age {age}. When you're ready, say `start test`."),
            )
            return
        if not has_start:
            await ctx.send(sender, _text("Couldn't parse that age. Try `age 25`."))
            return

    if has_start:
        await _run_test(ctx, sender, session_id)
        return

    if lower in {"hi", "hello", "hey", "?", "help", ""}:
        await ctx.send(sender, _text(WELCOME))
        return

    if lower in {"status", "bpm", "ping"}:
        if session_state.is_streaming():
            await ctx.send(
                sender,
                _text(f"Streaming. Latest BPM: {session_state.latest_bpm()}."),
            )
        else:
            await ctx.send(
                sender,
                _text(
                    "Not receiving HR data. Make sure your Garmin watch is on "
                    "and Broadcast Heart Rate is active."
                ),
            )
        return

    # Default fallback: re-show the welcome message.
    await ctx.send(sender, _text(WELCOME))


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    session_id = str(ctx.session)
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            await ctx.send(sender, _text(WELCOME))
        elif isinstance(item, TextContent):
            await _handle_text(ctx, sender, session_id, item.text)
        elif isinstance(item, EndSessionContent):
            SESSIONS.pop(session_id, None)


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.debug(f"ACK from {sender} for {msg.acknowledged_msg_id}")
