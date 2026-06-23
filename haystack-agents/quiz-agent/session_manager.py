"""Persistent per-user quiz session state, backed by ``ctx.storage``.

Each user's session is stored as a JSON blob under the key
``session:<sender_address>``.  The state machine has eight states:

    UNINITIALIZED → AWAITING_PAYMENT → CHOOSING_SOURCE_TYPE
    → AWAITING_FILE_ATTACH → AWAITING_SOURCES → INDEXING
    → QUIZZING → COMPLETED

Everything is JSON-serialised because ``ctx.storage`` only persists
JSON-compatible values.
"""

from __future__ import annotations

import json
import time
from typing import Any

from uagents import Context

# State machine constants.
UNINITIALIZED = "UNINITIALIZED"
AWAITING_PAYMENT = "AWAITING_PAYMENT"
CHOOSING_SOURCE_TYPE = "CHOOSING_SOURCE_TYPE"  # router card shown
AWAITING_FILE_ATTACH = "AWAITING_FILE_ATTACH"  # plain-text file capture
AWAITING_SOURCES = "AWAITING_SOURCES"
INDEXING = "INDEXING"
QUIZZING = "QUIZZING"
COMPLETED = "COMPLETED"

_SESSION_KEY = "session:{}"


def compute_weak_topics(state_data: dict[str, Any]) -> list[str]:
    """Return distinct topics the user answered incorrectly or skipped, in order."""
    questions = state_data.get("questions", [])
    answers = state_data.get("answers", {})
    weak: list[str] = []
    for q in questions:
        user_ans = answers.get(q["q_id"])
        # Treat unanswered (None) the same as a wrong answer — both need review.
        if user_ans != q["correct"]:
            topic = q.get("topic", "General")
            if topic not in weak:
                weak.append(topic)
    return weak


class SessionManager:
    """Thin, stateless wrapper around ``ctx.storage`` for per-user sessions."""

    def default_state(self) -> dict[str, Any]:
        """Return a fresh UNINITIALIZED session dict."""
        return {
            "state": UNINITIALIZED,
            "stripe_session_id": None,
            "stripe_paid": False,
            "sources": {},
            "questions": [],
            "original_questions": [],  # preserved so Full Retake always uses originals
            "answers": {},
            "current_q": 0,
            "score": 0,
            "time_limit_mins": 0,  # 0 = no limit; >0 = personal countdown
            "quiz_start_ts": None,  # unix timestamp when quiz entered QUIZZING
            "doc_store_key": None,
            "pending_pdf_uris": [],  # Agentverse storage URIs for PDFs
            "pending_urls": [],  # URLs captured during file-attach step
            "created_at": time.time(),
        }

    def get(self, ctx: Context, sender: str) -> dict[str, Any]:
        """Load the session for ``sender`` (or a default UNINITIALIZED one)."""
        raw = ctx.storage.get(_SESSION_KEY.format(sender))
        if not raw:
            return self.default_state()
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return self.default_state()

    def save(self, ctx: Context, sender: str, data: dict[str, Any]) -> None:
        """Persist the session dict for ``sender``."""
        ctx.storage.set(_SESSION_KEY.format(sender), json.dumps(data))
