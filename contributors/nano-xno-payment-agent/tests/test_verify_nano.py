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
