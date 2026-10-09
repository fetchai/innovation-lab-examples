"""Tests for the Nano (XNO) on-chain verification module.

These tests exercise the verification logic without depending on the live
public Nano RPC: they mock `verify_nano.nano_rpc_post` to return canned
`block_info` payloads and assert the decide logic (send subtype, confirmation,
destination, amount). This keeps CI deterministic and offline.
"""

import sys
from pathlib import Path

from unittest import mock

# Insert the module directory so the import works from any working directory
# (e.g. `pytest contributors/nano-xno-payment-agent/tests/` from the repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import verify_nano  # noqa: E402


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, *args):
        self.lines.append(("info", args))

    def error(self, *args):
        self.lines.append(("error", args))


def _send_block(amount_raw, dest="nano_1seller", confirmed=True, subtype="send"):
    return {
        "block_account": "nano_1buyer",
        "amount": str(amount_raw),
        "confirmed": "true" if confirmed else "false",
        "subtype": subtype,
        "contents": {
            "type": "state",
            "link_as_account": dest,
        },
    }


def test_verifies_confirmed_send_to_recipient():
    payload = _send_block(int(0.05 * verify_nano.RAW_PER_XNO))
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload) as rpc:
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    rpc.assert_called_once()
    assert ok is True


def test_rejects_amount_below_threshold():
    payload = _send_block(int(0.001 * verify_nano.RAW_PER_XNO))
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.05", logger=None)
    assert ok is False


def test_rejects_wrong_destination():
    payload = _send_block(int(0.05 * verify_nano.RAW_PER_XNO), dest="nano_1other")
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    assert ok is False


def test_rejects_unconfirmed_block():
    payload = _send_block(int(0.3 * verify_nano.RAW_PER_XNO), confirmed=False)
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    assert ok is False


def test_rejects_non_send_subtype():
    # A receive block (like a cashback for the same account) is not a buyer send.
    payload = _send_block(int(0.3 * verify_nano.RAW_PER_XNO), subtype="receive")
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    assert ok is False


def test_returns_false_for_blank_send_hash():
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value={}) as rpc:
        ok = verify_nano.verify_nano_send("", "nano_1seller", "0.03", logger=None)
    rpc.assert_not_called()
    assert ok is False


def test_returns_false_for_blank_recipient():
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value={}) as rpc:
        ok = verify_nano.verify_nano_send("ABC", "", "0.03", logger=None)
    rpc.assert_not_called()
    assert ok is False


def test_returns_false_for_invalid_amount():
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value={}) as rpc:
        ok = verify_nano.verify_nano_send(
            "ABC", "nano_1seller", "not-a-number", logger=None
        )
    rpc.assert_not_called()
    assert ok is False


def test_returns_false_for_live_rpc_error():
    with mock.patch.object(
        verify_nano,
        "nano_rpc_post",
        side_effect=RuntimeError("boom"),
    ):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    assert ok is False


def test_fails_closed_when_contents_is_a_hash_string():
    # A Nano node can return contents as the raw block hash string (legacy /
    # json_block not honoured) rather than the dict with link_as_account. The
    # verifier must not crash with AttributeError; it must fail closed.
    payload = _send_block(int(0.05 * verify_nano.RAW_PER_XNO))
    payload["contents"] = (
        "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF"
    )
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    assert ok is False


def test_fails_closed_when_contents_missing():
    # Missing contents (None) must also fail closed rather than crash.
    payload = _send_block(int(0.05 * verify_nano.RAW_PER_XNO))
    payload["contents"] = None
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        ok = verify_nano.verify_nano_send("ABC", "nano_1seller", "0.03", logger=None)
    assert ok is False


# --- Buyer-declared amount guard (AI-review blocking finding 2026-09-25) ---
# The seller must verify against what IT accepted (ACCEPTED_FUNDS[0].amount),
# never the buyer-controlled msg.funds.amount. declared_matches_accepted is the
# pure decision used in payment.py before any on-chain check.


def test_declared_matches_accepted_exact():
    # 0.0001 declared against 0.0001 accepted -> exact match, accepted.
    assert verify_nano.declared_matches_accepted("0.0001", "0.0001") is True
    assert verify_nano.declared_matches_accepted("0.5", "0.5") is True


def test_declared_matches_accepted_mismatch_rejected():
    # A buyer declaring less (or more) than the accepted amount must NOT match.
    assert verify_nano.declared_matches_accepted("0.00001", "0.0001") is False
    assert verify_nano.declared_matches_accepted("0.001", "0.0001") is False
    # The classic bypass: a microscopic declared amount.
    assert (
        verify_nano.declared_matches_accepted("0.000000000000000000001", "0.0001")
        is False
    )


def test_declared_matches_accepted_unparseable_fails_closed():
    # A buyer passing a non-numeric amount must fail closed.
    assert verify_nano.declared_matches_accepted("abc", "0.0001") is False
    assert verify_nano.declared_matches_accepted("", "0.0001") is False
    assert verify_nano.declared_matches_accepted("0.0001", "") is False


def test_payment_verifies_seller_accepted_amount_not_declared():
    """verify/commit path must not let the buyer set the verification threshold.

    Static guard: payment.py must call verify_nano_send with the seller's
    accepted amount and must reject a mismatched declared amount — never pass
    msg.funds.amount straight through to the on-chain verifier.
    """
    src = (Path(__file__).resolve().parent.parent / "payment.py").read_text()
    # verify_nano_send must be called with the seller's accepted amount, not the
    # buyer-declared msg.funds.amount.
    assert "str(accepted_amount)" in src, (
        "verify_nano_send must use the seller's accepted amount"
    )
    # The only place the buyer-declared amount appears must be the mismatch
    # guard (which rejects it against the accepted amount) — never as the
    # verification threshold passed to the on-chain verifier.
    assert "declared_matches_accepted(msg.funds.amount, accepted_amount)" in src
    assert "does not match the " in src and "accepted amount" in src
