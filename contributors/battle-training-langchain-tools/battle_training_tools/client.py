"""Minimal Streamable-HTTP MCP client for the public battle.training server.

The server at https://api.battle.training/mcp speaks MCP over Streamable
HTTP: one JSON-RPC request per POST, answered either as plain JSON or as a
``text/event-stream`` with ``data:`` lines. It is session-less in practice
(no ``Mcp-Session-Id`` is issued), so this client performs the ``initialize``
handshake lazily on first use and then issues ``tools/call`` requests.

Only the Python standard library plus ``httpx`` are used. The transport is
injectable so tests can run fully offline against a stub.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

DEFAULT_ENDPOINT = "https://api.battle.training/mcp"
PROTOCOL_VERSION = "2025-03-26"

# A transport takes (method, params) and returns the JSON-RPC ``result``.
Transport = Callable[[str, dict], Any]


class McpError(RuntimeError):
    """Raised when the MCP server returns a JSON-RPC error or bad output."""


def flatten_result(result: Any) -> str:
    """Flatten an MCP ``tools/call`` result into a single string.

    Text content blocks are joined with newlines. A block whose text parses
    as JSON is re-serialised compactly so downstream agents see the data,
    not the MCP envelope. Non-text blocks are noted, never executed.
    """
    if not isinstance(result, dict):
        return str(result)
    blocks = result.get("content")
    if not isinstance(blocks, list):
        return json.dumps(result, separators=(",", ":"), default=str)
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = str(block.get("text", ""))
            try:
                parsed = json.loads(text)
            except (ValueError, TypeError):
                parts.append(text)
            else:
                parts.append(json.dumps(parsed, separators=(",", ":"), default=str))
        else:
            parts.append(f"[{btype} content omitted]")
    if result.get("isError"):
        return "ERROR: " + "\n".join(parts)
    return "\n".join(parts)


class BattleTrainingClient:
    """Client for the battle.training MCP server.

    ``key`` is *your own* battle.training account key. It is sent only as an
    ``Authorization: Bearer`` header on the MCP connection (the documented
    alternative to passing ``key`` per tool call) and is never placed inside
    tool arguments. Read-only tools work without a key; account tools
    (``create_bot``, ``upload_version``, ...) require one.
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        key: Optional[str] = None,
        transport: Optional[Transport] = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self._key = key
        self._transport = transport
        self._timeout = timeout
        self._initialised = False
        self._request_id = 0

    @property
    def has_key(self) -> bool:
        return bool(self._key)

    # -- public API ------------------------------------------------------

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call one MCP tool and return its flattened text result."""
        if self._transport is not None:
            result = self._transport(
                "tools/call", {"name": name, "arguments": arguments}
            )
            return flatten_result(result)
        self._ensure_initialised()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return flatten_result(result)

    # -- internals -------------------------------------------------------

    def _ensure_initialised(self) -> None:
        if self._initialised:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "battle-training-langchain-tools",
                    "version": "0.1.0",
                },
            },
        )
        self._notify("notifications/initialized", {})
        self._initialised = True

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        return headers

    def _http_client(self):
        """httpx client honouring HTTPS_PROXY explicitly.

        ``trust_env=False`` plus an explicit proxy keeps behaviour identical
        across environments (some sandboxes export NO_PROXY values that
        httpx's pattern parser rejects). The proxy URL may embed
        credentials; it is used as configuration only, never logged.
        """
        import os

        import httpx

        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
        return httpx.Client(timeout=self._timeout, proxy=proxy, trust_env=False)

    def _rpc(self, method: str, params: dict) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        with self._http_client() as http:
            response = http.post(self.endpoint, json=payload, headers=self._headers())
            response.raise_for_status()
            message = _parse_rpc_body(
                response.text, response.headers.get("content-type", "")
            )
        if "error" in message:
            err = message["error"] or {}
            raise McpError(f"{method}: {err.get('message', 'unknown MCP error')}")
        return message.get("result")

    def _notify(self, method: str, params: dict) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        with self._http_client() as http:
            http.post(self.endpoint, json=payload, headers=self._headers())


def _parse_rpc_body(text: str, content_type: str) -> dict:
    """Parse a JSON or Server-Sent-Events JSON-RPC response body."""
    if "text/event-stream" in content_type:
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:") :].strip())
        raise McpError("event-stream response contained no data line")
    return json.loads(text)
