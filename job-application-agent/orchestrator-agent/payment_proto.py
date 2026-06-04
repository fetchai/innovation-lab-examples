"""Seller-side payment protocol — FET-native.

Charges a fixed FET amount per Greenhouse application. The buyer (the
user's ASI:One client) renders our `RequestPayment` as an inline
"Approve / Reject" payment card; tapping Approve sends a `CommitPayment`
with the on-chain FET transaction id, which we verify against the
Fetch.ai ledger via cosmpy.

Flow:

    seller (us)  ──RequestPayment──►  buyer (ASI:One renders the card)
                                       │
                                  user taps Approve → wallet pays
                                       │
    seller       ◄──CommitPayment──   buyer (with on-chain tx id)
       │
       │  verify_fet_payment_to_agent() against testnet/mainnet
       │
       ▼
    seller ──CompletePayment──► buyer    (and triggers on_complete)
                 or
    seller ──CancelPayment──► buyer      (and triggers on_failed)

Configuration (env):

- `PAYMENT_ENABLED`        — "true" turns the gate on. Default false.
- `PAYMENT_AMOUNT_FET`     — amount per application (default "10").
- `FET_USE_TESTNET`        — "true" (default) verifies against Dorado
                             testnet; "false" against mainnet.

Reference implementation: `fet-example/payment.py`.
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable, Optional
from uuid import uuid4

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


PaymentCompleteCallback = Callable[[Context, str], Awaitable[None]]
PaymentFailedCallback = Callable[[Context, str, str], Awaitable[None]]


payment_proto = Protocol(spec=payment_protocol_spec, role="seller")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


PAYMENT_METHOD = "fet_direct"
CURRENCY = "FET"


def _env_truthy(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    return _env_truthy("PAYMENT_ENABLED", default=False)


def use_testnet() -> bool:
    return _env_truthy("FET_USE_TESTNET", default=True)


def amount_fet() -> str:
    return os.getenv("PAYMENT_AMOUNT_FET", "10")


def gate_active() -> bool:
    """True iff the orchestrator should request payment before applying.

    Unlike the Skyfire variant, FET-direct doesn't need external API
    keys — the seller wallet (the agent's own wallet) is enough."""
    return is_enabled() and _agent_wallet is not None


# ---------------------------------------------------------------------------
# Callbacks wired in by agent.py
# ---------------------------------------------------------------------------


_on_complete: Optional[PaymentCompleteCallback] = None
_on_failed: Optional[PaymentFailedCallback] = None


def set_callbacks(
    *,
    on_complete: PaymentCompleteCallback,
    on_failed: Optional[PaymentFailedCallback] = None,
) -> None:
    """`on_complete(ctx, user_address)` runs after a successful FET
    verify + CompletePayment ack. `on_failed(ctx, user_address, reason)`
    runs after verification fails or the buyer rejects."""
    global _on_complete, _on_failed
    _on_complete = on_complete
    _on_failed = on_failed


_agent_wallet = None


def set_agent_wallet(wallet) -> None:  # noqa: ANN001
    global _agent_wallet
    _agent_wallet = wallet


# ---------------------------------------------------------------------------
# FET on-chain verification
# ---------------------------------------------------------------------------


def verify_fet_payment_to_agent(
    *,
    transaction_id: str,
    expected_amount_fet: str,
    sender_fet_address: str,
    logger,  # noqa: ANN001
) -> bool:
    """Verify that `transaction_id` on the Fetch.ai chain transferred at
    least `expected_amount_fet` from `sender_fet_address` to the agent
    wallet. Returns True on success."""
    if _agent_wallet is None:
        logger.error("verify_fet_payment_to_agent: agent wallet not set")
        return False
    try:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig
    except ImportError as exc:
        logger.error(f"cosmpy not installed: {exc}")
        return False

    testnet = use_testnet()
    network_config = (
        NetworkConfig.fetchai_stable_testnet()
        if testnet
        else NetworkConfig.fetchai_mainnet()
    )
    ledger = LedgerClient(network_config)

    try:
        expected_amount_micro = int(float(expected_amount_fet) * 10**18)
    except (TypeError, ValueError):
        logger.error(f"invalid expected_amount_fet: {expected_amount_fet!r}")
        return False

    expected_recipient = str(_agent_wallet.address())
    denom = "atestfet" if testnet else "afet"

    logger.info(
        f"Verifying {expected_amount_fet} FET from {sender_fet_address} "
        f"→ {expected_recipient} on {'testnet' if testnet else 'mainnet'} "
        f"(tx={transaction_id})"
    )

    try:
        tx_response = ledger.query_tx(transaction_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ledger.query_tx({transaction_id}) failed: {exc}")
        return False

    if not tx_response.is_successful():
        logger.error(f"tx {transaction_id} did not succeed on-chain")
        return False

    # Walk transfer events; require recipient + sender + amount all match.
    recipient_ok = False
    sender_ok = False
    amount_ok = False
    for event_type, attrs in tx_response.events.items():
        if event_type != "transfer":
            continue
        if attrs.get("recipient") != expected_recipient:
            continue
        recipient_ok = True
        if attrs.get("sender") == sender_fet_address:
            sender_ok = True
        amount_str = attrs.get("amount", "") or ""
        if amount_str.endswith(denom):
            try:
                value = int(amount_str.replace(denom, ""))
                if value >= expected_amount_micro:
                    amount_ok = True
            except ValueError:
                pass

    if recipient_ok and sender_ok and amount_ok:
        logger.info(f"FET payment verified: {transaction_id}")
        return True

    logger.error(
        f"FET verify failed (recipient_ok={recipient_ok} "
        f"sender_ok={sender_ok} amount_ok={amount_ok})"
    )
    return False


# ---------------------------------------------------------------------------
# Seller actions
# ---------------------------------------------------------------------------


async def request_payment_from_user(
    ctx: Context,
    user_address: str,
    *,
    description: Optional[str] = None,
    reference: Optional[str] = None,
    deadline_seconds: int = 300,
) -> None:
    """Send a `RequestPayment` for one application. ASI:One renders this
    as an inline payment card with **Approve** / **Reject** buttons."""
    funds = Funds(
        currency=CURRENCY,
        amount=amount_fet(),
        payment_method=PAYMENT_METHOD,
    )

    metadata: dict[str, str] = {
        "agent": "job_application_orchestrator",
        "service": "job_application",
        "fet_network": "stable-testnet" if use_testnet() else "mainnet",
        "mainnet": "false" if use_testnet() else "true",
    }
    if _agent_wallet:
        metadata["provider_agent_wallet"] = str(_agent_wallet.address())
    metadata["content"] = (
        description
        or "Authorise one Greenhouse job application. The orchestrator "
           "will hand the URL to its form-filler co-agent and submit on "
           "your behalf."
    )

    recipient_addr = (
        str(_agent_wallet.address())
        if _agent_wallet
        else str(ctx.agent.address)
    )

    req = RequestPayment(
        accepted_funds=[funds],
        recipient=recipient_addr,
        deadline_seconds=deadline_seconds,
        reference=reference or str(uuid4()),
        description=(
            description
            or f"Pay {amount_fet()} FET to run one automated job "
               f"application."
        ),
        metadata=metadata,
    )
    ctx.logger.info(
        f"[payment] RequestPayment → {user_address} "
        f"({funds.amount} {funds.currency} via {funds.payment_method}, "
        f"recipient={recipient_addr})"
    )
    await ctx.send(user_address, req)


# ---------------------------------------------------------------------------
# Protocol handlers (seller role)
# ---------------------------------------------------------------------------


@payment_proto.on_message(CommitPayment)
async def handle_commit_payment(
    ctx: Context, sender: str, msg: CommitPayment
) -> None:
    ctx.logger.info(
        f"[payment] CommitPayment from {sender} "
        f"(method={msg.funds.payment_method} currency={msg.funds.currency} "
        f"amount={msg.funds.amount} tx={msg.transaction_id})"
    )

    if not (
        msg.funds.payment_method == PAYMENT_METHOD
        and msg.funds.currency == CURRENCY
    ):
        ctx.logger.error(
            f"unsupported funds: {msg.funds.payment_method}/{msg.funds.currency}"
        )
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason=(
                    f"Only {CURRENCY} via {PAYMENT_METHOD} is accepted."
                ),
            ),
        )
        if _on_failed is not None:
            await _on_failed(ctx, sender, "unsupported_method")
        return

    buyer_fet_wallet = None
    if isinstance(msg.metadata, dict):
        buyer_fet_wallet = (
            msg.metadata.get("buyer_fet_wallet")
            or msg.metadata.get("buyer_fet_address")
        )
    if not buyer_fet_wallet:
        ctx.logger.error("CommitPayment missing buyer_fet_wallet metadata")
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason="Missing buyer FET wallet address in payment metadata.",
            ),
        )
        if _on_failed is not None:
            await _on_failed(ctx, sender, "missing_buyer_wallet")
        return

    try:
        verified = verify_fet_payment_to_agent(
            transaction_id=msg.transaction_id,
            expected_amount_fet=str(msg.funds.amount),
            sender_fet_address=buyer_fet_wallet,
            logger=ctx.logger,
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"verify_fet_payment_to_agent raised: {exc}")
        verified = False

    if verified:
        await ctx.send(
            sender, CompletePayment(transaction_id=msg.transaction_id)
        )
        if _on_complete is not None:
            try:
                await _on_complete(ctx, sender)
            except Exception as exc:  # noqa: BLE001
                ctx.logger.error(f"on_complete callback raised: {exc}")
        else:
            ctx.logger.warning(
                "Payment verified but no on_complete callback wired"
            )
        return

    # Verification failed — tell the buyer and clean up.
    await ctx.send(
        sender,
        CancelPayment(
            transaction_id=msg.transaction_id,
            reason="Payment verification failed.",
        ),
    )
    if _on_failed is not None:
        try:
            await _on_failed(ctx, sender, "verification_failed")
        except Exception as exc:  # noqa: BLE001
            ctx.logger.error(f"on_failed callback raised: {exc}")


@payment_proto.on_message(RejectPayment)
async def handle_reject_payment(
    ctx: Context, sender: str, msg: RejectPayment
) -> None:
    """Buyer tapped **Reject** on the inline card."""
    ctx.logger.info(f"[payment] RejectPayment from {sender}: {msg.reason}")
    if _on_failed is not None:
        try:
            await _on_failed(ctx, sender, f"buyer_rejected:{msg.reason or ''}")
        except Exception as exc:  # noqa: BLE001
            ctx.logger.error(f"on_failed callback raised: {exc}")
