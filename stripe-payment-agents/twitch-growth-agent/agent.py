"""Twitch growth uAgent: entry point.

Wires together the payment and chat protocols and owns the two background
interval loops (reactive monitor + OAuth-resume drain).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from dotenv import load_dotenv
from uagents import Agent, Context

from growth_pipeline import llm
from twitch.callback import drain_resume_signals, start_callback_server
import twitch.store as oauth_store
import twitch.reactive as reactive

from app_state import listener_manager
from protocols.chat_proto import (
    chat_proto,
    _announce_noticed,
    _ANNOUNCE_COLOR,
    _proactive_send_card,
    _resume_after_connect,
    _send_succeeded,
    build_reactive_offer_card,
    build_smart_announce_card,
    resolve_user_key,
)
from protocols.payment_proto import payment_proto

load_dotenv()
logger = logging.getLogger(__name__)

# Address is derived from AGENT_SEED, so it stays stable across restarts.
agent = Agent(
    name="twitch_growth_agent",
    seed=os.getenv("AGENT_SEED", "twitch-growth-agent-dev-seed"),
    port=8001,
    network="testnet",
    mailbox=os.getenv("AGENT_MAILBOX", "true").lower() in ("1", "true", "yes"),
    publish_agent_details=True,
    readme_path=os.getenv("AGENT_README", "agent_readme.md"),
    description=(
        "Analyzes a Twitch channel and produces a growth strategy report, plus "
        "channel actions (setup, announcements, chat settings, raids, clips). Free "
        "chat preview (channel + niche); a one-time $4.99 Stripe payment unlocks "
        "everything."
    ),
)

agent.include(payment_proto, publish_manifest=True)
agent.include(chat_proto, publish_manifest=True)

# How often the reactive monitor checks each live user's buffer for trouble.
MONITOR_INTERVAL_SECONDS = 20

# Short, so resume after the OAuth callback feels near-instant.
CONNECT_RESUME_POLL_SECONDS = 5


@agent.on_interval(period=MONITOR_INTERVAL_SECONDS)
async def _monitor_live_chat(ctx: Context):
    """Reactive copilot: for each user with a running listener, check both
    moderation (raid/spam) and celebration (cheer/sub) moments every tick, and
    send at most one card per tick — moderation wins, each has its own cooldown.
    """
    now = time.time()
    active = listener_manager.active_users()
    ctx.logger.info(f"reactive monitor tick: active_users={active}")
    for user_id in active:
        try:
            chat_signal = reactive.evaluate(user_id)
            ann_moment = reactive.evaluate_announcement(user_id)

            if chat_signal and not reactive.on_cooldown(user_id, now):
                status = await _proactive_send_card(
                    ctx,
                    user_id,
                    build_reactive_offer_card(
                        chat_signal["kind"],
                        chat_signal["setting"],
                        chat_signal["label"],
                    ),
                    chat_signal["noticed"],
                    f"5c {chat_signal['kind']}",
                )
                if _send_succeeded(status):
                    reactive.mark_offered(user_id, now)

            elif ann_moment and not reactive.announce_on_cooldown(user_id, now):
                draft = await asyncio.to_thread(
                    reactive.draft_announcement, ann_moment, llm
                )
                color = _ANNOUNCE_COLOR.get(ann_moment["kind"], "primary")
                ctx.storage.set(
                    f"pending_announcement:{user_id}",
                    {"message": draft, "color": color},
                )
                status = await _proactive_send_card(
                    ctx,
                    user_id,
                    build_smart_announce_card(draft),
                    _announce_noticed(ann_moment),
                    f"5d {ann_moment['kind']}",
                )
                if _send_succeeded(status):
                    reactive.mark_announced(user_id, now)

            else:
                ctx.logger.info(
                    f"  {user_id}: no offer this tick "
                    f"(chat={chat_signal and chat_signal['kind']}, "
                    f"ann={ann_moment and ann_moment['kind']})"
                )
        except Exception as exc:  # noqa: BLE001 - one user must not break the monitor
            ctx.logger.error(
                f"Reactive monitor error for {user_id}: {exc}", exc_info=True
            )


@agent.on_interval(period=CONNECT_RESUME_POLL_SECONDS)
async def _drain_connect_resumes(ctx: Context):
    """Drain resume signals queued by twitch/callback.py (which has no agent
    Context of its own) and deliver the pending feature into the user's thread.
    """
    for signal_data in drain_resume_signals():
        sender = signal_data.get("sender")
        if not sender:
            continue
        user_id = resolve_user_key(sender)
        job = ctx.storage.get(f"pending_connect:{user_id}") or signal_data.get(
            "pending"
        )
        ctx.storage.remove(f"pending_connect:{user_id}")
        try:
            await _resume_after_connect(ctx, sender, user_id, job)
        except Exception as exc:  # noqa: BLE001 - one resume must not kill the loop
            ctx.logger.error(
                f"connect-resume failed for {user_id}: {exc}", exc_info=True
            )


@agent.on_event("startup")
async def _on_startup(ctx: Context):
    ctx.logger.info(f"twitch_growth_agent ready: address={agent.address}")


@agent.on_event("shutdown")
async def _on_shutdown(ctx: Context):
    ctx.logger.info("twitch_growth_agent shutting down")


if __name__ == "__main__":
    oauth_store.init_db()
    start_callback_server()
    agent.run()
