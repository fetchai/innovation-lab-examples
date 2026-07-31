import asyncio
import json
import os
import re
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from payments import (  # noqa: E402
    BRIEF_KEY,
    HISTORY_KEY,
    ORIG_QUERY_KEY,
    clear_brief_state,
    clear_state,
    deliver_brief_after_stripe_confirm,
    payment_proto,
    request_payment_from_user,
    retry_paid_brief,
)
from workflow import answer_followup  # noqa: E402

# Agent setup
agent = Agent(
    name=os.getenv("AGENT_NAME", "Hackflow"),
    seed=os.environ["AGENT_SEED"],
    port=int(os.getenv("AGENT_PORT", "8008")),
    mailbox=True,
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)

AMOUNT_DISPLAY = f"${int(os.getenv('STRIPE_AMOUNT_CENTS', '100')) / 100:.2f}"

# ASI:One Stripe confirm pattern: <stripe:payment_id:UUID:CONFIRM>
_STRIPE_CONFIRM_RE = re.compile(r"^<stripe:payment_id:.+:CONFIRM>$")

_RESET_COMMANDS = {"cancel", "new search", "reset", "start over", "new query"}


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"[agent] {agent.name} | {agent.address}")
    port = os.getenv("AGENT_PORT", "8008")
    ctx.logger.info(
        f"[agent] Inspector: https://agentverse.ai/inspect/"
        f"?uri=http://127.0.0.1:{port}&address={agent.address}"
    )


@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(tz=timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    # Each ASI:One "New Chat" window gets a different ctx.session UUID.
    current_session = str(ctx.session)
    stored_session = ctx.storage.get(f"hackflow:session:{sender}")
    if stored_session and stored_session != current_session:
        ctx.logger.info(
            f"[agent] New chat session for {sender} "
            f"(prev={stored_session[:8]}… → cur={current_session[:8]}…) "
            "— full state reset (State A)"
        )
        clear_state(ctx, sender)  # wipe pending checkout/paid flag
        clear_brief_state(ctx, sender)  # wipe stored brief and history
    ctx.storage.set(f"hackflow:session:{sender}", current_session)

    user_text = next((b.text for b in msg.content if hasattr(b, "text")), "").strip()
    user_text = re.sub(r"^@\S+\s+", "", user_text).strip()

    if not user_text:
        await _send_text(
            ctx, sender, "Please describe the hackathon you want to research."
        )
        return

    # Stripe confirm message from ASI:One
    if _STRIPE_CONFIRM_RE.match(user_text):
        ctx.logger.info(f"[agent] Stripe confirm from {sender}")
        delivered = await deliver_brief_after_stripe_confirm(ctx, sender)
        if not delivered:
            await _send_text(
                ctx,
                sender,
                "Payment signal received but Stripe still shows unpaid. "
                "Wait a moment and send any message to retry.",
            )
        return

    # State D: brief already delivered, answer follow-ups for free
    stored_brief = ctx.storage.get(BRIEF_KEY.format(sender))
    if stored_brief:
        if user_text.lower() in _RESET_COMMANDS:
            clear_state(ctx, sender)
            clear_brief_state(ctx, sender)
            await _send_text(
                ctx, sender, "Starting fresh — send me your new hackathon query."
            )
            return
        original_query = ctx.storage.get(ORIG_QUERY_KEY.format(sender)) or ""

        # Load the conversation history for this session (last 10 turns max).
        history: list[dict] = json.loads(
            ctx.storage.get(HISTORY_KEY.format(sender)) or "[]"
        )

        ctx.logger.info(f"[agent] Follow-up (free) from {sender}: {user_text[:80]}")
        try:
            answer = await asyncio.to_thread(
                answer_followup, stored_brief, original_query, user_text, history
            )
        except Exception as exc:
            ctx.logger.error(f"[agent] answer_followup error: {exc}")
            answer = (
                "Hit an API limit on that follow-up — please try again in a moment."
            )

        # Persist this turn as alternating role/content dicts in the same format
        # that answer_followup reconstructs into HumanMessage / AIMessage objects.
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": answer})
        ctx.storage.set(HISTORY_KEY.format(sender), json.dumps(history[-20:]))

        await _send_text(ctx, sender, f"{answer}\n\n---\n")
        return

    # State C: paid, brief not yet delivered (retry for free)
    paid = ctx.storage.get(f"hackflow:paid:{sender}")
    if paid:
        if user_text.lower() in _RESET_COMMANDS:
            clear_state(ctx, sender)
            clear_brief_state(ctx, sender)
            await _send_text(
                ctx, sender, "Session cancelled. Send a new query to start over."
            )
            return

        original_query = ctx.storage.get(f"hackflow:query:{sender}") or user_text
        _silent_retry = user_text.lower() in (
            "retry",
            "try again",
            "yes",
            "ok",
            "sure",
            "",
        )
        if _silent_retry:
            combined = original_query
        else:
            # User named a specific hackathon, use it as the focused query
            combined = f"{original_query} — focusing on: {user_text}"
        ctx.logger.info(f"[agent] Paid retry from {sender}: {combined[:80]}")
        await retry_paid_brief(ctx, sender, combined_query=combined)
        return

    # State B: waiting for Stripe payment
    pending_query = ctx.storage.get(f"hackflow:query:{sender}")
    if pending_query:
        if user_text.lower() in _RESET_COMMANDS:
            clear_state(ctx, sender)
            clear_brief_state(ctx, sender)
            await _send_text(
                ctx, sender, "Session cancelled. Send a new query to start over."
            )
        else:
            await _send_text(
                ctx,
                sender,
                f"Still waiting for your {AMOUNT_DISPLAY} payment — "
                "check the card form above in the chat. "
                "Type 'new search' to start over with a different query.",
            )
        return

    # State A: new query (request payment immediately)
    ctx.logger.info(f"[agent] New query from {sender}: {user_text[:80]}")
    await _send_text(
        ctx,
        sender,
        "Welcome to Hackflow! AI agent specialized in hackathon competitive intelligence.",
    )
    await request_payment_from_user(ctx, sender, query=user_text)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"[agent] Ack from {sender} for {msg.acknowledged_msg_id}")


async def _send_text(ctx: Context, recipient: str, text: str) -> None:
    await ctx.send(
        recipient,
        ChatMessage(
            timestamp=datetime.now(tz=timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        ),
    )


agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
