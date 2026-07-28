"""Encrypted, multi-user token + OAuth-state store, SQLite-backed.

Tokens are encrypted at rest with a NaCl SecretBox. The oauth_states table
maps a signed state value back to the ASI:One sender that started the OAuth
flow, plus an optional stashed pending request.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

from nacl import secret as nacl_secret

DB_PATH = os.getenv("TOKEN_DB_PATH", "twitchy_tokens.db")

# OAuth state lifetime — the user has this long to complete the consent screen.
STATE_TTL_SECONDS = 600


def _box() -> nacl_secret.SecretBox:
    raw = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set; cannot encrypt tokens.")
    # Derive a fixed 32-byte key from whatever string the operator provides.
    return nacl_secret.SecretBox(hashlib.sha256(raw.encode()).digest())


def _encrypt(plaintext: str) -> str:
    return base64.b64encode(_box().encrypt(plaintext.encode())).decode()


def _decrypt(ciphertext: str) -> str:
    return _box().decrypt(base64.b64decode(ciphertext)).decode()


def _state_secret() -> bytes:
    raw = os.getenv("OAUTH_STATE_SECRET")
    if not raw:
        raise RuntimeError("OAUTH_STATE_SECRET is not set; cannot sign OAuth state.")
    return raw.encode()


def make_state() -> str:
    """Create an opaque, signed state token: '<nonce>.<hmac>'."""
    nonce = secrets.token_urlsafe(18)
    sig = hmac.new(_state_secret(), nonce.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{nonce}.{sig}"


def verify_state_sig(state: str) -> bool:
    """Validate the HMAC signature of a state token (cheap pre-check)."""
    try:
        nonce, sig = state.split(".", 1)
    except (ValueError, AttributeError):
        return False
    expected = hmac.new(_state_secret(), nonce.encode(), hashlib.sha256).hexdigest()[
        :24
    ]
    return hmac.compare_digest(sig, expected)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            twitch_user_id TEXT PRIMARY KEY,
            asi1_sender_id TEXT,
            access_token   TEXT,
            refresh_token  TEXT,
            expires_at     REAL,
            scopes         TEXT,
            updated_at     REAL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tokens_sender ON tokens(asi1_sender_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_states (
            state      TEXT PRIMARY KEY,
            sender     TEXT,
            pending    TEXT,
            created_at REAL
        )
        """
    )
    return conn


def init_db() -> None:
    """Ensure the schema exists (safe to call repeatedly, e.g. on startup)."""
    _connect().close()


def save_state(state: str, sender: str, pending: "dict | None" = None) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO oauth_states (state, sender, pending, created_at) VALUES (?,?,?,?)",
            (state, sender, json.dumps(pending) if pending else None, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def pop_state(state: str) -> "dict | None":
    """Consume a state token. Returns {"sender", "pending"} or None if missing/expired."""
    conn = _connect()
    try:
        # Purge expired states first.
        conn.execute(
            "DELETE FROM oauth_states WHERE created_at < ?",
            (time.time() - STATE_TTL_SECONDS,),
        )
        row = conn.execute(
            "SELECT sender, pending, created_at FROM oauth_states WHERE state = ?",
            (state,),
        ).fetchone()
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        conn.commit()
    finally:
        conn.close()

    if not row:
        return None
    if row["created_at"] < time.time() - STATE_TTL_SECONDS:
        return None
    return {
        "sender": row["sender"],
        "pending": json.loads(row["pending"]) if row["pending"] else None,
    }


def upsert_tokens(
    *,
    twitch_user_id: str,
    asi1_sender_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: float,
    scopes: "list[str] | str",
) -> None:
    if isinstance(scopes, list):
        scopes = " ".join(scopes)
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO tokens
                (twitch_user_id, asi1_sender_id, access_token, refresh_token,
                 expires_at, scopes, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                twitch_user_id,
                asi1_sender_id,
                _encrypt(access_token),
                _encrypt(refresh_token),
                expires_at,
                scopes,
                time.time(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_tokens(row: sqlite3.Row) -> dict:
    return {
        "twitch_user_id": row["twitch_user_id"],
        "asi1_sender_id": row["asi1_sender_id"],
        "access_token": _decrypt(row["access_token"]),
        "refresh_token": _decrypt(row["refresh_token"]),
        "expires_at": row["expires_at"],
        "scopes": (row["scopes"] or "").split(),
    }


def get_tokens_by_sender(sender: str) -> "dict | None":
    """Most recently updated token row for an ASI:One sender (decrypted), or None."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM tokens WHERE asi1_sender_id = ? ORDER BY updated_at DESC LIMIT 1",
            (sender,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_tokens(row) if row else None


def get_tokens_by_twitch_id(twitch_user_id: str) -> "dict | None":
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM tokens WHERE twitch_user_id = ?", (twitch_user_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_tokens(row) if row else None


def update_access_token(
    *, twitch_user_id: str, access_token: str, refresh_token: str, expires_at: float
) -> None:
    """Persist refreshed tokens for an existing row."""
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE tokens
               SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = ?
             WHERE twitch_user_id = ?
            """,
            (
                _encrypt(access_token),
                _encrypt(refresh_token),
                expires_at,
                time.time(),
                twitch_user_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
