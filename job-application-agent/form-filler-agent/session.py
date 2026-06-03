"""Per-user session state for the form-filler agent.

The session captures everything we need to keep showing the user a coherent
"this is your application form" view between chat turns:

- which Greenhouse posting is loaded
- the current set of filled fields (with provenance + confidence)
- which required fields are still missing
- a state enum to gate which user commands are valid
- a small history of user-applied edits (used for save-back to the profile)

Stored under `ctx.storage["session:<sender_address>"]` as a JSON-serialisable
dict. There is at most one active session per user; starting a new one
overwrites the previous one.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


SESSION_KEY_PREFIX = "session:"


class State(str, Enum):
    IDLE = "idle"
    EXTRACTING = "extracting"
    MAPPING = "mapping"
    REVIEWING = "reviewing"
    SUBMITTING = "submitting"
    DONE = "done"


@dataclass
class Session:
    user_address: str
    state: State = State.IDLE
    job_json: Optional[str] = None  # raw JobInfo JSON from the extractor
    job_title: Optional[str] = None
    job_company: Optional[str] = None
    job_location: Optional[str] = None
    board_token: Optional[str] = None
    job_id: Optional[str] = None
    # Each filled entry: {name, label, value, source, confidence, ftype}
    filled: list[dict[str, Any]] = field(default_factory=list)
    # Question schema (denormalised from job_json for fast lookup in commands)
    questions: list[dict[str, Any]] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    resume_path: Optional[str] = None
    last_submission: Optional[dict[str, Any]] = None
    user_edits: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------
    def index_of(self, name: str) -> int:
        for i, f in enumerate(self.filled):
            if f.get("name") == name:
                return i
        return -1

    def question_for(self, name: str) -> Optional[dict[str, Any]]:
        """Return the question dict that owns the field `name`, or None."""
        for q in self.questions:
            for f in q.get("fields") or []:
                if f.get("name") == name:
                    return q
        return None

    def field_meta(self, name: str) -> Optional[dict[str, Any]]:
        """Return the field-schema dict for `name`."""
        for q in self.questions:
            for f in q.get("fields") or []:
                if f.get("name") == name:
                    return f
        return None

    def set_field(
        self,
        name: str,
        value: Any,
        *,
        source: str,
        confidence: float = 1.0,
    ) -> None:
        label = ""
        ftype = ""
        q = self.question_for(name)
        if q:
            label = q.get("label") or ""
        meta = self.field_meta(name)
        if meta:
            ftype = meta.get("type") or ""

        idx = self.index_of(name)
        entry = {
            "name": name,
            "label": label,
            "value": value,
            "source": source,
            "confidence": confidence,
            "ftype": ftype,
        }
        if idx >= 0:
            self.filled[idx] = entry
        else:
            self.filled.append(entry)

        # Drop from missing list once we have a non-empty value.
        if value not in (None, "", []):
            self.missing_required = [
                m for m in self.missing_required if m != name
            ]
        self.updated_at = time.time()

    def clear_field(self, name: str) -> None:
        self.filled = [f for f in self.filled if f.get("name") != name]
        # If it's required, it goes back to missing.
        q = self.question_for(name)
        if q and q.get("required") and name not in self.missing_required:
            self.missing_required.append(name)
        self.updated_at = time.time()

    def all_required_filled(self) -> bool:
        return not self.missing_required

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Session":
        data = dict(d)
        state_val = data.pop("state", State.IDLE.value)
        sess = cls(user_address=data.pop("user_address"))
        sess.state = State(state_val)
        for key, value in data.items():
            if hasattr(sess, key):
                setattr(sess, key, value)
        return sess


# ---------------------------------------------------------------------------
# ctx.storage helpers — kept here so the storage key shape stays consistent.
# ---------------------------------------------------------------------------


def storage_key(user_address: str) -> str:
    return f"{SESSION_KEY_PREFIX}{user_address}"


def load(storage, user_address: str) -> Session:
    """Return the existing session for `user_address`, or a fresh IDLE one."""
    raw = storage.get(storage_key(user_address))
    if not raw:
        return Session(user_address=user_address)
    if isinstance(raw, str):
        # ctx.storage round-trips through JSON for some backends.
        import json

        try:
            raw = json.loads(raw)
        except Exception:  # noqa: BLE001
            return Session(user_address=user_address)
    try:
        return Session.from_dict(raw)
    except Exception:  # noqa: BLE001
        return Session(user_address=user_address)


def save(storage, sess: Session) -> None:
    sess.updated_at = time.time()
    storage.set(storage_key(sess.user_address), sess.to_dict())


def clear(storage, user_address: str) -> None:
    try:
        storage.remove(storage_key(user_address))
    except Exception:  # noqa: BLE001
        # Some storage backends use a different API; try set-to-None as fallback.
        try:
            storage.set(storage_key(user_address), None)
        except Exception:  # noqa: BLE001
            pass
