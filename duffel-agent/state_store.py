# state_store.py

import sqlite3
import threading
import json
import os
from typing import Any, Dict, Optional

_DB_PATH = os.getenv("SESSION_DB_PATH", "./state/sessions.db")

# Ensure directory exists
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

_conn: Optional[sqlite3.Connection] = None
_conn_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False, isolation_level=None)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_state (
                user_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _conn = conn
    return _conn


def load_state(user_id: str) -> Dict[str, Any]:
    conn = _get_conn()
    cur = conn.execute(
        "SELECT state_json FROM session_state WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    if row:
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            # corruption fallback
            return {}
    return {}


def save_state(user_id: str, state: Dict[str, Any]) -> None:
    conn = _get_conn()
    state_json = json.dumps(state)
    with _conn_lock:
        conn.execute(
            """
            INSERT INTO session_state(user_id, state_json) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
              state_json=excluded.state_json, 
              updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, state_json)
        )


def clear_state(user_id: str) -> None:
    conn = _get_conn()
    with _conn_lock:
        conn.execute(
            "DELETE FROM session_state WHERE user_id = ?",
            (user_id,)
        )