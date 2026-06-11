"""Layer 1 - persistent structured profile storage.

Two backends with the same Protocol so the rest of the codebase (field mapper,
seeding scripts, tests) is agnostic:

* `ContextStore`  - wraps a uAgents `ctx.storage` instance. Used in the running
                    agent. Persists via the uAgents runtime to its own JSON
                    file under the agent's data dir.
* `FileStore`     - wraps a plain JSON file. Used by CLI helpers and tests.
                    Same on-disk format as `ContextStore` writes through.

Both expose `get(user_key) -> UserProfile | None` and `set(user_key, profile)`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Protocol

from models import UserProfile

PROFILE_KEY_PREFIX = "profile:"


def _key(user_key: str) -> str:
    return f"{PROFILE_KEY_PREFIX}{user_key}"


class ProfileStore(Protocol):
    def get(self, user_key: str) -> Optional[UserProfile]: ...

    def set(self, user_key: str, profile: UserProfile) -> None: ...

    def delete(self, user_key: str) -> bool: ...

    def list_users(self) -> list[str]: ...


class ContextStore:
    """uAgents `ctx.storage`-backed profile store. Used inside agent handlers."""

    def __init__(self, storage):
        self._s = storage

    def get(self, user_key: str) -> Optional[UserProfile]:
        raw = self._s.get(_key(user_key))
        if raw is None:
            return None
        # ctx.storage stores arbitrary JSON; round-trip through string for safety.
        if isinstance(raw, str):
            return UserProfile.model_validate_json(raw)
        return UserProfile.model_validate(raw)

    def set(self, user_key: str, profile: UserProfile) -> None:
        profile.touch()
        # Store as plain dict so uagents' storage can re-serialize cleanly.
        self._s.set(_key(user_key), profile.model_dump(mode="json"))

    def delete(self, user_key: str) -> bool:
        # uagents storage doesn't expose delete; overwrite with None as a tombstone.
        if self._s.get(_key(user_key)) is None:
            return False
        self._s.set(_key(user_key), None)
        return True

    def list_users(self) -> list[str]:
        # uagents storage isn't enumerable from a stable public API; callers that
        # need this should use FileStore instead. Return empty as a safe default.
        return []


class FileStore:
    """Plain JSON-file profile store. Useful for seeding/tests."""

    def __init__(self, path: str | os.PathLike):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("{}")

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text() or "{}")
        except json.JSONDecodeError:
            return {}

    def _save(self, data: dict) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._path)

    def get(self, user_key: str) -> Optional[UserProfile]:
        data = self._load()
        raw = data.get(user_key)
        if raw is None:
            return None
        return UserProfile.model_validate(raw)

    def set(self, user_key: str, profile: UserProfile) -> None:
        profile.touch()
        data = self._load()
        data[user_key] = profile.model_dump(mode="json")
        self._save(data)

    def delete(self, user_key: str) -> bool:
        data = self._load()
        if user_key not in data:
            return False
        del data[user_key]
        self._save(data)
        return True

    def list_users(self) -> list[str]:
        return list(self._load().keys())
