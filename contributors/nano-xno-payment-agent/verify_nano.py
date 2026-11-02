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
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

# Public Nano RPC (rpc.nano.to). No key required for read actions.
# Override with the NANO_RPC_URL env var to point at a private/shared node.
NANO_RPC_URL = os.getenv("NANO_RPC_URL", "https://rpc.nano.to")

# Node lookups are bounded: 15 s timeout, 64 KiB response cap, and plain-HTTP RPC is
# refused unless the host is loopback.
RPC_TIMEOUT_S = 15
RPC_MAX_BYTES = 64 * 1024
_LOOPBACK = ("localhost", "127.0.0.1", "::1")


def rpc_url_allowed(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and parts.hostname in _LOOPBACK


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


def declared_matches_accepted(declared_xno, accepted_xno) -> bool:
    """True iff a buyer's declared funds exactly equal what the seller accepted.

    The buyer controls the amount they declare on CommitPayment, so accepting
    \"at least the declared amount\" lets a buyer price themselves at a
    microscopic figure.  The accepted amount comes from the seller's own
    ACCEPTED_FUNDS (what it requested through RequestPayment), never from the
    buyer's message.  Returns False for any non-equality or unparseable value,
    so a bad declared amount fails closed.
    """
    declared_raw = _xno_to_raw(str(declared_xno))
    accepted_raw = _xno_to_raw(str(accepted_xno))
    if declared_raw is None or accepted_raw is None:
        return False
    return declared_raw == accepted_raw


def nano_rpc_post(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """POST a Nano RPC action to the public node and return parsed JSON."""
    if not rpc_url_allowed(NANO_RPC_URL):
        raise ValueError("NANO_RPC_URL must be https (plain http only for loopback)")
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
    with urllib.request.urlopen(req, timeout=RPC_TIMEOUT_S) as resp:  # noqa: S310
        body = resp.read(RPC_MAX_BYTES + 1)
    if len(body) > RPC_MAX_BYTES:
        raise ValueError("Nano RPC response too large")
    return json.loads(body.decode("utf-8"))


def verify_nano_send(
    send_hash: str,
    expected_recipient: str,
    expected_amount_xno: str | float,
    *,
    expected_representative: str | None = None,
    valid_from: int | None = None,
    valid_until: int | None = None,
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
    # With json_block it is a dict; some nodes/legacy paths return the raw
    # block hash as a string instead. Guard against both so the handler never
    # crashes on a malformed payload — fail closed on anything unexpected.
    contents = data.get("contents")
    if not isinstance(contents, dict):
        if logger:
            got = type(contents).__name__ if contents is not None else "missing"
            logger.error(
                f"Block {send_hash} returned unexpected contents ({got}); "
                "cannot confirm destination"
            )
        return False
    dest = contents.get("link_as_account", "") or ""
    if dest.lower() != expected_recipient.lower():
        if logger:
            logger.error(
                f"Block {send_hash} was sent to {dest}, expected {expected_recipient}"
            )
        return False

    # Order binding: the buyer signed the order commitment into the block's
    # representative (see nano_binding.py), so this block is for THIS order only.
    if expected_representative is not None:
        rep = contents.get("representative", "") or ""
        if rep.lower() != expected_representative.lower():
            if logger:
                logger.error(f"Block {send_hash} is not committed to this order")
            return False
    # Window: judged on the block's own time, not on when the commit arrived.
    if valid_from is not None or valid_until is not None:
        try:
            block_time = int(data.get("local_timestamp", ""))
        except (TypeError, ValueError):
            block_time = 0
        if (
            block_time <= 0
            or (valid_from is not None and block_time < valid_from)
            or (valid_until is not None and block_time > valid_until)
        ):
            if logger:
                logger.error(
                    f"Block {send_hash} time {block_time} outside the order window"
                )
            return False

    if logger:
        logger.info(
            f"Nano send verified: {send_hash} -> {dest} "
            f"({amount_raw / RAW_PER_XNO} XNO)"
        )
    return True
