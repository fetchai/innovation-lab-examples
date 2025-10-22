# tools/fet_payments.py
"""
FET payment verification via Cosmos-SDK (FET) Ledger.

Verifies a bank-transfer style transaction by:
- tx_hash (Cosmos tx endpoint)
- recipient_address
- amount in FET units

Falls back to logs/events parsing if MsgSend is missing. Uses retries because indexing may lag.

Environment variables:
  FET_LCD_URL             (default: https://rest-dorado.fetch.ai)
  FET_DENOM               (default: "afet"; used for heuristics/logging)
  FET_DENOM_SCALE         (optional float, e.g., 1e18 for ‘afet’ or 1e6 for ‘ufet’)
  FET_VERIFY_ATTEMPTS     (default: 5)
  FET_VERIFY_DELAY_SEC    (default: 2.0)
"""

from __future__ import annotations
import os
import math
import asyncio
from typing import Optional, Any, Dict

import httpx

FET_LCD_URL = os.getenv("FET_LCD_URL", "https://rest-dorado.fetch.ai").rstrip("/")
FET_DENOM = os.getenv("FET_DENOM", "afet")
FET_VERIFY_ATTEMPTS = int(os.getenv("FET_VERIFY_ATTEMPTS", "5"))
FET_VERIFY_DELAY_SEC = float(os.getenv("FET_VERIFY_DELAY_SEC", "2.0"))

def _denom_scale(denom: Optional[str]) -> float:
    """Determine scaling factor: converts atomic units to FET units."""
    env = os.getenv("FET_DENOM_SCALE")
    if env:
        try:
            s = float(env)
            if s > 0:
                return s
        except Exception:
            pass
    d = (denom or "").strip().lower()
    # heuristic: if denom starts with 'u' assume micro (1e6)
    if d.startswith("u"):
        return 1e6
    # default to atto (1e18)
    return 1e18

def _to_float(s: Any) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None

def _nearly_equal(a: float, b: float, rel_tol: float = 1e-6, abs_tol: float = 1e-12) -> bool:
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)

def _parse_amount_denom_atom(s: str) -> tuple[Optional[float], str]:
    """
    Parse string like "1000000ufet" or "5000afet" → (amount_atom, denom).
    Caller may split on commas before calling.
    """
    num = []
    denom = []
    for ch in s:
        if ch.isdigit() or ch == ".":
            num.append(ch)
        else:
            denom.append(ch)
    if not num:
        return None, "".join(denom)
    try:
        amt_atom = float("".join(num))
    except ValueError:
        return None, "".join(denom)
    return amt_atom, "".join(denom)

async def _fetch_tx_json(tx_hash: str, logger) -> Optional[Dict[str, Any]]:
    """Fetch transaction JSON from Fetch ledger with retries."""
    if not tx_hash:
        return None
    candidates = [tx_hash, tx_hash.lower()]
    async with httpx.AsyncClient(timeout=20.0) as client:
        for attempt in range(1, FET_VERIFY_ATTEMPTS + 1):
            for h in candidates:
                url = f"{FET_LCD_URL}/cosmos/tx/v1beta1/txs/{h}"
                try:
                    resp = await client.get(url)
                except httpx.HTTPError as e:
                    logger.error(f"LCD request error: {type(e).__name__}: {e}")
                    continue
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as e:
                        logger.error(f"Invalid JSON from LCD: {e}")
                        return None
                # 404 often means not yet indexed; retry
            if attempt < FET_VERIFY_ATTEMPTS:
                await asyncio.sleep(FET_VERIFY_DELAY_SEC)
    logger.error("LCD tx fetch failed: not found after retries")
    return None

def _check_tx_code_ok(data: Dict[str, Any], logger) -> bool:
    try:
        code = int((data.get("tx_response") or {}).get("code", 0))
        if code != 0:
            logger.error(f"Non-zero tx code: {code}")
            return False
        return True
    except Exception:
        return True

def _match_via_messages(
    data: Dict[str, Any],
    recipient_address: str,
    expected_amount_fet: float,
    logger,
    *,
    sender_address: Optional[str] = None
) -> bool:
    """Check for Cosmos MsgSend in body-messages matching recipient and amount."""
    tx = data.get("tx") or {}
    body = tx.get("body") or {}
    msgs = body.get("messages") or []
    for m in msgs:
        msg_type = m.get("@type") or ""
        if "MsgSend" not in msg_type:
            continue
        to_addr = m.get("to_address")
        from_addr = m.get("from_address")
        if to_addr != recipient_address:
            continue
        if sender_address and from_addr and sender_address != from_addr:
            continue
        for coin in (m.get("amount") or []):
            denom = (coin.get("denom") or "").lower()
            amt_atom = _to_float(coin.get("amount"))
            if amt_atom is None:
                continue
            scale = _denom_scale(denom)
            amt_fet = amt_atom / scale
            if _nearly_equal(amt_fet, expected_amount_fet):
                return True
    return False

def _match_via_events(
    data: Dict[str, Any],
    recipient_address: str,
    expected_amount_fet: float,
    logger
) -> bool:
    """Fallback: scan logs → events 'coin_received' or 'transfer'."""
    txr = data.get("tx_response") or {}
    logs = txr.get("logs") or []
    for log in logs:
        for ev in (log.get("events") or []):
            etype = (ev.get("type") or "").lower()
            if etype not in ("coin_received","transfer"):
                continue
            receiver = None
            amount_raw = None
            for a in (ev.get("attributes") or []):
                k = (a.get("key") or "").lower()
                v = a.get("value") or ""
                if k in ("receiver","recipient"):
                    receiver = v
                elif k == "amount":
                    amount_raw = v
            if receiver != recipient_address or not amount_raw:
                continue
            parts = amount_raw.split(",") if "," in amount_raw else [amount_raw]
            for p in parts:
                amt_atom, denom = _parse_amount_denom_atom(p)
                if amt_atom is None:
                    continue
                scale = _denom_scale(denom)
                amt_fet = amt_atom / scale
                if _nearly_equal(amt_fet, expected_amount_fet):
                    return True
    return False

async def verify_fet_payment(
    tx_hash: str,
    recipient_address: str,
    amount_fet: str | float,
    logger,
    *,
    sender_address: Optional[str] = None
) -> bool:
    """Main entry: ensure tx_hash sent `amount_fet` FET to `recipient_address`."""
    if not tx_hash or not recipient_address:
        logger.error("verify_fet_payment: missing tx_hash or recipient_address")
        return False
    expected_amount = _to_float(amount_fet)
    if expected_amount is None or expected_amount <= 0:
        logger.error(f"verify_fet_payment: invalid amount_fet={amount_fet!r}")
        return False

    data = await _fetch_tx_json(tx_hash, logger)
    if not data:
        return False

    if not _check_tx_code_ok(data, logger):
        return False

    if _match_via_messages(data, recipient_address, expected_amount, logger, sender_address=sender_address):
        return True

    if _match_via_events(data, recipient_address, expected_amount, logger):
        return True

    logger.error("verify_fet_payment: no matching transfer found for recipient/amount")
    return False