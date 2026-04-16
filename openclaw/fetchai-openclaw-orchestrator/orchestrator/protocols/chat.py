"""
ASI:One Chat Protocol integration.

This protocol makes the Orchestrator Agent discoverable and usable
from ASI:One by implementing the standard ``AgentChatProtocol``.

Flow:
  1. ASI:One sends a ``ChatMessage`` containing the user's objective
  2. We acknowledge receipt immediately
  3. We run the objective through the planner
  4. If a paired connector exists -> dispatch the task (async reply later)
  5. If no connector -> execute locally for demo purposes
  6. Return results as a ``ChatMessage`` back to ASI:One

Reference:
  https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from orchestrator.planner import plan_objective
from orchestrator.protocols.models import (
    TaskDispatchRequest,
)

logger = logging.getLogger(__name__)

# Create the protocol from the official spec so ASI:One recognises it
chat_proto = Protocol(spec=chat_protocol_spec)

# ---------------------------------------------------------------------------
# Constants for feedback-loop detection
# ---------------------------------------------------------------------------

# Maximum pending chat tasks before we refuse new ones.
# Prevents unbounded growth from echo loops.
_MAX_PENDING_TASKS = 5

# Minimum seconds between processing objectives from the SAME sender.
_SENDER_COOLDOWN_SECS = 30

# Regex to strip @agent1q... prefix that ASI:One prepends to messages.
_AGENT_ADDRESS_PREFIX_RE = re.compile(
    r"^@agent1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{59}\s*",
)

# Command verbs that indicate a GENUINE user request (imperative form).
# If the cleaned message starts with one of these, it is never an echo.
_COMMAND_VERBS_RE = re.compile(
    r"^(generate|analyze|analyse|review|audit|check|inspect|scan|clone|"
    r"create|build|run|test|summarize|summarise|compare|look|give|get|"
    r"show|find|list|tell|explain|help|what|how|can)\b",
    re.I,
)

# If the message contains a GitHub URL, it is a genuine request.
_GITHUB_URL_RE = re.compile(r"https?://github\.com/", re.I)

# Keywords the user would realistically include in a genuine objective.
# If a message does NOT contain any of these, it is probably an echo.
_GENUINE_OBJECTIVE_KEYWORDS = re.compile(
    r"\b("
    r"generate|weekly|report|analyze|analyse|review|audit|health|score|"
    r"check|inspect|github\.com|repo|clone|scan|hello|hi|help|what|how|"
    r"create|build|run|test|summary|status"
    r")\b",
    re.I,
)

# Patterns that indicate the message is an echo of our own response.
# ASI:One's LLM creatively rewrites our replies and sends them back.
# IMPORTANT: Do NOT include patterns that overlap with genuine user requests
# (e.g. "weekly dev report" would block "Generate my weekly dev report").
_ECHO_PATTERNS = [
    "task dispatched",
    "task executed",
    "execution complete",
    "standing by for results",
    "awaiting exec",
    "awaiting result",
    "awaiting execution",
    "report generation dispatched",
    "report complete!",
    "report dispatched",
    "report mode activated",
    "report generated!",
    "report delivered!",
    "report in flight",
    "report in motion",
    "report landed",
    "report creation initiated",
    "mission running",
    "mission accomplished",
    "mission unclear",
    "mission should i execute",
    "intel compiling",
    "pipeline:",
    "pipeline running",
    "pipeline active",
    "repos scanned",
    "repos scanning",
    "gen + post",
    "scan_directory",
    "generate_report",
    "post_summary",
    "clone_repo",
    "analyze_repo",
    "generate_health_report",
    "wait for it",
    "spinning in loops",
    "looping through messages",
    "breaking the cyc",
    "stuck in the recursion",
    "ready for slack",
    "slack integration pending",
    "slack blocked",
    "slack posting",
    "integration not configured",
    "standing by for your",
    "standing by!",
    "what mission should i",
    "what do you want me to do",
    "what should i do next",
    "no objective received",
    "no directive received",
    "no task received",
    "i need instructions",
    "give me a job",
    "hold up",
    "commits tracked",
    "commits captured",
    "commits logged",
    "commits across",
    "weekly report generated",
    "weekly scan done",
    "three repos",
    "3 repos scanned",
    "scan complete but empty",
    "ghost town",
    "ready when you are",
    "ready to rock",
    "ready to post",
    "let's go!",
    "let's ship",
    "let's execute",
    "let's roll",
    "let's complete",
    "rockin' the commits",
    "documentation is the breakfast",
    "step pipeline:",
    "-step pipeline",
    "weekly dev intel",
    "dev intel across",
    "data-pipeline:",
    "mission complete!",
    "drop your mission",
    "deploy!",
    "no objective detected",
]

# Regex to detect task IDs embedded in messages (our own outputs echoed back)
_TASK_ID_RE = re.compile(r"task_[0-9a-f]{10,}", re.I)

# Emoji-heavy messages (3+ emoji) are almost always echoes from ASI:One's LLM
_EMOJI_RE = re.compile(
    r"[\U0001f300-\U0001f9ff\U00002600-\U000027bf\U0000fe00-\U0000fe0f"
    r"\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff\U00002702-\U000027b0"
    r"\U0000200d\U0000fe0f]"
)


# ---------------------------------------------------------------------------
# Helper - send a ChatMessage reply
# ---------------------------------------------------------------------------


async def send_chat_reply(ctx: Context, recipient: str, text: str):
    """Send a ChatMessage with text content back to the recipient."""
    await ctx.send(
        recipient,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(text=text)],
        ),
    )


# ---------------------------------------------------------------------------
# Feedback loop detection helpers
# ---------------------------------------------------------------------------


def _clean_objective(text: str) -> str:
    """Strip @agent... prefix and leading/trailing whitespace."""
    cleaned = _AGENT_ADDRESS_PREFIX_RE.sub("", text).strip()
    return cleaned


def _looks_like_echo(text: str) -> bool:
    """Return True if the text appears to be our own response echoed back."""
    # Clean the text first (strip @agent prefix, whitespace)
    cleaned = _clean_objective(text)
    lower = cleaned.lower()

    # --- GENUINE REQUEST FAST-PATH ---
    # If the cleaned message starts with a command verb, it is a real user
    # request regardless of any echo pattern substring matches.
    if _COMMAND_VERBS_RE.match(cleaned):
        return False

    # If the message contains a GitHub URL, it is a real request.
    if _GITHUB_URL_RE.search(text):
        return False

    # --- ECHO CHECKS ---
    # Check for known echo patterns
    if any(pattern in lower for pattern in _ECHO_PATTERNS):
        return True

    # Check for embedded task IDs (task_xxxxxxxxxxxx)
    if _TASK_ID_RE.search(text):
        return True

    # Messages with 3+ emoji are almost certainly ASI:One's LLM rewrites
    emoji_count = len(_EMOJI_RE.findall(text))
    if emoji_count >= 3:
        return True

    # If the message does NOT contain any genuine objective keywords,
    # it is very likely an echo/status message.
    if not _GENUINE_OBJECTIVE_KEYWORDS.search(cleaned):
        return True

    return False


def _get_pending_count(ctx: Context) -> int:
    """Return the number of pending chat tasks."""
    pending = ctx.storage.get("chat_pending")
    if not pending:
        return 0
    try:
        return len(json.loads(pending))
    except (json.JSONDecodeError, TypeError):
        return 0


def _prune_pending(ctx: Context) -> None:
    """Remove all pending chat tasks to prevent unbounded growth."""
    ctx.storage.set("chat_pending", "{}")


# ---------------------------------------------------------------------------
# ChatMessage handler  (ASI:One -> Orchestrator)
# ---------------------------------------------------------------------------


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """
    Receive a natural-language objective from ASI:One and process it.
    """
    from orchestrator.agent import (
        fetch_policy,
        orchestrator_private_key,
        pairing_store,
    )
    from shared.crypto import sign_payload

    # --- Acknowledge immediately ---------------------------------------------
    await ctx.send(
        sender,
        ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id,
            timestamp=datetime.now(timezone.utc),
        ),
    )

    # --- Extract text from message content -----------------------------------
    objective_text = ""
    for content in msg.content:
        if isinstance(content, StartSessionContent):
            ctx.logger.info("Chat session started by %s", sender)
            return  # nothing to process yet
        elif isinstance(content, TextContent):
            objective_text = content.text
        # Ignore other content types gracefully

    if not objective_text:
        # Do NOT reply to empty messages -- replying causes ASI:One loops.
        ctx.logger.warning("Empty objective from %s - ignoring silently", sender)
        return

    ctx.logger.info("Chat objective from %s: %.120s", sender, objective_text)

    # --- Strip @agent... prefix that ASI:One prepends -------------------------
    objective_text = _clean_objective(objective_text)
    if not objective_text:
        ctx.logger.warning("Objective empty after cleaning - ignoring")
        return

    # --- Feedback loop detection (pattern-based) -----------------------------
    if _looks_like_echo(objective_text):
        ctx.logger.warning(
            "Detected echo/feedback loop - ignoring: %.80s",
            objective_text,
        )
        return

    # --- Pending task cap ----------------------------------------------------
    # If we already have too many pending tasks, prune them (stale echoes).
    pending_count = _get_pending_count(ctx)
    if pending_count > _MAX_PENDING_TASKS:
        ctx.logger.warning(
            "Too many pending tasks (%d) - pruning stale entries",
            pending_count,
        )
        _prune_pending(ctx)

    # --- Per-sender cooldown -------------------------------------------------
    now = time.time()
    sender_key = f"sender_cd:{hashlib.md5(sender.encode()).hexdigest()[:12]}"
    last_dispatch = ctx.storage.get(sender_key)
    if last_dispatch and (now - float(last_dispatch)) < _SENDER_COOLDOWN_SECS:
        ctx.logger.warning(
            "Sender %s in cooldown (%.0fs remaining) - ignoring",
            sender[:20],
            _SENDER_COOLDOWN_SECS - (now - float(last_dispatch)),
        )
        return

    # --- Dedup: ignore exact same text within short window -------------------
    obj_hash = hashlib.md5(objective_text.encode()).hexdigest()[:12]
    dedup_key = f"dedup:{obj_hash}"
    last_seen = ctx.storage.get(dedup_key)
    if last_seen and (now - float(last_seen)) < 120:
        ctx.logger.warning("Duplicate objective - ignoring: %.60s", objective_text)
        return
    ctx.storage.set(dedup_key, str(now))

    # --- Plan the objective --------------------------------------------------
    plan = plan_objective(objective_text)
    ctx.logger.info("Generated plan %s with %d steps", plan.task_id, len(plan.steps))

    # --- Fetch-side policy ---------------------------------------------------
    user_id = sender
    rejection = fetch_policy.validate(user_id, plan)
    if rejection is not None:
        # Do NOT reply with rejection details -- that also triggers loops.
        ctx.logger.warning(
            "Policy rejected plan %s: %s",
            plan.task_id,
            rejection.value,
        )
        return

    # --- Start sender cooldown (BEFORE dispatching) --------------------------
    ctx.storage.set(sender_key, str(now))

    # --- Try to dispatch to a paired connector -------------------------------
    devices = pairing_store.devices_for_user(user_id)

    # Also check all devices as a fallback (for local testing)
    if not devices:
        devices = pairing_store.all_devices()

    if devices:
        device = devices[0]
        plan_dict = plan.model_dump(mode="json")
        plan_json = json.dumps(plan_dict, sort_keys=True, default=str)

        signature = ""
        if orchestrator_private_key is not None:
            signature = sign_payload(orchestrator_private_key, plan_dict)

        dispatch = TaskDispatchRequest(
            user_id=device.user_id,
            device_id=device.device_id,
            task_plan_json=plan_json,
            signature=signature,
        )

        # Store pending task for async result correlation (chat-originated)
        pending = ctx.storage.get("chat_pending") or "{}"
        pending_dict: dict = json.loads(pending)
        pending_dict[plan.task_id] = {
            "sender": sender,
            "objective": objective_text,
        }
        ctx.storage.set("chat_pending", json.dumps(pending_dict))

        connector_address = ctx.storage.get(
            f"connector:{device.user_id}:{device.device_id}"
        )
        if connector_address:
            ctx.logger.info(
                "Dispatching task %s to connector %s", plan.task_id, connector_address
            )
            await ctx.send(connector_address, dispatch)

            # Do NOT send intermediate "task dispatched" message.
            # ASI:One echoes such messages back, creating a feedback loop.
            # The user will receive the final result directly when execution
            # completes (via _relay_to_chat in objective.py).
            return
        else:
            ctx.logger.warning(
                "Connector address not found for %s:%s - falling back to local",
                device.user_id,
                device.device_id,
            )

    # --- Fallback: execute locally (demo / no connector paired) --------------
    ctx.logger.info("No connector available - executing plan locally")
    from connector.executor import execute_plan

    result = execute_plan(plan)

    # Format results as readable text
    report_text = result.outputs.get("generate_report", {}).get(
        "report_text"
    ) or result.outputs.get("generate_health_report", {}).get("report_text")

    if report_text:
        await send_chat_reply(ctx, sender, report_text)
    else:
        result_lines = [
            f"Task {result.task_id} completed ({result.status.value}).",
            "",
        ]
        for sr in result.step_results:
            emoji = "done" if sr.status.value == "completed" else "failed"
            result_lines.append(f"- {sr.action}: {emoji}")
            if sr.error:
                result_lines.append(f"  Error: {sr.error}")

        await send_chat_reply(ctx, sender, "\n".join(result_lines))


# ---------------------------------------------------------------------------
# ChatAcknowledgement handler
# ---------------------------------------------------------------------------


@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        "Chat acknowledgement from %s for message %s",
        sender,
        msg.acknowledged_msg_id,
    )
