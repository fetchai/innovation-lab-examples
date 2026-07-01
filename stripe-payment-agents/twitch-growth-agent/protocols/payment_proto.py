"""Payment protocol: Stripe verification and order fulfilment.

The payment_proto Protocol object is included into the Agent in agent.py.
"""

from __future__ import annotations

import asyncio
import logging

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    RejectPayment,
    payment_protocol_spec,
)

from protocols.chat_proto import (
    _deliver_job,
    _send,
    resolve_user_key,
    verify_checkout_session_paid,
)

logger = logging.getLogger(__name__)


def build_payment_proto() -> Protocol:
    """Seller side of the Agent Payment Protocol with Stripe verification."""
    proto = Protocol(spec=payment_protocol_spec, role="seller")

    @proto.on_message(CommitPayment)
    async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
        """Verify the Stripe payment, then complete and deliver the report.
        A CommitPayment is only ever answered with CompletePayment or CancelPayment.
        """
        ctx.logger.info(f"on_commit from sender: {sender}")
        session_id = msg.transaction_id
        order = ctx.storage.get(f"order:{session_id}")
        if isinstance(order, str):  # legacy order shape: a bare growth_report channel
            order = {
                "intent": "growth_report",
                "params": {"channel_name": order},
                "user_id": resolve_user_key(sender),
            }
        ctx.logger.info(f"CommitPayment for session {session_id} (order={order})")

        if not order:
            await _send(
                ctx,
                sender,
                CancelPayment(transaction_id=session_id, reason="unknown order"),
            )
            return

        if ctx.storage.get(f"fulfilled:{session_id}"):
            await _send(
                ctx,
                sender,
                CancelPayment(
                    transaction_id=session_id, reason="order already fulfilled"
                ),
            )
            return

        try:
            paid = await asyncio.to_thread(verify_checkout_session_paid, session_id)
        except Exception as exc:  # noqa: BLE001 - any Stripe error => unverified
            ctx.logger.error(f"Stripe verification error: {exc}")
            await _send(
                ctx,
                sender,
                CancelPayment(
                    transaction_id=session_id, reason=f"verification failed: {exc}"
                ),
            )
            return

        if not paid:
            ctx.logger.info(f"Session {session_id} not paid; cancelling.")
            await _send(
                ctx,
                sender,
                CancelPayment(
                    transaction_id=session_id, reason="payment not completed"
                ),
            )
            return

        ctx.storage.set(f"fulfilled:{session_id}", True)
        await _send(ctx, sender, CompletePayment(transaction_id=session_id))

        unlock_user = order.get("user_id") or resolve_user_key(sender)
        ctx.storage.set(f"unlocked:{unlock_user}", True)
        ctx.logger.info(f"User {unlock_user} unlocked.")

        ctx.storage.remove(f"order:{session_id}")
        await _deliver_job(ctx, sender, order)

    @proto.on_message(RejectPayment)
    async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
        """Buyer declined the payment request."""
        ctx.logger.info(f"on_reject from sender: {sender}")
        ctx.logger.info(f"Payment rejected by {sender}: {msg.reason}")

    return proto


payment_proto = build_payment_proto()
