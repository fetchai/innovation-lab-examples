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
- `PAYMENT_AMOUNT_FET`     — amount per application (default "0.1").
- `FET_USE_TESTNET`        — "true" (default) verifies against Dorado
                             testnet; "false" against mainnet.
- `PAYMENT_RECIPIENT_FET`  — wallet that receives the FET payment.
- `PAYMENT_BUYER_FET`      — optional wallet expected to send the payment.
- `PAYMENT_TESTNET_AUTO_PAY` — "true" lets the fallback card submit a
                               real testnet transfer using a configured
                               mnemonic. Ignored on mainnet.
- `PAYMENT_TESTNET_PAYER_MNEMONIC` — testnet payer wallet mnemonic.
- `PAYMENT_TESTNET_PAYER_PRIVATE_KEY` — testnet payer private key as hex.

Reference implementation: `fet-example/payment.py`.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Awaitable, Callable, Optional
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.models import Model
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
    return os.getenv("PAYMENT_AMOUNT_FET", "0.1")


def recipient_fet_address(ctx: Optional[Context] = None) -> str:
    configured = os.getenv("PAYMENT_RECIPIENT_FET", "").strip()
    if configured:
        return configured
    if _agent_wallet:
        return str(_agent_wallet.address())
    return str(ctx.agent.address) if ctx is not None else ""


def expected_buyer_fet_address() -> str:
    return os.getenv("PAYMENT_BUYER_FET", "").strip()


def testnet_auto_pay_enabled() -> bool:
    return use_testnet() and _env_truthy("PAYMENT_TESTNET_AUTO_PAY", default=False)


def balance_fet(address: str, logger=None) -> Optional[str]:  # noqa: ANN001
    """Return wallet balance in FET as a compact decimal string."""
    if not address:
        return None
    try:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig
        from cosmpy.crypto.address import Address

        network_config = (
            NetworkConfig.fetchai_stable_testnet()
            if use_testnet()
            else NetworkConfig.fetchai_mainnet()
        )
        ledger = LedgerClient(network_config)
        denom = "atestfet" if use_testnet() else "afet"
        raw_amount = ledger.query_bank_balance(Address(address), denom)
    except Exception as exc:  # noqa: BLE001
        if logger is not None:
            logger.warning(f"balance query failed for {address}: {exc}")
        return None

    fet_value = Decimal(raw_amount) / Decimal(10**18)
    text = f"{fet_value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def execute_testnet_payment(logger) -> tuple[bool, str, Optional[str]]:  # noqa: ANN001
    """Submit a real testnet FET transfer using a configured payer key.

    Returns (success, reason_or_tx_hash, payer_address). This is deliberately
    testnet-only; mainnet must go through a real wallet approval/CommitPayment.
    """
    if not use_testnet():
        return False, "auto_pay_mainnet_disabled", None
    if not testnet_auto_pay_enabled():
        return False, "auto_pay_disabled", None

    mnemonic = os.getenv("PAYMENT_TESTNET_PAYER_MNEMONIC", "").strip()
    private_key_hex = os.getenv("PAYMENT_TESTNET_PAYER_PRIVATE_KEY", "").strip()
    if not mnemonic and not private_key_hex:
        return False, "missing_payment_testnet_payer_key", None

    try:
        from cosmpy.aerial.client import LedgerClient, NetworkConfig
        from cosmpy.aerial.wallet import LocalWallet, PrivateKey
        from cosmpy.crypto.address import Address

        if mnemonic:
            payer_wallet = LocalWallet.from_mnemonic(mnemonic, prefix="fetch")
        else:
            private_key_hex = private_key_hex.removeprefix("0x")
            payer_wallet = LocalWallet(
                PrivateKey(bytes.fromhex(private_key_hex)),
                prefix="fetch",
            )
        payer_address = str(payer_wallet.address())
        expected_payer = expected_buyer_fet_address()
        if expected_payer and payer_address != expected_payer:
            logger.error(
                f"testnet payer mnemonic mismatch: {payer_address} "
                f"!= {expected_payer}"
            )
            return False, "payer_mnemonic_address_mismatch", payer_address

        recipient_address = recipient_fet_address()
        if not recipient_address:
            return False, "missing_recipient", payer_address

        amount_atestfet = int(Decimal(amount_fet()) * Decimal(10**18))
        ledger = LedgerClient(NetworkConfig.fetchai_stable_testnet())
        submitted = ledger.send_tokens(
            Address(recipient_address),
            amount_atestfet,
            "atestfet",
            payer_wallet,
            memo="job_application_orchestrator",
        )
        logger.info(
            f"[payment] submitted testnet transfer tx={submitted.tx_hash} "
            f"from={payer_address} to={recipient_address} "
            f"amount={amount_fet()} FET"
        )
        submitted.wait_to_complete(timeout=30, poll_period=1)

        verified = verify_fet_payment(
            transaction_id=submitted.tx_hash,
            expected_amount_fet=amount_fet(),
            sender_fet_address=payer_address,
            recipient_fet_address=recipient_address,
            logger=logger,
        )
        if not verified:
            return False, "verification_failed", payer_address
        return True, submitted.tx_hash, payer_address
    except Exception as exc:  # noqa: BLE001
        logger.error(f"testnet auto payment failed: {exc}")
        return False, f"auto_pay_error:{exc}", None


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


def verify_fet_payment(
    *,
    transaction_id: str,
    expected_amount_fet: str,
    sender_fet_address: str,
    recipient_fet_address: str,
    logger,  # noqa: ANN001
) -> bool:
    """Verify that `transaction_id` on the Fetch.ai chain transferred at
    least `expected_amount_fet` from `sender_fet_address` to the expected
    wallet. Returns True on success."""
    if not recipient_fet_address:
        logger.error("verify_fet_payment: recipient wallet not configured")
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

    expected_recipient = recipient_fet_address
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
    expected_buyer = expected_buyer_fet_address()
    if expected_buyer:
        metadata["buyer_fet_wallet"] = expected_buyer
        metadata["expected_buyer_fet_wallet"] = expected_buyer
    metadata["content"] = (
        description
        or "Please complete the FET payment to start the Greenhouse application."
    )

    recipient_addr = recipient_fet_address(ctx)

    # Bare session UUID, same as duffel (`reference=session`).
    session_ref = reference or (str(ctx.session) if ctx.session else str(uuid4()))

    req = RequestPayment(
        accepted_funds=[funds],
        recipient=recipient_addr,
        deadline_seconds=deadline_seconds,
        reference=session_ref,
        description=description or "Greenhouse job application — pay to proceed",
        metadata=metadata,
    )
    ctx.logger.info(
        f"[payment] RequestPayment → {user_address} "
        f"({funds.amount} {funds.currency} via {funds.payment_method}, "
        f"recipient={recipient_addr})"
    )
    try:
        ctx.logger.info(f"[payment] payload: {req.model_dump_json()}")
    except Exception:  # noqa: BLE001
        ctx.logger.info(f"[payment] payload (repr): {req!r}")
    status = await ctx.send_raw(
        destination=user_address,
        message_schema_digest=Model.build_schema_digest(req),
        message_body=req.model_dump_json(),
        protocol_digest=payment_proto.digest,
    )
    ctx.logger.info(
        f"[payment] send_raw status={status.status} "
        f"protocol_digest={payment_proto.digest}"
    )


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

    expected_recipient = recipient_fet_address(ctx)
    if msg.recipient != expected_recipient:
        ctx.logger.error(
            f"CommitPayment recipient mismatch: {msg.recipient} "
            f"!= {expected_recipient}"
        )
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason="Payment recipient did not match the requested wallet.",
            ),
        )
        if _on_failed is not None:
            await _on_failed(ctx, sender, "wrong_recipient")
        return

    if str(msg.funds.amount) != amount_fet():
        ctx.logger.error(
            f"CommitPayment amount mismatch: {msg.funds.amount} "
            f"!= {amount_fet()}"
        )
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=msg.transaction_id,
                reason="Payment amount did not match the requested amount.",
            ),
        )
        if _on_failed is not None:
            await _on_failed(ctx, sender, "wrong_amount")
        return

    buyer_fet_wallet = None
    if isinstance(msg.metadata, dict):
        buyer_fet_wallet = (
            msg.metadata.get("buyer_fet_wallet")
            or msg.metadata.get("buyer_fet_address")
            or msg.metadata.get("expected_buyer_fet_wallet")
        )
    configured_buyer = expected_buyer_fet_address()
    if configured_buyer:
        if buyer_fet_wallet and buyer_fet_wallet != configured_buyer:
            ctx.logger.error(
                f"CommitPayment buyer wallet mismatch: "
                f"{buyer_fet_wallet} != {configured_buyer}"
            )
            await ctx.send(
                sender,
                CancelPayment(
                    transaction_id=msg.transaction_id,
                    reason="Payment was not sent from the expected FET wallet.",
                ),
            )
            if _on_failed is not None:
                await _on_failed(ctx, sender, "wrong_buyer_wallet")
            return
        buyer_fet_wallet = configured_buyer
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
        verified = verify_fet_payment(
            transaction_id=msg.transaction_id,
            expected_amount_fet=amount_fet(),
            sender_fet_address=buyer_fet_wallet,
            recipient_fet_address=expected_recipient,
            logger=ctx.logger,
        )
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"verify_fet_payment raised: {exc}")
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
