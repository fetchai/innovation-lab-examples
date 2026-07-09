import asyncio
from uuid import uuid4

from uagents import Context
from uagents_core.contrib.protocols.payment import Funds, RequestPayment

from config import STRIPE_AMOUNT_CENTS
from stripe_payments import (
    create_embedded_checkout_session,
    format_price,
)


async def request_payment_from_user(
    ctx: Context, user_address: str, description: str | None = None
):
    """Create a Stripe embedded checkout and send RequestPayment to the user."""
    desc = description or f"RAG document ingestion — {format_price()}"

    try:
        checkout = await asyncio.to_thread(
            create_embedded_checkout_session,
            user_address=user_address,
            chat_session_id=str(uuid4()),
            description=desc,
        )

        # Persist checkout session so the commit handler can verify later
        ctx.storage.set(f"pending_stripe:{user_address}", checkout)

        payment_request = RequestPayment(
            accepted_funds=[
                Funds(
                    currency="USD",
                    amount=f"{STRIPE_AMOUNT_CENTS / 100:.2f}",
                    payment_method="stripe",
                )
            ],
            recipient=str(ctx.agent.address),
            deadline_seconds=300,
            reference=checkout["checkout_session_id"],
            description=f"Pay {format_price()} for document ingestion.",
            metadata={
                "stripe": checkout,
                "service": "rag_ingestion",
            },
        )

        await ctx.send(user_address, payment_request)
        ctx.logger.info(
            f"Stripe payment request sent to {user_address[:20]}... "
            f"({format_price()}, session={checkout['checkout_session_id'][:12]}...)"
        )
    except Exception as e:
        ctx.logger.error(f"Stripe checkout creation failed: {e}")
        raise
