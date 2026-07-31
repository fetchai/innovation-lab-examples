"""Per-user orchestrator session state.

The orchestrator owns two things on the user's behalf:

1. **Profile pointer** — which profile-agent `user_key` belongs to this
   chat sender, plus a small cache of the last-known profile snapshot
   so we can answer `show profile` without a round-trip on every turn.
2. **Apply pointer** — when we hand off into `form-filler-agent`, we
   remember a coarse "we're currently applying" flag so subsequent
   chat turns can be routed correctly.

Stored under `ctx.storage["orch:<sender_address>"]`.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


SESSION_KEY_PREFIX = "orch:"


class ApplyState(str, Enum):
    IDLE = "idle"
    # The user pasted a URL and we've sent them a RequestPayment;
    # waiting for CommitPayment before we touch form-filler.
    PAYMENT_PENDING = "payment_pending"
    APPLYING = "applying"
    DONE = "done"


@dataclass
class OrchestratorSession:
    user_address: str
    user_key: str = field(default="")

    def __post_init__(self):
        if not self.user_key:
            self.user_key = self.user_address

    # Profile cache — last `show_profile` response so re-renders are cheap.
    profile_summary: Optional[dict[str, Any]] = None
    profile_loaded_at: float = 0.0

    # Resume version registry the orchestrator maintains. Each entry:
    # {name, source_filename, ingested_at, path}
    resume_versions: list[dict[str, Any]] = field(default_factory=list)
    active_resume_version: Optional[str] = None

    # Application handoff state.
    apply_state: ApplyState = ApplyState.IDLE
    apply_job_url: Optional[str] = None

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["apply_state"] = self.apply_state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OrchestratorSession":
        data = dict(d)
        apply_state_val = data.pop("apply_state", ApplyState.IDLE.value)
        sess = cls(user_address=data.pop("user_address"))
        sess.apply_state = ApplyState(apply_state_val)
        for key, value in data.items():
            if key == "user_key" and value == "me":
                continue  # migrate old sessions to per-user keys
            if hasattr(sess, key):
                setattr(sess, key, value)
        return sess


# ---------------------------------------------------------------------------
# ctx.storage helpers
# ---------------------------------------------------------------------------


def storage_key(user_address: str) -> str:
    return f"{SESSION_KEY_PREFIX}{user_address}"


def load(storage, user_address: str) -> OrchestratorSession:
    """Return the existing session for `user_address`, or a fresh one."""
    raw = storage.get(storage_key(user_address))
    if not raw:
        return OrchestratorSession(user_address=user_address)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:  # noqa: BLE001
            return OrchestratorSession(user_address=user_address)
    try:
        return OrchestratorSession.from_dict(raw)
    except Exception:  # noqa: BLE001
        return OrchestratorSession(user_address=user_address)


def save(storage, sess: OrchestratorSession) -> None:
    sess.updated_at = time.time()
    storage.set(storage_key(sess.user_address), sess.to_dict())


def clear(storage, user_address: str) -> None:
    try:
        storage.remove(storage_key(user_address))
    except Exception:  # noqa: BLE001
        try:
            storage.set(storage_key(user_address), None)
        except Exception:  # noqa: BLE001
            pass
