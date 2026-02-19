import asyncio
import time

from uagents import Context
from uagents_core.contrib.protocols.chat import ChatMessage
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
)

from config import STRIPE_AMOUNT_CENTS
from llm import generate_horoscope, normal_reply
from state import (
    clear_state,
    extract_sign,
    extract_text,
    load_state,
    make_chat,
    save_state,
    wants_horoscope,
)
from stripe_payments import create_embedded_checkout_session, verify_checkout_session_paid


def _looks_like_new_chat(text_l: str) -> bool:
    # The chat UI often reuses the same sender address across multiple "new chat" threads.
    # When the user is clearly starting over, we should drop any old pending-payment state.
    starters = (
        "what can you do",
        "what can you",
        "who are you",
        "hello",
        "hi",
        "hey",
        "how can you help",
        "help",
    )
    return any(s in text_l for s in starters)


async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    text = extract_text(msg)
    text_l = text.lower()

    state = load_state(ctx, sender)

    sign = str(state.get("sign") or "").lower().strip() or ""
    awaiting_sign = bool(state.get("awaiting_sign"))
    was_awaiting_sign = awaiting_sign
    awaiting_payment = bool(state.get("awaiting_payment"))
    pending_stripe = state.get("pending_stripe") if isinstance(state.get("pending_stripe"), dict) else None

    ctx.logger.info(f"[chat] inbound sender={sender} session={ctx.session} text={text!r} state={state}")

    wants = wants_horoscope(text_l)

    # If payment is already pending, keep the interaction simple: re-send the same RequestPayment.
    if awaiting_payment and pending_stripe:
        if (not wants) and _looks_like_new_chat(text_l):
            clear_state(ctx, sender)
            state = {}
            sign = ""
            awaiting_sign = False
            was_awaiting_sign = False
            awaiting_payment = False
            pending_stripe = None
        if not wants:
            reply = await normal_reply(text)
            await ctx.send(
                sender,
                make_chat(
                    (reply or "Say 'give me my horoscope' to begin.")
                    + "\n\nPayment is still pending. Please complete the Stripe checkout above."
                ),
            )
            return
        req = RequestPayment(
            accepted_funds=[Funds(currency="USD", amount=f"{STRIPE_AMOUNT_CENTS / 100:.2f}", payment_method="stripe")],
            recipient=str(ctx.agent.address),
            deadline_seconds=300,
            reference=str(ctx.session),
            description="Pay $1 to receive your horoscope of the day.",
            metadata={"stripe": pending_stripe, "service": "daily_horoscope"},
        )
        await ctx.send(sender, req)
        await ctx.send(sender, make_chat("Payment is still pending. Please complete the Stripe checkout above."))
        return

    # If we're waiting for the user to provide a sign, treat the next message as the sign input.
    if awaiting_sign:
        sign_guess = extract_sign(text_l)
        if not sign_guess:
            await ctx.send(
                sender,
                make_chat(
                    "What’s your star sign? (e.g. Aries, Taurus, Gemini, Cancer, Leo, Virgo, Libra, Scorpio, Sagittarius, Capricorn, Aquarius, Pisces)"
                ),
            )
            return
        sign = sign_guess
        state["sign"] = sign
        state["awaiting_sign"] = False
        save_state(ctx, sender, state)
        wants = wants or was_awaiting_sign

    # Decide whether to reply normally or run the horoscope flow.
    if not wants:
        reply = await normal_reply(text)
        await ctx.send(sender, make_chat(reply or "Say 'give me my horoscope' to begin."))
        return

    # Horoscope flow: require a sign.
    if not sign:
        state["awaiting_sign"] = True
        state["expires_at"] = time.time() + 30 * 60
        save_state(ctx, sender, state)
        await ctx.send(
            sender,
            make_chat(
                "Sure — what’s your star sign? (e.g. Aries, Taurus, Gemini, Cancer, Leo, Virgo, Libra, Scorpio, Sagittarius, Capricorn, Aquarius, Pisces)"
            ),
        )
        return

    description = f"Daily horoscope for {sign.title()}"
    checkout = await asyncio.to_thread(
        create_embedded_checkout_session,
        user_address=sender,
        chat_session_id=str(ctx.session),
        description=description,
    )

    state["awaiting_payment"] = True
    state["pending_stripe"] = checkout
    state["sign"] = sign
    state["expires_at"] = time.time() + 30 * 60
    save_state(ctx, sender, state)

    req = RequestPayment(
        accepted_funds=[Funds(currency="USD", amount=f"{STRIPE_AMOUNT_CENTS / 100:.2f}", payment_method="stripe")],
        recipient=str(ctx.agent.address),
        deadline_seconds=300,
        reference=str(ctx.session),
        description="Pay $1 to receive your horoscope of the day.",
        metadata={"stripe": checkout, "service": "daily_horoscope"},
    )
    await ctx.send(sender, req)
    await ctx.send(sender, make_chat("Once payment completes, I’ll reply here with your horoscope."))


async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
    if msg.funds.payment_method != "stripe" or not msg.transaction_id:
        await ctx.send(sender, RejectPayment(reason="Unsupported payment method (expected stripe)."))
        return

    paid = await asyncio.to_thread(verify_checkout_session_paid, msg.transaction_id)
    if not paid:
        await ctx.send(sender, RejectPayment(reason="Stripe payment not completed yet. Please finish checkout."))
        return

    state = load_state(ctx, sender)
    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))

    sign = str(state.get("sign") or "").strip() or "unknown"
    horoscope = await generate_horoscope(sign)
    await ctx.send(sender, make_chat(horoscope or "Payment received, but I couldn’t generate your horoscope right now."))
    clear_state(ctx, sender)


async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
    clear_state(ctx, sender)
    await ctx.send(sender, make_chat(f"Payment was rejected. {msg.reason or ''}".strip()))

