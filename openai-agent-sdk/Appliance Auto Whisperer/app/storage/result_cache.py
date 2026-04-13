from __future__ import annotations

import time
from typing import Any

from app.config.constants import RESULT_CACHE_TTL_SECONDS


class ResultCache:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._entries.get(key)
        if not item:
            return None
        ts, val = item
        if time.time() - ts > RESULT_CACHE_TTL_SECONDS:
            del self._entries[key]
            return None
        return val

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = (time.time(), value)
