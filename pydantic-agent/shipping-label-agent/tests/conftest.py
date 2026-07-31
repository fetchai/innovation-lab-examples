"""Shared test setup.

Sets deterministic **test** credentials for the whole suite before any project
module is imported, and exposes an autouse fixture that fails loudly if any key
does not match its test-key prefix - so a live key can never sneak into a run.
"""

from __future__ import annotations

import os

import pytest

# Test credentials — set before importing project modules. These are obviously
# fake and only exercise the test-key-prefix guards; no network call uses them.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy_secret")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_dummy_publishable")
os.environ.setdefault("SHIPPO_TOKEN", "shippo_test_dummy_token")
os.environ.setdefault("ASI_ONE_API_KEY", "asi-test-key-not-used")

STRIPE_TEST_SECRET_PREFIX = "sk_test_"
STRIPE_TEST_PUBLISHABLE_PREFIX = "pk_test_"
SHIPPO_TEST_PREFIX = "shippo_test_"


@pytest.fixture(autouse=True)
def require_test_keys() -> None:
    """Fail the test run loudly unless every configured key is a test key."""
    secret = os.environ.get("STRIPE_SECRET_KEY", "")
    assert secret.startswith(STRIPE_TEST_SECRET_PREFIX), (
        f"STRIPE_SECRET_KEY must start with {STRIPE_TEST_SECRET_PREFIX!r} (test key only)"
    )
    publishable = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    if publishable:
        assert publishable.startswith(STRIPE_TEST_PUBLISHABLE_PREFIX), (
            f"STRIPE_PUBLISHABLE_KEY must start with {STRIPE_TEST_PUBLISHABLE_PREFIX!r}"
        )
    shippo_token = os.environ.get("SHIPPO_TOKEN", "")
    assert shippo_token.startswith(SHIPPO_TEST_PREFIX), (
        f"SHIPPO_TOKEN must start with {SHIPPO_TEST_PREFIX!r} (test token only)"
    )
