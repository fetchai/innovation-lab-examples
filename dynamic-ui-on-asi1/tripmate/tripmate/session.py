"""Per-user session state management (uAgents KeyValueStore)."""

from __future__ import annotations

from typing import Any


class SessionStore:
    """Wraps ctx.storage with per-sender session keys."""

    def __init__(self, storage, sender: str):
        self._storage = storage
        self._sender = sender
        self._key = f"session:{sender}"
        self._data: dict[str, Any] = storage.get(self._key) or {}

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, **kwargs) -> None:
        self._data.update(kwargs)

    def save(self) -> None:
        self._storage.set(self._key, self._data)

    def clear(self) -> None:
        self._data = {}
        self._storage.set(self._key, {})

    def remember_search(
        self, tool: str, args: dict, raw_result: str, index: dict
    ) -> None:
        from tripmate.utils import parse_mcp_json

        data = parse_mcp_json(raw_result) or {}
        self._data["last_search"] = {
            "tool": tool,
            "args": args,
            "search_id": str(data.get("search_id") or ""),
        }
        self._data["last_results"] = raw_result
        self._data["results_index"] = index
        self.save()

    def lookup_item(self, item_id: str) -> dict:
        return self._data.get("results_index", {}).get(item_id, {})

    def add_history(self, role: str, content: str) -> None:
        history = self._data.get("history", [])
        history.append({"role": role, "content": content})
        self._data["history"] = history[-12:]
        self.save()

    def get_history(self) -> list[dict]:
        return self._data.get("history", [])
