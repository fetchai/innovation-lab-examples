"""Bind a Nano payment to the one order it was issued for (no wallet, no keys).

A Nano block has no memo, so "a confirmed send of the right amount to NANO_ACCOUNT"
proves nothing about WHICH order it paid. Here the seller issues an opaque random
order id per RequestPayment and asks the buyer to sign the send block with
``representative`` = a commitment account derived from (order id, payTo, price).
verify_nano.verify_nano_send(..., expected_representative=...) checks that field, and
this module keeps a persistent, one-to-one ``block hash -> order`` record in the
agent's ``ctx.storage`` (any object with has/get/set/remove) with a validity window.
See https://github.com/dhyabi2/xno-call-binding (docs/BINDING-STANDARD.md, option C).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time

_ALPHA = "13456789abcdefghijkmnopqrstuwxyz"
ORDER_PREFIX = "nano_order:"
BLOCK_PREFIX = "nano_block:"


def _enc32(data: bytes, chars: int) -> str:
    """Base32 (Nano alphabet) of ``data`` as exactly ``chars`` characters.

    Nano pads on the HIGH side: the 256-bit key is read as a 260-bit number with
    four leading zero bits, which is why every account starts with 1 or 3. Padding
    the low side instead gives a string a node never returns for the same key, so
    the representative check in verify_nano would refuse every honest payment.
    """
    n = int.from_bytes(data, "big")
    if n >> (5 * chars):
        raise ValueError("data does not fit in the requested width")
    return "".join(_ALPHA[(n >> (5 * i)) & 31] for i in reversed(range(chars)))


def pubkey_to_account(pub: bytes) -> str:
    """32-byte public key -> nano_ address (52 chars key + 8 chars blake2b-5 checksum)."""
    if len(pub) != 32:
        raise ValueError("public key must be 32 bytes")
    key = _enc32(pub, 52)
    chk = _enc32(hashlib.blake2b(pub, digest_size=5).digest()[::-1], 8)
    return "nano_" + key + chk


def commitment_rep_account(order_id: str, pay_to: str, price_raw: int) -> str:
    """Account the buyer must set as the send block's representative."""
    if isinstance(price_raw, bool) or not isinstance(price_raw, int):
        raise TypeError("price_raw must be an int of raw")
    msg = (
        b"xno-binding/v1/rep|"
        + order_id.encode()
        + b"|"
        + pay_to.encode()
        + b"|"
        + str(price_raw).encode()
    )
    return pubkey_to_account(hashlib.sha256(msg).digest())


def new_order(storage, buyer: str, pay_to: str, price_raw: int, ttl_s: int, now=None):
    """Issue an opaque (128-bit random) order id and persist it. Returns (id, rep, expires_at)."""
    now = int(time.time() if now is None else now)
    order_id = secrets.token_hex(16)
    expires_at = now + int(ttl_s)
    storage.set(
        ORDER_PREFIX + order_id,
        json.dumps(
            {
                "buyer": buyer,
                "pay_to": pay_to,
                "price_raw": str(price_raw),
                "expires_at": expires_at,
                "status": "open",
                "block": None,
            }
        ),
    )
    return order_id, commitment_rep_account(order_id, pay_to, price_raw), expires_at


def load_order(storage, order_id: str):
    raw = storage.get(ORDER_PREFIX + order_id) if order_id else None
    return json.loads(raw) if raw else None


def claim_block(storage, order_id: str, buyer: str, block_hash: str, now=None):
    """Synchronously (no await between check and set) reserve block_hash for the order.

    Returns (order, None) when reserved, or (None, reason). One block <-> one order:
    a hash already claimed, an order already claimed or paid, a different buyer, or an
    expired window are all refused.
    """
    now = int(time.time() if now is None else now)
    order = load_order(storage, order_id)
    if order is None:
        return None, "unknown order"
    if order["buyer"] != buyer:
        return None, "order belongs to another requester"
    if now > order["expires_at"]:
        return None, "order expired"
    if order["status"] != "open":
        return None, "order already claimed or paid"
    bkey = BLOCK_PREFIX + block_hash
    if storage.get(bkey):
        return None, "block already claimed"
    storage.set(bkey, order_id)
    order["status"], order["block"] = "claimed", block_hash
    storage.set(ORDER_PREFIX + order_id, json.dumps(order))
    return order, None


def release_block(storage, order_id: str, block_hash: str) -> None:
    """Verification failed: reopen the order. The block stays unclaimed for retry."""
    order = load_order(storage, order_id)
    if order and order.get("block") == block_hash and order["status"] == "claimed":
        order["status"], order["block"] = "open", None
        storage.set(ORDER_PREFIX + order_id, json.dumps(order))
        storage.remove(BLOCK_PREFIX + block_hash)


def finalize(storage, order_id: str) -> None:
    order = load_order(storage, order_id)
    if order:
        order["status"] = "paid"
        storage.set(ORDER_PREFIX + order_id, json.dumps(order))
