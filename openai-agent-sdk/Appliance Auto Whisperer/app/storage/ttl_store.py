from __future__ import annotations

import time
from typing import Any


class TTLStore:
    def __init__(self, default_ttl_s: float) -> None:
        self._default_ttl_s = default_ttl_s
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if not item:
            return None
        exp, val = item
        if time.time() > exp:
            del self._data[key]
            return None
        return val

    def set(self, key: str, value: Any, ttl_s: float | None = None) -> None:
        ttl = ttl_s if ttl_s is not None else self._default_ttl_s
        self._data[key] = (time.time() + ttl, value)
