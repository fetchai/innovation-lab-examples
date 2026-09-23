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
from verify_nano import verify_nano_send

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Amount requested per job, in XNO. Fee is always zero at the protocol level.
DEFAULT_XNO_AMOUNT = os.getenv("NANO_AMOUNT", "0.0001")

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

# Nano receiving account. In a real deployment set this to the agent's own Nano
# account (NANO_ACCOUNT in .env). For a local no-wallet demo you can use the
# reward / faucet-style address below, which only demonstrates the verify path.
NANO_ACCOUNT = os.getenv("NANO_ACCOUNT", "")

XNO_FUNDS = Funds(currency="XNO", amount=DEFAULT_XNO_AMOUNT, payment_method="nano_xno")
ACCEPTED_FUNDS = [XNO_FUNDS]

# Replay protection: remember send-block hashes already honoured, so the same
# payment cannot be used to claim service twice. Persist in ctx.storage so it
# survives restarts.
PAID_PREFIX = "nano_paid:"


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

    # The buyer names its Nano send block hash as transaction_id.
    tx_id = msg.transaction_id
    ctx.logger.info(f"[nano] Verifying send {tx_id} of {msg.funds.amount} XNO")

    # Replay protection: reject a send hash already honoured.
    paid_key = PAID_PREFIX + tx_id
    if ctx.storage.has(paid_key) or ctx.storage.get(paid_key):
        ctx.logger.warning(f"[nano] Send {tx_id} already honoured; rejecting replay")
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=tx_id,
                reason="Payment already used",
            ),
        )
        return

    # Run the blocking RPC verify off the event loop so the agent keeps serving
    # other messages while the public Nano node answers.
    ok = await asyncio.to_thread(
        verify_nano_send,
        tx_id,
        NANO_ACCOUNT,
        str(msg.funds.amount),
        logger=ctx.logger,
    )
    if ok:
        ctx.storage.set(paid_key, True)
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

    payment_request = RequestPayment(
        accepted_funds=ACCEPTED_FUNDS,
        recipient=str(ctx.agent.address),
        deadline_seconds=300,
        reference=str(ctx.session),
        description=description,
        metadata=metadata,
    )
    await ctx.send(user_address, payment_request)
    ctx.logger.info(
        f"[nano] RequestPayment sent to {user_address}: "
        f"{ACCEPTED_FUNDS[0].amount} XNO via nano_xno"
    )
