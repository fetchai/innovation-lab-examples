"""NANO_AMOUNT is validated when payment.py loads, not in the chat handler."""

import os
import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent


def _import_payment(amount):
    env = dict(os.environ, NANO_AMOUNT=amount)
    return subprocess.run(
        [sys.executable, "-c", "import payment"],
        cwd=AGENT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_non_numeric_amount_fails_at_startup_with_clear_message():
    for bad in ("abc", "", "-1", "0", "NaN"):
        r = _import_payment(bad)
        assert r.returncode != 0, bad
        assert "NANO_AMOUNT must be a positive XNO amount" in r.stderr, (bad, r.stderr)


def test_valid_amount_loads():
    r = _import_payment("0.0001")
    assert r.returncode == 0, r.stderr
