"""lastminute.com MCP client via npx mcp-remote."""

import json
import subprocess
import threading
import time

from tripmate.config import MCP_ARGS, MCP_COMMAND, MCP_RPC_TIMEOUT, MCP_STARTUP_TIMEOUT


class LastMinuteMCP:
    def __init__(self, command: str = MCP_COMMAND, args: list | None = None):
        self._command = command
        self._args = args or MCP_ARGS
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._req_id = 0
        self._tool_names: set[str] = set()
        self._ready = False

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _drain_stderr(self) -> None:
        if not self._proc or not self._proc.stderr:
            return
        for line in self._proc.stderr:
            if "Connected to remote server" in line:
                break

    def _start_unlocked(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = subprocess.Popen(
            [self._command, *self._args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        deadline = time.time() + MCP_STARTUP_TIMEOUT
        while time.time() < deadline:
            if self._proc.poll() is not None:
                err = (self._proc.stderr.read() if self._proc.stderr else "")[:500]
                raise RuntimeError(f"mcp-remote exited early: {err or 'unknown error'}")
            time.sleep(0.3)
        self._rpc_unlocked(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "TripMate", "version": "1.0"},
            },
        )
        self._notify_unlocked("notifications/initialized", {})
        tools = self._rpc_unlocked("tools/list", {})
        self._tool_names = {t["name"] for t in tools.get("tools", [])}
        self._ready = True

    def _ensure_session_unlocked(self) -> None:
        if self._ready and self._proc and self._proc.poll() is None:
            return
        self._ready = False
        self._start_unlocked()

    def _read_response(self, req_id: int) -> dict:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("mcp-remote not running")
        deadline = time.time() + MCP_RPC_TIMEOUT
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError("mcp-remote process exited unexpectedly")
            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == req_id:
                if "error" in msg:
                    err = msg["error"]
                    raise RuntimeError(err.get("message", str(err)))
                return msg.get("result", msg)
        raise RuntimeError("mcp-remote timeout waiting for response")

    def _send_unlocked(self, body: dict, expect_response: bool = True) -> dict | None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("mcp-remote stdin unavailable")
        self._proc.stdin.write(json.dumps(body) + "\n")
        self._proc.stdin.flush()
        if expect_response and "id" in body:
            return self._read_response(body["id"])
        return None

    def _rpc_unlocked(self, method: str, params: dict | None = None) -> dict:
        body: dict = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            body["params"] = params
        return self._send_unlocked(body) or {}

    def _notify_unlocked(self, method: str, params: dict | None = None) -> None:
        body: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        self._send_unlocked(body, expect_response=False)

    def call_tool(self, name: str, arguments: dict) -> str:
        with self._lock:
            self._ensure_session_unlocked()
            tool_name = name
            aliases = {
                "search_packages": ["search_flight_and_hotel_package"],
                "search_flight_and_hotel_package": ["search_flight_and_hotel_package"],
                "search_hotels": ["search_only_hotel"],
                "search_only_hotel": ["search_only_hotel"],
                "search_flights": ["search_flights"],
                "select_hotel_options": ["select_hotel_options"],
                "generate_booking_link": ["generate_booking_link"],
            }
            if tool_name not in self._tool_names:
                for candidate in aliases.get(name, [name]):
                    if candidate in self._tool_names:
                        tool_name = candidate
                        break
            result = self._rpc_unlocked(
                "tools/call", {"name": tool_name, "arguments": arguments}
            )
        content = result.get("content", [])
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(parts) if parts else json.dumps(result)


mcp_client = LastMinuteMCP()
