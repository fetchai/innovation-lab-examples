#!/usr/bin/env python3
"""
Fetch.ai uAgent wrapper for restaurant recommendations.

This keeps the existing recommendation logic unchanged by invoking:
  npx tsx src/agent/cli.ts "<query>"

Run:
  python src/fetch_uagent.py

Required:
  - MCP server running separately (npm run dev)
  - Node deps installed (npm install)
  - Python deps: pip install -r requirements-fetch-uagent.txt
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from uuid import uuid4

from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from stripe_checkout import (
    create_embedded_checkout_session,
    create_hosted_checkout_session,
    get_amount_cents,
    is_configured as stripe_is_configured,
    verify_checkout_session_paid,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PORT = int(os.getenv("FETCH_UAGENT_PORT", "8000"))
DEFAULT_NAME = os.getenv("FETCH_UAGENT_NAME", "restaurant_recommendation_uagent")
DEFAULT_SEED = os.getenv(
    "FETCH_UAGENT_SEED",
    "replace-this-with-your-own-strong-seed-phrase-please",
)
DEFAULT_ENDPOINT = os.getenv("FETCH_UAGENT_ENDPOINT", "").strip()
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY", "").strip()
MAILBOX_ENABLED = os.getenv("FETCH_UAGENT_MAILBOX", "true").lower() in {
    "1",
    "true",
    "yes",
}

FREE_REQUEST_LIMIT = int(os.getenv("FREE_REQUEST_LIMIT", "3"))

# Agentverse chat can use a different `sender` per message; per-sender counters then never
# reach the limit. Use "global" (default) for one shared quota, or "sender" for strict per-peer.
def _paywall_state_key(sender: str) -> str:
    mode = (os.getenv("PAYWALL_SCOPE", "global") or "global").lower().strip()
    if mode in ("sender", "per_sender", "peer"):
        return sender
    return "__global__"


class RequestMessage(Model):
    text: str


class ResponseMessage(Model):
    text: str


class RecommendResult:
    def __init__(self, ok: bool, text: str):
        self.ok = ok
        self.text = text


@dataclass
class UserGateState:
    """Per-sender usage and payment state (in-memory; restarts reset)."""

    requests_used: int = 0
    paid_unlocked: bool = False
    pending_query: str = ""
    pending_checkout_session_id: str = ""


_gate_state_by_sender: Dict[str, UserGateState] = {}


def _gate_state(sender: str) -> UserGateState:
    key = _paywall_state_key(sender)
    state = _gate_state_by_sender.get(key)
    if state is None:
        state = UserGateState()
        _gate_state_by_sender[key] = state
    return state


def _paywall_chat_text() -> str:
    amount_cents = get_amount_cents()
    amount_usd = f"{amount_cents / 100:.2f}"
    return (
        f"You've used your {FREE_REQUEST_LIMIT} free requests. "
        f"Please pay ${amount_usd} via Stripe to continue."
    )


def build_stripe_checkout_for_gate(sender: str, state: UserGateState) -> dict | None:
    """
    Create a Stripe Checkout payload for RequestPayment.metadata[\"stripe\"].

    Prefer hosted checkout so chat can include a real pay link; fall back to embedded.
    """
    if not stripe_is_configured():
        return None
    corr = state.pending_checkout_session_id or str(uuid4())
    checkout = create_hosted_checkout_session(
        user_address=sender,
        chat_session_id=corr,
        description="Unlock unlimited restaurant discovery queries.",
    )
    if not checkout:
        checkout = create_embedded_checkout_session(
            user_address=sender,
            chat_session_id=corr,
            description="Unlock unlimited restaurant discovery queries.",
        )
    if not checkout:
        return None
    state.pending_checkout_session_id = checkout.get("checkout_session_id", "")
    return checkout


def _paywall_user_message(checkout: dict | None) -> str:
    msg = _paywall_chat_text()
    if checkout and checkout.get("checkout_url"):
        msg += f"\n\n[Pay with Stripe]({checkout['checkout_url']})"
    elif checkout and checkout.get("client_secret"):
        msg += (
            "\n\nIf you do not see a Pay card above, reload the chat or open the "
            "agent in Agentverse — payment uses the embedded Stripe checkout."
        )
    return msg


async def _emit_request_payment(ctx: Context, sender: str, checkout: dict) -> None:
    amount_cents = get_amount_cents()
    amount_usd = f"{amount_cents / 100:.2f}"
    req = RequestPayment(
        accepted_funds=[Funds(currency="USD", amount=amount_usd, payment_method="stripe")],
        recipient=str(ctx.agent.address),
        description=f"Pay ${amount_usd} to continue using restaurant discovery.",
        metadata={"stripe": checkout, "service": "restaurant_discovery"},
    )
    await ctx.send(sender, req)


def _clean_cli_output(raw: str) -> str:
    lines = [line.rstrip() for line in raw.splitlines()]
    filtered: list[str] = []
    for line in lines:
        if line.startswith("[dotenv@"):
            continue
        if line.startswith("> mcp-restaurant-booking@"):
            continue
        if line.startswith("> tsx "):
            continue
        filtered.append(line)
    while filtered and filtered[0] == "":
        filtered.pop(0)
    while filtered and filtered[-1] == "":
        filtered.pop()
    return "\n".join(filtered).strip()


def _run_recommender_cli(query: str) -> RecommendResult:
    cmd = ["npx", "tsx", "src/agent/cli.ts", query]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )

    if proc.returncode == 0:
        out = _clean_cli_output(proc.stdout)
        if out:
            return RecommendResult(ok=True, text=out)
        return RecommendResult(ok=False, text="Empty response from recommendation CLI.")

    err = _clean_cli_output(proc.stderr or proc.stdout)
    return RecommendResult(ok=False, text=err or "Recommendation CLI failed.")


async def recommend(query: str) -> RecommendResult:
    return await asyncio.to_thread(_run_recommender_cli, query)


def _chat_text_message(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


agent_kwargs = {
    "name": DEFAULT_NAME,
    "seed": DEFAULT_SEED,
    "port": DEFAULT_PORT,
    "mailbox": MAILBOX_ENABLED,
}
if DEFAULT_ENDPOINT:
    agent_kwargs["endpoint"] = [DEFAULT_ENDPOINT]
if AGENTVERSE_API_KEY:
    agent_kwargs["agentverse"] = {"api_key": AGENTVERSE_API_KEY}

agent = Agent(**agent_kwargs)
protocol = Protocol(name="RestaurantRecommendationProtocol", version="1.0.0")
chat_protocol = Protocol(spec=chat_protocol_spec)
payment_protocol = Protocol(spec=payment_protocol_spec, role="seller")


@agent.on_event("startup")
async def startup(ctx: Context) -> None:
    endpoint = f"http://127.0.0.1:{DEFAULT_PORT}"
    ctx.logger.info("uAgent started")
    ctx.logger.info("Name: %s", DEFAULT_NAME)
    ctx.logger.info("Address: %s", agent.address)
    ctx.logger.info("Port: %s", DEFAULT_PORT)
    ctx.logger.info("Local endpoint: %s", endpoint)
    ctx.logger.info("Mailbox enabled: %s", MAILBOX_ENABLED)
    if DEFAULT_ENDPOINT:
        ctx.logger.info("Advertised endpoint: %s", DEFAULT_ENDPOINT)
    ctx.logger.info("Ensure MCP server is running at http://127.0.0.1:3000/mcp")
    ctx.logger.info(
        "Payment: after %s free requests, Stripe via Agent Payment Protocol (seller).",
        FREE_REQUEST_LIMIT,
    )
    ctx.logger.info(
        "Paywall scope: %s (set PAYWALL_SCOPE=sender for per-peer limits).",
        (os.getenv("PAYWALL_SCOPE", "global") or "global").lower(),
    )


@protocol.on_message(RequestMessage, replies=ResponseMessage)
async def handle_request(ctx: Context, sender: str, msg: RequestMessage) -> None:
    query = (msg.text or "").strip()
    if not query:
        await ctx.send(sender, ResponseMessage(text="Missing request text."))
        return

    state = _gate_state(sender)
    # Hosted Checkout may complete in the browser without CommitPayment; unlock on next message.
    if not state.paid_unlocked and state.pending_checkout_session_id:
        if verify_checkout_session_paid(state.pending_checkout_session_id):
            state.paid_unlocked = True
            pending = state.pending_query
            state.pending_query = ""
            state.pending_checkout_session_id = ""
            if pending:
                result = await recommend(pending)
                if result.ok:
                    await ctx.send(sender, ResponseMessage(text=result.text))
                else:
                    await ctx.send(
                        sender,
                        ResponseMessage(
                            text=f"Failed to get recommendations: {result.text}"
                        ),
                    )
                return

    if state.paid_unlocked:
        result = await recommend(query)
        if result.ok:
            await ctx.send(sender, ResponseMessage(text=result.text))
        else:
            await ctx.send(
                sender, ResponseMessage(text=f"Failed to get recommendations: {result.text}")
            )
        return

    if state.requests_used >= FREE_REQUEST_LIMIT:
        state.pending_query = query
        checkout = build_stripe_checkout_for_gate(sender, state)
        await ctx.send(sender, ResponseMessage(text=_paywall_user_message(checkout)))
        if checkout:
            await _emit_request_payment(ctx, sender, checkout)
        else:
            await ctx.send(
                sender,
                ResponseMessage(
                    text="Stripe is not configured or checkout failed. "
                    "Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY, then restart the agent."
                ),
            )
        return

    result = await recommend(query)
    if result.ok:
        state.requests_used += 1
        await ctx.send(sender, ResponseMessage(text=result.text))
    else:
        await ctx.send(
            sender, ResponseMessage(text=f"Failed to get recommendations: {result.text}")
        )


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_ack(
    ctx: Context, sender: str, msg: ChatAcknowledgement
) -> None:
    ctx.logger.info(
        "Got chat acknowledgement from %s for msg_id=%s",
        sender,
        msg.acknowledged_msg_id,
    )


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    if msg.msg_id:
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )

    query = msg.text().strip() if hasattr(msg, "text") else ""
    if not query:
        await ctx.send(sender, _chat_text_message("Please send a text query."))
        return

    state = _gate_state(sender)
    # Hosted Checkout may complete in the browser without CommitPayment; unlock on next message.
    if not state.paid_unlocked and state.pending_checkout_session_id:
        if verify_checkout_session_paid(state.pending_checkout_session_id):
            state.paid_unlocked = True
            pending = state.pending_query
            state.pending_query = ""
            state.pending_checkout_session_id = ""
            if pending:
                result = await recommend(pending)
                response_text = (
                    result.text if result.ok else f"Failed to get recommendations: {result.text}"
                )
                await ctx.send(sender, _chat_text_message(response_text))
                return

    if state.paid_unlocked:
        result = await recommend(query)
        response_text = (
            result.text if result.ok else f"Failed to get recommendations: {result.text}"
        )
        await ctx.send(sender, _chat_text_message(response_text))
        return

    if state.requests_used >= FREE_REQUEST_LIMIT:
        state.pending_query = query
        checkout = build_stripe_checkout_for_gate(sender, state)
        await ctx.send(sender, _chat_text_message(_paywall_user_message(checkout)))
        if checkout:
            await _emit_request_payment(ctx, sender, checkout)
        else:
            await ctx.send(
                sender,
                _chat_text_message(
                    "Stripe is not configured or checkout failed. "
                    "Set STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY, then restart the agent."
                ),
            )
        return

    result = await recommend(query)
    if result.ok:
        state.requests_used += 1
    response_text = (
        result.text if result.ok else f"Failed to get recommendations: {result.text}"
    )
    await ctx.send(sender, _chat_text_message(response_text))


@payment_protocol.on_message(CommitPayment)
async def handle_commit_payment(ctx: Context, sender: str, msg: CommitPayment) -> None:
    state = _gate_state(sender)
    if msg.funds.payment_method != "stripe" or not msg.transaction_id:
        await ctx.send(
            sender,
            RejectPayment(reason="Unsupported payment method (expected stripe checkout session id)."),
        )
        return

    if not verify_checkout_session_paid(msg.transaction_id):
        await ctx.send(
            sender,
            RejectPayment(reason="Stripe payment not completed yet. Please finish checkout."),
        )
        return

    state.paid_unlocked = True
    state.pending_checkout_session_id = msg.transaction_id
    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))

    pending = state.pending_query
    state.pending_query = ""
    if pending:
        result = await recommend(pending)
        response_text = (
            result.text if result.ok else f"Failed to get recommendations: {result.text}"
        )
        await ctx.send(sender, _chat_text_message(response_text))
    else:
        await ctx.send(
            sender,
            _chat_text_message("Payment confirmed. You're unlocked — ask me anything."),
        )


@payment_protocol.on_message(RejectPayment)
async def handle_reject_payment(ctx: Context, sender: str, msg: RejectPayment) -> None:
    ctx.logger.info("RejectPayment from %s: %s", sender, msg.reason)


if __name__ == "__main__":
    agent.include(protocol, publish_manifest=True)
    agent.include(chat_protocol, publish_manifest=True)
    agent.include(payment_protocol, publish_manifest=True)
    agent.run()
