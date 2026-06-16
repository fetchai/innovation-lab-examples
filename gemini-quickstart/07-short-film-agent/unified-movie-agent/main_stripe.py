"""
Unified Movie Agent — Stripe-gated entry point.

Same pipeline as main.py, but requires Stripe payment before film production.
Uses a different seed so it registers as a separate agent for testing.

Flow:
  1. User sends prompt (+ optional ref image URLs)
  2. Agent stores prompt, creates Stripe Checkout session, sends RequestPayment
  3. User pays via embedded Stripe Checkout in Agentverse UI
  4. UI sends CommitPayment → agent verifies with Stripe → CompletePayment
  5. Agent runs the full film production pipeline
  6. Film result links sent back to the user

Run:  python main_stripe.py
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (  # noqa: E402
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
)

from config import SCENE_COUNT  # noqa: E402
from pipeline.orchestrator import produce_film  # noqa: E402
from payment_proto import build_payment_proto  # noqa: E402
from stripe_payments import (  # noqa: E402
    STRIPE_AMOUNT_CENTS,
    STRIPE_CURRENCY,
    create_embedded_checkout_session,
    verify_checkout_session_paid,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main_stripe")


# ── Agent (different seed + port from main.py) ────────────────────

AGENT_NAME = "unified_movie_agent_stripe"
AGENT_SEED = "unified-movie-agent-stripe-seed-2025"
AGENT_PORT = 8002  # different port from main.py (8001)

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)


# ── Helpers ────────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://\S+")


def _extract(raw: str):
    """Extract up to 3 image URLs and the remaining prompt text."""
    urls = _URL_RE.findall(raw)
    prompt = raw
    for u in urls:
        prompt = prompt.replace(u, "")
    return urls[:3], prompt.strip()


def _chat_msg(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=str(uuid4()),
        content=[TextContent(text=text, type="text")],
    )


# ── State helpers (per-sender, stored in ctx.storage) ─────────────


def _state_key(sender: str) -> str:
    return f"film_payment_state:{sender}"


def _load_state(ctx: Context, sender: str) -> dict:
    raw = ctx.storage.get(_state_key(sender))
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}


def _save_state(ctx: Context, sender: str, state: dict) -> None:
    ctx.storage.set(_state_key(sender), json.dumps(state))


def _clear_state(ctx: Context, sender: str) -> None:
    ctx.storage.set(_state_key(sender), "{}")


# ── Request queue (one film at a time) ─────────────────────────────

_active: Optional[str] = None  # request-id of in-flight film
_queue: List[Dict[str, Any]] = []  # waiting requests


async def _process_queue(ctx: Context) -> None:
    global _active
    if not _queue:
        _active = None
        log.info("Queue empty — ready for new requests.")
        return
    nxt = _queue.pop(0)
    for i, q in enumerate(_queue):
        await ctx.send(
            q["user"], _chat_msg(f"⏳ Queue update: you are now #{i + 1} in line.")
        )
    await _run_film(ctx, nxt["user"], nxt["prompt"], nxt["refs"])


async def _run_film(ctx: Context, user: str, prompt: str, refs: List[str]) -> None:
    """Kick off the full pipeline and stream progress to the user."""
    global _active
    request_id = str(uuid4())
    _active = request_id

    log.info("▶️  Processing request %s from %s…", request_id, user[:16])

    async def notify(msg: str) -> None:
        await ctx.send(user, _chat_msg(msg))

    result = await produce_film(
        user_prompt=prompt,
        ref_urls=refs,
        notify=notify,
    )

    if result.error:
        log.warning("Film failed: %s", result.error)
        if not result.final_url:
            await notify(
                f"🛑 **Film production failed.**\n"
                f"Reason: {result.error}\n\n"
                f"Please try again with a different prompt."
            )
    else:
        # Build final consolidated message with all per-scene links
        lines = [
            f"🎉 **Your full {SCENE_COUNT}-scene AI film is ready!**\n",
            f"📖 **Title:** {result.title}",
            f"🧵 **Logline:** {result.logline}\n",
        ]
        for s in result.scenes:
            lines.append(f"**Scene {s.scene_index}: {s.scene_title}**")
            if s.video_url:
                lines.append(f"🎥 Video: [View]({s.video_url})")
            if s.voice_url:
                lines.append(f"🗣️ Voice: [Listen]({s.voice_url})")
            if s.music_url:
                lines.append(f"🎵 Music: [Listen]({s.music_url})")
            if s.assembled_url:
                lines.append(f"📽️ Assembled: [Watch]({s.assembled_url})")
            lines.append("")
        if result.final_url:
            lines.append(f"📽️ **[Watch Full Movie]({result.final_url})**\n")
            lines.append(f"**Final Movie:**\n")  # noqa: F541
            lines.append(f"![]({result.final_url})\n")
        lines.append("Thank you for creating with the Unified Movie Agent ✨")
        await notify("\n".join(lines))

    log.info("✅ Request %s complete.", request_id)
    await _process_queue(ctx)


# ── Chat handler (payment-gated) ──────────────────────────────────


@chat_proto.on_message(ChatMessage)
async def handle_user_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    # Extract text
    full_text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            full_text += item.text + "\n"
    full_text = full_text.strip()
    if not full_text:
        return

    # Acknowledge
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    refs, prompt = _extract(full_text)
    log.info("📨 New request from %s — prompt: %s", sender[:16], prompt[:100])

    # Always clear any old payment state and create a fresh checkout.
    # ctx.storage persists across restarts, so old sessions go stale.
    _clear_state(ctx, sender)
    log.info("Cleared old state for %s — creating fresh Stripe checkout", sender[:16])

    # ── Payment flow: store prompt + create Stripe checkout ──────

    description = f"{SCENE_COUNT}-scene AI cinematic short film"
    try:
        checkout = await asyncio.to_thread(
            create_embedded_checkout_session,
            user_address=sender,
            chat_session_id=str(ctx.session),
            description=description,
        )
    except Exception as e:
        log.error("Stripe checkout creation failed: %s", e, exc_info=True)
        await ctx.send(
            sender,
            _chat_msg(
                f"❌ **Payment setup failed.** Could not create Stripe checkout session.\n"
                f"Error: {e}\n\nPlease try again."
            ),
        )
        return

    log.info(
        "Stripe checkout created: session_id=%s, has_client_secret=%s, has_publishable_key=%s",
        checkout.get("checkout_session_id"),
        bool(checkout.get("client_secret")),
        bool(checkout.get("publishable_key")),
    )

    # Store the prompt, refs, and checkout session in state
    state = {
        "prompt": prompt,
        "refs": refs,
        "awaiting_payment": True,
        "pending_stripe": checkout,
        "expires_at": time.time() + 30 * 60,  # 30 min TTL
    }
    _save_state(ctx, sender, state)

    # Send RequestPayment FIRST (triggers Stripe checkout UI in Agentverse)
    amount_str = f"{STRIPE_AMOUNT_CENTS / 100:.2f}"
    req = RequestPayment(
        accepted_funds=[
            Funds(currency="USD", amount=amount_str, payment_method="stripe")
        ],
        recipient=str(ctx.agent.address),
        deadline_seconds=300,
        reference=str(ctx.session),
        description=f"Pay ${amount_str} to generate your {SCENE_COUNT}-scene AI film.",
        metadata={"stripe": checkout, "service": "ai_film_generation"},
    )
    await ctx.send(sender, req)
    # Chat message AFTER RequestPayment (UI needs RequestPayment first to render checkout)
    await ctx.send(
        sender,
        _chat_msg(
            "Once payment completes, I'll start generating your film automatically."
        ),
    )

    log.info("💳 RequestPayment sent for %s — awaiting payment", sender[:16])


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    pass


# ── Payment handlers ──────────────────────────────────────────────


async def on_commit(ctx: Context, sender: str, msg: CommitPayment) -> None:
    """Called when the UI sends CommitPayment after user completes Stripe checkout."""
    try:
        log.info("💰 CommitPayment received from %s", sender[:16])
        log.info("   transaction_id=%s", msg.transaction_id)
        log.info("   funds=%s", msg.funds)
        log.info(
            "   payment_method=%s",
            getattr(msg.funds, "payment_method", None) if msg.funds else None,
        )

        # Defensive: check funds exists before accessing payment_method
        payment_method = (  # noqa: F841
            getattr(msg.funds, "payment_method", None) if msg.funds else None
        )
        if not msg.transaction_id:
            log.warning("No transaction_id in CommitPayment")
            await ctx.send(sender, RejectPayment(reason="Missing transaction ID."))
            return

        # Verify with Stripe
        log.info("Verifying payment with Stripe: session_id=%s", msg.transaction_id)
        paid = await asyncio.to_thread(verify_checkout_session_paid, msg.transaction_id)
        log.info("Stripe verification result: paid=%s", paid)
        if not paid:
            await ctx.send(
                sender,
                RejectPayment(
                    reason="Stripe payment not completed yet. Please finish checkout."
                ),
            )
            return

        # Payment verified — send CompletePayment
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
        log.info("✅ Payment verified for %s — CompletePayment sent", sender[:16])

        # Load the stored prompt + refs
        state = _load_state(ctx, sender)
        log.info(
            "Loaded state for %s: has_prompt=%s, has_refs=%s",
            sender[:16],
            bool(state.get("prompt")),
            bool(state.get("refs")),
        )
        prompt = state.get("prompt", "")
        refs = state.get("refs", [])
        _clear_state(ctx, sender)

        if not prompt:
            await ctx.send(
                sender,
                _chat_msg(
                    "✅ Payment received, but I couldn't find your film prompt. "
                    "Please send your prompt again (no additional payment needed — "
                    "contact support if charged)."
                ),
            )
            return

        await ctx.send(
            sender,
            _chat_msg(
                "✅ **Payment confirmed!** Starting your film production now...\n"
            ),
        )

        # Queue or run immediately
        if _active is not None:
            _queue.append({"user": sender, "prompt": prompt, "refs": refs})
            pos = len(_queue)
            await ctx.send(
                sender,
                _chat_msg(
                    f"⏳ **You're #{pos} in the queue.**\n"
                    f"Another film is being produced. Yours will start automatically!"
                ),
            )
        else:
            asyncio.create_task(_run_film(ctx, sender, prompt, refs))

    except Exception as e:
        log.error("on_commit handler crashed: %s", e, exc_info=True)
        try:
            await ctx.send(sender, _chat_msg(f"❌ Error processing payment: {e}"))
        except Exception:
            pass


async def on_reject(ctx: Context, sender: str, msg: RejectPayment) -> None:
    """Called when payment is rejected or cancelled."""
    log.info("❌ RejectPayment from %s: %s", sender[:16], msg.reason)
    _clear_state(ctx, sender)
    await ctx.send(
        sender,
        _chat_msg(
            f"❌ **Payment was cancelled or rejected.** {msg.reason or ''}\n\n"
            f"Send your prompt again anytime to start a new checkout."
        ),
    )


# ── Wire up protocols ─────────────────────────────────────────────

payment_proto = build_payment_proto(on_commit, on_reject)

agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)


# ── Lifecycle ─────────────────────────────────────────────────────


@agent.on_event("startup")
async def startup(ctx: Context) -> None:
    log.info("🎬 Unified Movie Agent (Stripe-gated) starting…")
    log.info("📍 Address: %s", agent.address)
    log.info("🎞️  %d scenes | 💳 Stripe payment required", SCENE_COUNT)


if __name__ == "__main__":
    print("🎬 Unified Movie Agent (Stripe-gated)")
    print(f"📍 Address: {agent.address}")
    print(
        f"🎞️  {SCENE_COUNT} scenes | 💳 Stripe payment: ${STRIPE_AMOUNT_CENTS / 100:.2f} {STRIPE_CURRENCY.upper()}"
    )
    print()
    agent.run()
