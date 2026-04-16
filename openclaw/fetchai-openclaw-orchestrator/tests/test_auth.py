"""Tests for connector.auth – request signature verification."""

import json

from connector.auth import RequestAuthenticator
from shared.crypto import generate_keypair, public_key_to_hex, sign_payload
from shared.schemas import RejectionReason, TaskPlan, TaskStep, StepType


def _make_signed_plan():
    """Helper: create a plan, sign it, return (plan_json, sig_hex, pub_hex)."""
    priv, pub = generate_keypair()
    plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="scan_directory")])
    plan_dict = plan.model_dump(mode="json")
    plan_json = json.dumps(plan_dict, sort_keys=True, default=str)
    sig = sign_payload(priv, plan_dict)
    return plan_json, sig, public_key_to_hex(pub)


def test_verify_valid_signature():
    plan_json, sig, pub_hex = _make_signed_plan()
    auth = RequestAuthenticator(orchestrator_public_key_hex=pub_hex)
    ok, reason = auth.verify_dispatch(plan_json, sig)
    assert ok is True
    assert reason is None


def test_reject_empty_signature():
    auth = RequestAuthenticator(orchestrator_public_key_hex="a" * 64)
    ok, reason = auth.verify_dispatch("{}", "")
    assert ok is False
    assert reason == RejectionReason.INVALID_SIGNATURE


def test_reject_tampered_payload():
    plan_json, sig, pub_hex = _make_signed_plan()
    auth = RequestAuthenticator(orchestrator_public_key_hex=pub_hex)
    tampered = plan_json.replace("scan_directory", "delete_all")
    ok, reason = auth.verify_dispatch(tampered, sig)
    assert ok is False
    assert reason == RejectionReason.INVALID_SIGNATURE


def test_no_key_allows_in_dev_mode():
    """With no orchestrator key configured, verification is skipped."""
    auth = RequestAuthenticator()
    ok, reason = auth.verify_dispatch("{}", "any-sig")
    assert ok is True
    assert reason is None


def test_reject_wrong_key():
    plan_json, sig, _ = _make_signed_plan()
    _, other_pub = generate_keypair()
    auth = RequestAuthenticator(
        orchestrator_public_key_hex=public_key_to_hex(other_pub)
    )
    ok, reason = auth.verify_dispatch(plan_json, sig)
    assert ok is False
