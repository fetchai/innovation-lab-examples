"""
Nano (XNO) on-chain payment verification for the uAgents payment protocol.

Nano is a feeless, single-block-final layer-1: each transfer publishes one block
that is confirmed within ~0.2s of deterministic ORV finality (no reorgs, no
chargebacks, no settlement window, no gas). This module verifies that a buyer's
Nano payment actually reached the seller's account using the public network RPC
— keyless, read-only.

Verification model used here: the seller publishes its Nano receiving account in
RequestPayment.metadata["provider_nano_account"]. The buyer pays by sending XNO
to that account and reports its **send block hash** as transaction_id on
CommitPayment. The seller then queries block_info for that send block and checks
that it is a confirmed send to the seller's account for at least the requested
amount. This matches the buyer's reported transaction directly, so one payment
cannot be reused to verify many commits.
"""

from __future__ import annotations

import json
import os
import urllib.request
from decimal import Decimal
from typing import Any

# Public Nano RPC (rpc.nano.to). No key required for read actions.
# Override with the NANO_RPC_URL env var to point at a private/shared node.
NANO_RPC_URL = os.getenv("NANO_RPC_URL", "https://rpc.nano.to")

# There are 10^30 raw units (raw) per 1 XNO.
RAW_PER_XNO = 10**30


def _xno_to_raw(xno: str | float) -> int | None:
    """Convert a human XNO amount (decimal string/number) to raw units.

    Uses Decimal so a value like \"0.0001\" maps exactly to 10^26 raw — never a
    float rounding error that could make a valid payment appear short.
    """
    try:
        return int(Decimal(str(xno)) * Decimal(RAW_PER_XNO))
    except (ArithmeticError, ValueError, TypeError):
        return None


def nano_rpc_post(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """POST a Nano RPC action to the public node and return parsed JSON."""
    payload = json.dumps({"action": action, **params}).encode("utf-8")
    req = urllib.request.Request(
        NANO_RPC_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "uagents-nano-payment-example/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (https only)
        return json.loads(resp.read().decode("utf-8"))


def verify_nano_send(
    send_hash: str,
    expected_recipient: str,
    expected_amount_xno: str | float,
    *,
    logger: Any = None,
) -> bool:
    """Verify a Nano send block reached a recipient for at least a given amount.

    Queries block_info for `send_hash` (the buyer's reported transaction_id) and
    returns True only if it is a confirmed send to `expected_recipient` for at
    least `expected_amount_xno` XNO. This binds the buyer's reported transaction
    to the actual on-chain transfer, so one payment cannot verify many commits.
    """
    if not send_hash:
        if logger:
            logger.error("No Nano send block hash to verify")
        return False
    if not expected_recipient:
        if logger:
            logger.error("No Nano receiving account configured")
        return False
    expected_raw = _xno_to_raw(expected_amount_xno)
    if expected_raw is None:
        if logger:
            logger.error(f"Invalid expected amount: {expected_amount_xno}")
        return False

    try:
        data = nano_rpc_post("block_info", {"hash": send_hash, "json_block": "true"})
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.error(f"Nano RPC block_info failed: {exc}")
        return False

    error = data.get("error")
    if error:
        if logger:
            logger.error(f"Nano RPC error: {error}")
        return False

    # The reported block must be a confirmed transfer of the right size to us.
    subtype = data.get("subtype")
    if subtype != "send":
        if logger:
            logger.error(f"Block {send_hash} is subtype '{subtype}', expected 'send'")
        return False

    if data.get("confirmed") not in (True, "true"):
        if logger:
            logger.error(f"Block {send_hash} is not confirmed")
        return False

    try:
        amount_raw = int(data.get("amount", "0"))
    except (TypeError, ValueError):
        amount_raw = 0
    if amount_raw < expected_raw:
        if logger:
            logger.error(
                f"Block {send_hash} sent {amount_raw / RAW_PER_XNO} XNO, "
                f"expected >= {expected_amount_xno}"
            )
        return False

    # contents.link_as_account is the destination account of a send block.
    contents = data.get("contents") or {}
    dest = contents.get("link_as_account", "")
    if dest.lower() != expected_recipient.lower():
        if logger:
            logger.error(
                f"Block {send_hash} was sent to {dest}, expected {expected_recipient}"
            )
        return False

    if logger:
        logger.info(
            f"Nano send verified: {send_hash} -> {dest} "
            f"({amount_raw / RAW_PER_XNO} XNO)"
        )
    return True
