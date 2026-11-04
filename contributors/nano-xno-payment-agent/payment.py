"""
uAgents payment-protocol seller example with a Nano (XNO) settlement rail.

Shows how an Agentverse seller can request and verify a payment on the Nano
layer-1 — fee-less, single-block final — using the standard uAgents payment
protocol models (Funds/RequestPayment/CommitPayment/CompletePayment). This is
the same shape as the repo's `fet-example` (fet_direct) and
`image-agent-payment-protocol` (skyfire), with payment_method="nano_xno".

Nano specifics this example highlights:
  * Funds(currency="XNO", payment_method="nano_xno") — a new rail next to
    "fetch_direct" and "skyfire" on the same protocol models.
  * The seller publishes its Nano receiving account in
    RequestPayment.metadata["provider_nano_account"].
  * The buyer pays by sending XNO to that account and reports the send block
    hash as transaction_id on CommitPayment.
  * The seller verifies the confirmed receive via the public Nano RPC
    (verify_nano.py) — no escrow, no gas, no settlement window, no reversal.
"""

import asyncio
import os

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from shared import create_text_chat
from nano_binding import (
    claim_block,
    commitment_rep_account,
    finalize,
    new_order,
    release_block,
)
from verify_nano import (
    _xno_to_raw,
    declared_matches_accepted,
    verify_nano_send,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Amount requested per job, in XNO. Fee is always zero at the protocol level.
DEFAULT_XNO_AMOUNT = os.getenv("NANO_AMOUNT", "0.0001").strip()

# Fail at startup, not inside the chat handler: a non-numeric or non-positive
# NANO_AMOUNT would otherwise only surface when the first payment is requested.
_amount_raw = _xno_to_raw(DEFAULT_XNO_AMOUNT)
if _amount_raw is None or _amount_raw <= 0:
    raise ValueError(
        f"NANO_AMOUNT must be a positive XNO amount such as 0.0001, got {DEFAULT_XNO_AMOUNT!r}"
    )

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

# Nano receiving account: the agent's own Nano account (NANO_ACCOUNT in .env).
NANO_ACCOUNT = os.getenv("NANO_ACCOUNT", "")

XNO_FUNDS = Funds(currency="XNO", amount=DEFAULT_XNO_AMOUNT, payment_method="nano_xno")
ACCEPTED_FUNDS = [XNO_FUNDS]

ORDER_TTL_S = 300  # validity window of an issued order


@payment_proto.on_message(CommitPayment)
async def handle_commit_payment(ctx: Context, sender: str, msg: CommitPayment):
    """Buyer says it paid. Verify the Nano receive on-chain before completing."""
    ctx.logger.info(f"[nano] CommitPayment received from {sender}: {msg.funds}")

    if not (msg.funds.payment_method == "nano_xno" and msg.funds.currency == "XNO"):
        ctx.logger.error(
            f"[nano] Unsupported payment method: {msg.funds.payment_method} "
            f"/ {msg.funds.currency}"
        )
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason="Unsupported payment method",
            ),
        )
        return

    if not NANO_ACCOUNT:
        ctx.logger.error("[nano] NANO_ACCOUNT is not set; cannot verify on-chain")
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason="Seller Nano account not configured",
            ),
        )
        return

    # Runtime amount guard (AI-review blocking finding 2026-09-25): the buyer
    # controls msg.funds, so we MUST NOT verify against the amount they declare
    # — they could claim a microscopic amount and be priced at their own word.
    # The on-chain check must enforce what the SELLER accepted and requested
    # (ACCEPTED_FUNDS[0].amount). Reject any commit whose declared funds do not
    # exactly match the accepted amount, logging the divergence for audit,
    # before any RPC or work is spent.
    accepted_amount = ACCEPTED_FUNDS[0].amount
    if not declared_matches_accepted(msg.funds.amount, accepted_amount):
        ctx.logger.error(
            f"[nano] Amount mismatch: buyer declared {msg.funds.amount} XNO but "
            f"this seller accepted {accepted_amount} XNO; rejecting"
        )
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason=(
                    f"Declared amount {msg.funds.amount} XNO does not match the "
                    f"accepted amount {accepted_amount} XNO"
                ),
            ),
        )
        return

    # The buyer names its Nano send block hash as transaction_id.
    tx_id = msg.transaction_id
    ctx.logger.info(f"[nano] Verifying send {tx_id} of {accepted_amount} XNO")

    # Order binding + replay protection (docs/BINDING-STANDARD.md): the commit must
    # name an order THIS seller issued to THIS requester (msg.reference), inside its
    # validity window. The block hash is claimed one-to-one with that order in
    # ctx.storage (persistent) BEFORE the awaited RPC, and released if verification
    # fails, so a duplicate commit cannot be credited twice.
    order, reason = claim_block(ctx.storage, msg.reference or "", sender, tx_id)
    if order is None:
        ctx.logger.warning(f"[nano] Commit refused for {tx_id}: {reason}")
        await ctx.send(
            sender, CancelPayment(transaction_id=tx_id, reason=f"Refused: {reason}")
        )
        return
    order_id = msg.reference
    rep_account = commitment_rep_account(
        order_id, order["pay_to"], int(order["price_raw"])
    )

    # Run the blocking RPC verify off the event loop so the agent keeps serving
    # other messages while the public Nano node answers. Verify against the
    # SELLER's accepted amount (accepted_amount), never the buyer's declared
    # msg.funds.amount — a buyer-controlled amount is the bypass the guard above
    # closes, and this call must not reintroduce it.
    ok = await asyncio.to_thread(
        verify_nano_send,
        tx_id,
        NANO_ACCOUNT,
        str(accepted_amount),
        expected_representative=rep_account,
        valid_until=order["expires_at"],
        logger=ctx.logger,
    )
    if ok:
        finalize(ctx.storage, order_id)
        ctx.logger.info(f"[nano] Payment confirmed: {tx_id}")
        await ctx.send(sender, CompletePayment(transaction_id=tx_id))
        # Continue the seller's own post-payment handler here, e.g. release the
        # purchased service / data.
        await ctx.send(
            sender,
            create_text_chat(
                f"Payment verified (XNO send block {tx_id}). Your job is being processed."
            ),
        )
    else:
        # Verification failed — release the reservation so a corrected or
        # different commit for this tx is not permanently stuck as "paid".
        release_block(ctx.storage, order_id, tx_id)
        ctx.logger.error(f"[nano] Payment NOT verified for tx {tx_id}")
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=tx_id,
                reason="Nano payment could not be verified on-chain",
            ),
        )


@payment_proto.on_message(RejectPayment)
async def handle_reject_payment(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"[nano] Payment rejected by {sender}: {msg.reason}")
    await ctx.send(
        sender,
        create_text_chat("Payment request was declined. Reply to try again."),
    )


async def request_payment_from_user(ctx: Context, user_address: str, description: str):
    """Send a RequestPayment asking the buyer to settle in XNO."""
    metadata: dict[str, str] = {
        "agent": "nano-xno-payment-agent",
        "service": "nano_settled_job",
        "rail": "nano",
    }
    if NANO_ACCOUNT:
        metadata["provider_nano_account"] = NANO_ACCOUNT

    # One opaque order per request. The buyer must sign the send block with
    # representative = metadata["provider_nano_representative"] and echo the order id
    # as CommitPayment.reference.
    order_id, rep, _ = new_order(
        ctx.storage,
        user_address,
        NANO_ACCOUNT,
        _xno_to_raw(ACCEPTED_FUNDS[0].amount),
        ORDER_TTL_S,
    )
    metadata["provider_nano_representative"] = rep

    payment_request = RequestPayment(
        accepted_funds=ACCEPTED_FUNDS,
        recipient=str(ctx.agent.address),
        deadline_seconds=ORDER_TTL_S,
        reference=order_id,
        description=description,
        metadata=metadata,
    )
    await ctx.send(user_address, payment_request)
    ctx.logger.info(
        f"[nano] RequestPayment sent to {user_address}: "
        f"{ACCEPTED_FUNDS[0].amount} XNO via nano_xno"
    )
