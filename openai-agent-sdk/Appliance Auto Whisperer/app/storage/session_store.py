from __future__ import annotations

import time
import uuid

from app.config.constants import SESSION_TTL_SECONDS
from app.models.session_state import SessionState


class SessionStore:
    def __init__(self) -> None:
        self._last_seen: dict[str, float] = {}
        self._states: dict[str, SessionState] = {}

    def new_session(self) -> str:
        sid = uuid.uuid4().hex
        self.touch(sid)
        return sid

    def touch(self, session_id: str) -> None:
        self._last_seen[session_id] = time.time()
        cutoff = time.time() - SESSION_TTL_SECONDS
        dead = [k for k, t in self._last_seen.items() if t < cutoff]
        for k in dead:
            self._last_seen.pop(k, None)
            self._states.pop(k, None)

    def put_state(self, session_id: str, state: SessionState) -> None:
        self._states[session_id] = state

    def get_state(self, session_id: str) -> SessionState | None:
        return self._states.get(session_id)
