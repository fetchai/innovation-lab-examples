"""Tests for shared.crypto – keypair generation, signing, verification."""

import tempfile

from shared.crypto import (
    generate_keypair,
    load_keypair,
    private_key_to_hex,
    public_key_to_hex,
    save_keypair,
    sign_payload,
    verify_signature,
)


def test_generate_keypair():
    priv, pub = generate_keypair()
    assert priv is not None
    assert pub is not None


def test_hex_roundtrip():
    priv, pub = generate_keypair()
    priv_hex = private_key_to_hex(priv)
    pub_hex = public_key_to_hex(pub)
    assert len(priv_hex) == 64  # 32 bytes → 64 hex chars
    assert len(pub_hex) == 64


def test_sign_and_verify():
    priv, pub = generate_keypair()
    pub_hex = public_key_to_hex(pub)
    payload = {"task_id": "t1", "action": "scan_directory"}

    sig = sign_payload(priv, payload)
    assert isinstance(sig, str)
    assert len(sig) == 128  # 64 bytes → 128 hex chars

    assert verify_signature(pub_hex, payload, sig) is True


def test_verify_rejects_tampered_payload():
    priv, pub = generate_keypair()
    pub_hex = public_key_to_hex(pub)
    payload = {"task_id": "t1"}
    sig = sign_payload(priv, payload)

    tampered = {"task_id": "t2"}
    assert verify_signature(pub_hex, tampered, sig) is False


def test_verify_rejects_wrong_key():
    priv1, _ = generate_keypair()
    _, pub2 = generate_keypair()
    pub2_hex = public_key_to_hex(pub2)

    payload = {"x": 1}
    sig = sign_payload(priv1, payload)
    assert verify_signature(pub2_hex, payload, sig) is False


def test_save_and_load_keypair():
    priv, pub = generate_keypair()
    with tempfile.TemporaryDirectory() as tmpdir:
        save_keypair(tmpdir, priv)
        loaded_priv, loaded_pub = load_keypair(tmpdir)

    assert private_key_to_hex(loaded_priv) == private_key_to_hex(priv)
    assert public_key_to_hex(loaded_pub) == public_key_to_hex(pub)
