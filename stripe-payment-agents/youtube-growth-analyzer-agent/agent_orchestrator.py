"""
User-facing orchestrator for the YouTube Growth Analyzer.

This module is the **Agentverse / ASI:One entrypoint**.

Chat protocol (ASI:One / Agentverse)
----------------------------------
- The agent includes the **Agent Chat Protocol** (`uagents_core.contrib.protocols.chat`).
- Incoming user turns are delivered as `ChatMessage` payloads (typically `TextContent` parts).
- The orchestrator replies with `ChatMessage` + (when payment is required) a seller-side
  `RequestPayment` carrying Stripe embedded Checkout metadata.

Multi-agent orchestration (LangGraph)
--------------------------------------
- **Free path graph**: `channel_fetch` → `basic_preview` (lightweight preview only).
- **Premium path graph**: `engagement` → `strategy` (full report), executed only after Stripe verification.

Payment protocol (seller role)
------------------------------
- The agent includes the **Agent Payment Protocol** with `role="seller"`.
- It sends `RequestPayment` with `Funds(..., payment_method="stripe")` and `metadata["stripe"]` for embedded Checkout.
- After checkout, the client sends `CommitPayment` with `transaction_id` equal to the Stripe Checkout Session id.
- The seller verifies payment via Stripe, then sends `CompletePayment`, then delivers premium text.

Run locally: `python agent_orchestrator.py`
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    RejectPayment,
    payment_protocol_spec,
)

from agent_basic_analysis import build_free_preview
from agentverse_mailbox_connect import schedule_mailbox_registration
from agent_channel_fetch import (
    extract_channel_locator,
    parse_youtube_channel_id_or_handle,
)
from agent_engagement import analyze_engagement
from agent_strategy import build_premium_report
from config import (
    AGENT_PORT,
    PREMIUM_REPORT_CHUNK_CHARS,
    STATE_TTL_SECONDS,
    STRIPE_AMOUNT_CENTS,
    STRIPE_PRODUCT_NAME,
)
from models import ChannelSnapshot, EngagementMetrics, PaymentActionPayload
from payment_handler import (
    build_request_payment,
    create_embedded_checkout_session,
    verify_checkout_session_amount_usd,
    verify_checkout_session_paid,
)


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


_configure_logging()
logger = logging.getLogger("youtube-growth-analyzer-agent")

ChatHandler = Callable[[Context, str, ChatMessage], Awaitable[None]]


class GraphState(TypedDict, total=False):
    """LangGraph state shared across multi-agent nodes."""

    channel_input: str
    error: str | None
    snapshot: dict[str, Any] | None
    preview_markdown: str | None
    engagement: dict[str, Any] | None
    premium_markdown: str | None


def _node_fetch(state: GraphState) -> GraphState:
    from agent_channel_fetch import resolve_and_fetch

    snap, err = resolve_and_fetch(state.get("channel_input", ""))
    if err or snap is None:
        if err:
            hint = f" {err.hint}" if err.hint else ""
            return {**state, "error": f"{err.message}{hint}", "snapshot": None}
        return {
            **state,
            "error": "Could not resolve channel data.",
            "snapshot": None,
        }
    return {**state, "error": None, "snapshot": snap.model_dump(mode="json")}


def _node_preview(state: GraphState) -> GraphState:
    if state.get("error"):
        return state
    snap = ChannelSnapshot.model_validate(state.get("snapshot") or {})
    preview = build_free_preview(snap)
    return {**state, "preview_markdown": preview.to_markdown()}


def _node_engagement(state: GraphState) -> GraphState:
    if state.get("error"):
        return state
    snap = ChannelSnapshot.model_validate(state.get("snapshot") or {})
    eng = analyze_engagement(snap)
    return {**state, "engagement": eng.model_dump(mode="json")}


def _node_strategy(state: GraphState) -> GraphState:
    if state.get("error"):
        return state
    snap = ChannelSnapshot.model_validate(state.get("snapshot") or {})
    eng = EngagementMetrics.model_validate(state.get("engagement") or {})
    report = build_premium_report(snap, eng)
    return {**state, "premium_markdown": report.to_markdown()}


def build_free_graph():
    """Fetch + free preview only (premium content must not be generated here)."""
    g = StateGraph(GraphState)
    g.add_node("fetch", _node_fetch)
    g.add_node("preview", _node_preview)
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "preview")
    g.add_edge("preview", END)
    return g.compile()


def build_premium_graph():
    """Engagement + strategy: runs only after payment verification succeeds."""
    g = StateGraph(GraphState)
    g.add_node("engagement", _node_engagement)
    g.add_node("strategy", _node_strategy)
    g.add_edge(START, "engagement")
    g.add_edge("engagement", "strategy")
    g.add_edge("strategy", END)
    return g.compile()


FREE_GRAPH = build_free_graph()
PREMIUM_GRAPH = build_premium_graph()


def run_free_pipeline(channel_input: str) -> GraphState:
    """Execute the free-tier LangGraph pipeline."""
    return FREE_GRAPH.invoke({"channel_input": channel_input})


def run_premium_pipeline(snapshot: dict[str, Any]) -> GraphState:
    """Execute the premium LangGraph pipeline for an already-fetched channel snapshot."""
    return PREMIUM_GRAPH.invoke({"snapshot": snapshot, "error": None})


def state_key(sender: str) -> str:
    return f"yt_growth_state:{sender}"


def load_state(ctx: Context, sender: str) -> dict[str, Any]:
    raw = ctx.storage.get(state_key(sender))
    if isinstance(raw, dict):
        state = raw
    elif isinstance(raw, str) and raw:
        try:
            state = json.loads(raw)
            if not isinstance(state, dict):
                state = {}
        except Exception:
            state = {}
    else:
        state = {}

    try:
        exp = float(state.get("expires_at") or 0)
        if not exp or time.time() > exp:
            return {}
    except Exception:
        return {}

    allowed = {
        "awaiting_payment",
        "pending_stripe",
        "snapshot",
        "channel_input",
        "preview_markdown",
        "expires_at",
    }
    return {k: state[k] for k in allowed if k in state}


def save_state(ctx: Context, sender: str, state: dict[str, Any]) -> None:
    ctx.storage.set(state_key(sender), json.dumps(state))


def clear_state(ctx: Context, sender: str) -> None:
    ctx.storage.set(state_key(sender), "{}")


def extract_text(msg: ChatMessage) -> str:
    try:
        direct = msg.text()
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
    except Exception:
        pass
    parts: list[str] = []
    for c in msg.content:
        if isinstance(c, TextContent) and c.text:
            parts.append(c.text)
        elif hasattr(c, "text") and getattr(c, "text", None):
            parts.append(str(getattr(c, "text")))
    out = " ".join(parts).strip()
    if not out:
        logger.warning(
            "ChatMessage had no extractable text; content types=%s",
            [type(c).__name__ for c in msg.content],
        )
    return out


def make_chat(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=text)],
    )


def _chunk_text_for_chat(text: str, max_chars: int) -> list[str]:
    """
    Split long markdown into multiple parts. Many chat clients (including ASI:One) truncate
    a single bubble; chunking preserves the full premium report.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = text[start:end]
            # Prefer paragraph break, then line break
            pp = window.rfind("\n\n")
            if pp > 200:
                end = start + pp + 2
            else:
                nl = window.rfind("\n")
                if nl > 200:
                    end = start + nl + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks if chunks else [text[:max_chars]]


def _looks_like_new_intent(text_l: str) -> bool:
    starters = (
        "hello",
        "hi",
        "hey",
        "help",
        "start over",
        "reset",
        "new analysis",
        "analyze ",
        "analyse ",
    )
    return any(s in text_l for s in starters)


def _payment_action_json(checkout: dict[str, Any]) -> str:
    """Frontend-friendly JSON block (in addition to AgentPayment RequestPayment metadata)."""
    action = {
        "type": "stripe_embedded_checkout",
        "label": PaymentActionPayload().label,
        "amount_usd": f"{STRIPE_AMOUNT_CENTS / 100:.2f}",
        "currency": "USD",
        "ui_mode": checkout.get("ui_mode", "embedded"),
        "publishable_key": checkout.get("publishable_key"),
        "client_secret": checkout.get("client_secret"),
        "checkout_session_id": checkout.get("checkout_session_id")
        or checkout.get("id"),
    }
    return json.dumps({"payment_action": action}, indent=2)


def _compose_paywall_message(preview_md: str, checkout: dict[str, Any]) -> str:
    return (
        preview_md
        + "\n\n---\n\n"
        + "**Payment required:** Pay **$5.00 USD** once to unlock the full premium growth report.\n\n"
        + "The client should render Stripe embedded Checkout using the `RequestPayment` metadata "
        + "(`metadata['stripe']`) and/or the machine-readable JSON below.\n\n"
        + "```json\n"
        + _payment_action_json(checkout)
        + "\n```"
    )


async def _on_chat_impl(ctx: Context, sender: str, msg: ChatMessage) -> None:
    text = extract_text(msg)
    text_l = (text or "").lower().strip()
    state = load_state(ctx, sender)

    awaiting_payment = bool(state.get("awaiting_payment"))
    pending = (
        state.get("pending_stripe")
        if isinstance(state.get("pending_stripe"), dict)
        else None
    )

    ctx.logger.info(
        "[chat] sender=%s session=%s text=%r awaiting_payment=%s",
        sender,
        ctx.session,
        text,
        awaiting_payment,
    )

    if awaiting_payment:
        if not pending:
            clear_state(ctx, sender)
            await ctx.send(
                sender,
                make_chat(
                    "Your previous payment session has expired or is invalid. "
                    "Please send a YouTube channel URL or name to start a new analysis."
                ),
            )
            return

        parsed_channel_id, parsed_handle = parse_youtube_channel_id_or_handle(text)
        has_explicit_locator = bool(
            parsed_channel_id
            or parsed_handle
            or ("youtube.com" in text_l)
            or ("youtu.be" in text_l)
        )
        if has_explicit_locator:
            clear_state(ctx, sender)
            # Fall through: run a new free analysis for the newly provided channel.
        elif _looks_like_new_intent(text_l):
            clear_state(ctx, sender)
            await ctx.send(
                sender,
                make_chat(
                    "Okay — send a YouTube channel URL or channel name to analyze."
                ),
            )
            return
        else:
            req = build_request_payment(
                agent_address=str(ctx.agent.address),
                reference=str(ctx.session),
                checkout=pending,
                description=f"Pay ${STRIPE_AMOUNT_CENTS / 100:.2f} to unlock the full premium YouTube growth report.",
            )
            await ctx.send(sender, req)
            await ctx.send(
                sender,
                make_chat(
                    "Payment is still pending. Complete the Stripe checkout (Pay) to unlock the full premium report."
                ),
            )
            return

    channel_input = extract_channel_locator(text)
    if not channel_input:
        await ctx.send(
            sender,
            make_chat(
                "Send a **YouTube channel URL** (e.g. `https://www.youtube.com/@SomeChannel`) "
                "or a **channel name** to search."
            ),
        )
        return

    # Run LangGraph free pipeline (fetch + preview only).
    try:
        result = await asyncio.to_thread(run_free_pipeline, channel_input)
    except Exception as e:
        logger.exception("Free pipeline failed")
        await ctx.send(
            sender, make_chat(f"Something went wrong while analyzing the channel: {e}")
        )
        return

    if result.get("error"):
        await ctx.send(
            sender,
            make_chat(f"Could not analyze that channel yet.\n\n{result['error']}"),
        )
        return

    preview_md = str(result.get("preview_markdown") or "")
    snapshot = result.get("snapshot")
    if not isinstance(snapshot, dict):
        await ctx.send(
            sender, make_chat("Unexpected internal error: missing channel snapshot.")
        )
        return

    description = f"{STRIPE_PRODUCT_NAME} — {snapshot.get('title', 'YouTube channel')}"
    checkout = await asyncio.to_thread(
        create_embedded_checkout_session,
        user_address=sender,
        chat_session_id=str(ctx.session),
        description=description,
    )

    expires_at = time.time() + STATE_TTL_SECONDS
    save_state(
        ctx,
        sender,
        {
            "awaiting_payment": True,
            "pending_stripe": checkout,
            "snapshot": snapshot,
            "channel_input": channel_input,
            "preview_markdown": preview_md,
            "expires_at": expires_at,
        },
    )

    req = build_request_payment(
        agent_address=str(ctx.agent.address),
        reference=str(ctx.session),
        checkout=checkout,
        description=f"Pay ${STRIPE_AMOUNT_CENTS / 100:.2f} to unlock the full premium YouTube growth report.",
    )
    try:
        await ctx.send(sender, req)
        await ctx.send(
            sender, make_chat(_compose_paywall_message(preview_md, checkout))
        )
    except Exception as e:
        logger.exception("Failed to send payment request or chat after free preview")
        await ctx.send(
            sender,
            make_chat(
                "Free preview was generated, but one payment message failed to deliver."
                " If you already see a Pay button, complete checkout and then confirm payment."
                f"\n\nError detail: {e}"
            ),
        )


async def on_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Chat handler with top-level error handling so clients always get a text reply when possible."""
    try:
        await _on_chat_impl(ctx, sender, msg)
    except Exception as e:
        logger.exception("on_chat failed")
        try:
            await ctx.send(
                sender,
                make_chat(
                    f"**Error**\n\n{type(e).__name__}: {e}\n\n"
                    "Check agent logs. Common causes: invalid YouTube/Stripe keys, or mailbox not connected in Agent Inspector."
                ),
            )
        except Exception as send_err:
            logger.exception("Could not send error ChatMessage: %s", send_err)


async def on_commit(ctx: Context, sender: str, msg: CommitPayment) -> None:
    if msg.funds.payment_method != "stripe" or not msg.transaction_id:
        await ctx.send(
            sender,
            RejectPayment(reason="Unsupported payment method (expected stripe)."),
        )
        return

    paid = await asyncio.to_thread(verify_checkout_session_paid, msg.transaction_id)
    if not paid:
        await ctx.send(
            sender,
            RejectPayment(
                reason="Stripe payment not completed yet. Please finish checkout."
            ),
        )
        return

    if not await asyncio.to_thread(
        verify_checkout_session_amount_usd, msg.transaction_id, STRIPE_AMOUNT_CENTS
    ):
        await ctx.send(
            sender,
            RejectPayment(reason="Paid amount mismatch — please contact support."),
        )
        return

    state = load_state(ctx, sender)
    pending = state.get("pending_stripe")
    pending_session_id = None
    if isinstance(pending, dict):
        pending_session_id = pending.get("checkout_session_id") or pending.get("id")

    if not state.get("awaiting_payment") or not isinstance(pending_session_id, str):
        await ctx.send(
            sender,
            RejectPayment(
                reason="No pending payment session found. Please request a new analysis."
            ),
        )
        return

    if msg.transaction_id != pending_session_id:
        await ctx.send(
            sender,
            RejectPayment(
                reason="Payment session mismatch. Please complete the currently requested checkout."
            ),
        )
        return

    snapshot = state.get("snapshot")
    if not isinstance(snapshot, dict):
        await ctx.send(
            sender,
            RejectPayment(
                reason="Missing internal session state. Please request a new analysis."
            ),
        )
        return

    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))

    try:
        premium = await asyncio.to_thread(run_premium_pipeline, snapshot)
    except Exception as e:
        logger.exception("Premium pipeline failed")
        await ctx.send(
            sender, make_chat(f"Payment verified, but report generation failed: {e}")
        )
        clear_state(ctx, sender)
        return

    if premium.get("error"):
        await ctx.send(
            sender,
            make_chat(
                f"Payment verified, but report generation failed:\n\n{premium['error']}"
            ),
        )
        clear_state(ctx, sender)
        return

    report = str(premium.get("premium_markdown") or "")
    footer = (
        "\n\n---\n\n"
        "_Thanks — if you want another channel, start a new message with a new URL or name._"
    )
    body = report + footer
    chunks = _chunk_text_for_chat(body, PREMIUM_REPORT_CHUNK_CHARS)
    total = len(chunks)
    ctx.logger.info(
        "Sending premium report in %s chat message(s), ~%s chars total (chunk limit=%s)",
        total,
        len(body),
        PREMIUM_REPORT_CHUNK_CHARS,
    )
    try:
        for i, chunk in enumerate(chunks):
            if i == 0:
                text = "**Premium report unlocked (paid)**\n\n" + chunk
            else:
                text = f"**(Premium report continued {i + 1}/{total})**\n\n{chunk}"
            await ctx.send(sender, make_chat(text))
    except Exception:
        logger.exception("Failed sending premium report chunk %d/%d", i + 1, total)
        try:
            await ctx.send(
                sender,
                make_chat(
                    f"Part of the premium report could not be delivered (chunk {i + 1}/{total}). "
                    "Please start a new analysis to regenerate the report — you will NOT be charged again."
                ),
            )
        except Exception:
            logger.exception("Could not notify user about chunk delivery failure")
    finally:
        clear_state(ctx, sender)


async def on_reject_payment(ctx: Context, sender: str, msg: RejectPayment) -> None:
    clear_state(ctx, sender)
    await ctx.send(sender, make_chat(f"Payment flow ended. {msg.reason or ''}".strip()))


def build_chat_proto(on_chat_handler: ChatHandler) -> Protocol:
    proto = Protocol(spec=chat_protocol_spec)

    @proto.on_message(ChatMessage)
    async def _on_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )
        await on_chat_handler(ctx, sender, msg)

    @proto.on_message(ChatAcknowledgement)
    async def _on_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
        return

    return proto


def build_payment_proto(
    on_commit: Callable[[Context, str, CommitPayment], Awaitable[None]],
    on_reject: Callable[[Context, str, RejectPayment], Awaitable[None]],
) -> Protocol:
    proto = Protocol(spec=payment_protocol_spec, role="seller")

    @proto.on_message(CommitPayment)
    async def _on_commit(ctx: Context, sender: str, msg: CommitPayment) -> None:
        await on_commit(ctx, sender, msg)

    @proto.on_message(RejectPayment)
    async def _on_reject(ctx: Context, sender: str, msg: RejectPayment) -> None:
        await on_reject(ctx, sender, msg)

    return proto


def main() -> None:
    # Logs show up immediately in terminals and IDEs (especially on macOS).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except Exception:
            pass

    # Validate critical env early for clearer failures.
    from config import (
        get_stripe_publishable_key,
        get_stripe_secret_key,
        get_stripe_success_url,
        get_youtube_api_key,
    )

    _ = get_youtube_api_key()
    _ = get_stripe_secret_key()
    _ = get_stripe_publishable_key()
    _ = get_stripe_success_url()

    use_mailbox = os.getenv("USE_MAILBOX", "true").lower() == "true"

    # ASI:One / Agentverse: must use the Agentverse mailbox URL as the registered endpoint.
    # If you pass `endpoint=http://127.0.0.1:...` together with `mailbox=True`, uAgents keeps
    # localhost and does NOT use the mailbox — `is_mailbox_agent` is false and remote chat fails.
    endpoint: str | list[str] | None
    if use_mailbox:
        endpoint = None
    else:
        endpoint = [f"http://127.0.0.1:{AGENT_PORT}/submit"]

    agent = Agent(
        name="youtube-growth-analyzer-agent",
        port=AGENT_PORT,
        seed=os.getenv(
            "AGENT_SEED", "youtube growth analyzer agent secure recovery seed phrase"
        ),
        endpoint=endpoint,
        mailbox=use_mailbox,
        enable_agent_inspector=True,
        description=(
            "Multi-agent YouTube growth analyzer: free preview, then $5 Stripe checkout for a full report. "
            "Innovation Lab example (chat + seller payment protocols)."
        ),
        metadata={
            "tags": [
                "innovationlab",
                "youtube",
                "stripe",
                "langgraph",
                "asi1",
                "agent-chat-protocol",
            ],
            "protocols": ["AgentChatProtocol", "AgentPaymentProtocol"],
            "payment": {
                "currency": "USD",
                "amount": "5.00",
                "rail": "stripe_embedded_checkout",
            },
        },
    )

    agent.include(build_chat_proto(on_chat), publish_manifest=True)
    agent.include(
        build_payment_proto(on_commit, on_reject_payment), publish_manifest=True
    )

    av_token = (os.getenv("AGENTVERSE_API_TOKEN") or "").strip()
    if use_mailbox and av_token:
        schedule_mailbox_registration(AGENT_PORT, av_token)
        logger.info(
            "AGENTVERSE_API_TOKEN is set — mailbox registration will POST /connect after "
            "MAILBOX_CONNECT_DELAY_SECONDS (default 15s), with retries."
        )
    elif use_mailbox:
        logger.warning(
            "No AGENTVERSE_API_TOKEN in .env — add your Agentverse profile API token, "
            "or open Agent Inspector → Connect → Mailbox. ASI:One will not work until the mailbox exists."
        )

    logger.info(
        "Agent address (use in ASI:One): %s | health: curl -s http://127.0.0.1:%s/agent_info",
        agent.address,
        AGENT_PORT,
    )

    @agent.on_event("startup")
    async def _log_mailbox_help(ctx: Context) -> None:
        if os.getenv("LOG_MAILBOX_HELP", "true").lower() not in ("1", "true", "yes"):
            return
        ctx.logger.info(
            "Remote chat requires an Agentverse mailbox. "
            "Set AGENTVERSE_API_TOKEN or use Inspector → Connect → Mailbox. "
            "Docs: https://uagents.fetch.ai/docs/agentverse/mailbox"
        )

    agent.run()


if __name__ == "__main__":
    main()
