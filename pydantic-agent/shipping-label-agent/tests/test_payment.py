"""Stripe payment gate tests: happy path + Stripe's documented decline card.

No network: the Stripe SDK is replaced with a small in-memory fake via
``payment._stripe``. The decline path uses Stripe's documented ``card_declined``
test number (``4000000000000002``) to model a checkout that never becomes paid.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import payment


class _FakeSession:
    def __init__(self, session_id: str, url: str, payment_status: str) -> None:
        self.id = session_id
        self.url = url
        self.payment_status = payment_status
        self.client_secret = "cs_secret_test"


class FakeStripe:
    """Minimal stand-in for the ``stripe`` module used by ``payment``."""

    def __init__(self) -> None:
        self.api_key: str | None = None
        self._sessions: dict[str, _FakeSession] = {}
        self._next = ("cs_test_paid", "https://checkout.stripe.test/pay", "paid")
        self.checkout = SimpleNamespace(
            Session=SimpleNamespace(create=self._create, retrieve=self._retrieve)
        )

    def set_next(self, session_id: str, payment_status: str) -> None:
        self._next = (session_id, "https://checkout.stripe.test/pay", payment_status)

    def _create(self, **_: object) -> _FakeSession:
        session_id, url, status = self._next
        session = _FakeSession(session_id, url, status)
        self._sessions[session_id] = session
        return session

    def _retrieve(self, session_id: str) -> _FakeSession:
        return self._sessions.get(session_id, _FakeSession(session_id, "", "unpaid"))


@pytest.fixture()
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(payment, "_stripe", lambda: fake)
    return fake


def test_assert_stripe_test_keys_accepts_test_keys() -> None:
    # Uses the sk_test_/pk_test_ keys from conftest — should not raise.
    payment.assert_stripe_test_keys()


def test_assert_stripe_test_keys_rejects_live_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_should_never_run")
    with pytest.raises(RuntimeError):
        payment.assert_stripe_test_keys()


def test_checkout_session_is_embedded_and_carries_client_secret(
    fake_stripe: FakeStripe,
) -> None:
    fake_stripe.set_next("cs_test_ok", "paid")
    checkout = payment.create_checkout_session("agent1qxyz", "session-123")
    assert checkout["checkout_session_id"] == "cs_test_ok"
    assert checkout["ui_mode"] == "embedded_page"
    assert checkout["client_secret"]
    # All metadata values must be plain strings - RequestPayment.metadata is
    # typed dict[str, str | dict[str, str]], so nested values can't be int/etc.
    assert all(isinstance(v, str) for v in checkout.values())


def test_happy_path_payment_confirmed(fake_stripe: FakeStripe) -> None:
    fake_stripe.set_next("cs_test_ok", "paid")
    checkout = payment.create_checkout_session("agent1qxyz", "session-123")
    assert payment.verify_paid(checkout["checkout_session_id"]) is True


def test_documented_decline_card_is_never_paid(fake_stripe: FakeStripe) -> None:
    # Stripe's documented generic decline card.
    assert payment.TEST_DECLINE_CARD == "4000000000000002"
    # A checkout paid for with the decline card stays unpaid.
    fake_stripe.set_next("cs_test_declined", "unpaid")
    checkout = payment.create_checkout_session("agent1qxyz", "session-123")
    assert payment.verify_paid(checkout["checkout_session_id"]) is False


def test_verify_paid_handles_missing_session(fake_stripe: FakeStripe) -> None:
    assert payment.verify_paid("") is False
    assert payment.verify_paid("cs_never_created") is False
