"""
Cryptographic utilities for the Fetch-OpenClaw integration.

Uses Ed25519 for:
  • Device keypair generation
  • Task plan signing (orchestrator → connector)
  • Signature verification (connector side)
"""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a fresh Ed25519 keypair."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def private_key_to_hex(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    return raw.hex()


def public_key_to_hex(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return raw.hex()


def private_key_from_hex(hex_str: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_str))


def public_key_from_hex(hex_str: str) -> Ed25519PublicKey:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey as _Pub,
    )

    return _Pub.from_public_bytes(bytes.fromhex(hex_str))


# ---------------------------------------------------------------------------
# Signing / verification
# ---------------------------------------------------------------------------


def sign_payload(private_key: Ed25519PrivateKey, payload: dict) -> str:
    """Sign a JSON-serialisable dict; return hex-encoded signature."""
    canonical = json.dumps(payload, sort_keys=True, default=str).encode()
    sig = private_key.sign(canonical)
    return sig.hex()


def verify_signature(
    public_key_hex: str,
    payload: dict,
    signature_hex: str,
) -> bool:
    """Verify an Ed25519 signature over a canonical JSON payload."""
    try:
        pub = public_key_from_hex(public_key_hex)
        canonical = json.dumps(payload, sort_keys=True, default=str).encode()
        pub.verify(bytes.fromhex(signature_hex), canonical)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def save_keypair(directory: str | Path, private_key: Ed25519PrivateKey) -> Path:
    """Persist a keypair to *directory*; returns the directory path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    priv_hex = private_key_to_hex(private_key)
    pub_hex = public_key_to_hex(private_key.public_key())

    (directory / "private.hex").write_text(priv_hex)
    (directory / "public.hex").write_text(pub_hex)
    return directory


def load_keypair(directory: str | Path) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Load a previously-saved keypair from *directory*."""
    directory = Path(directory)
    priv = private_key_from_hex((directory / "private.hex").read_text().strip())
    return priv, priv.public_key()
