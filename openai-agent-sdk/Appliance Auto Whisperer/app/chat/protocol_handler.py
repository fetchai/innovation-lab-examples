from __future__ import annotations

from typing import Any

from app.chat.final_response_builder import build_chat_response
from app.chat.request_parser import parse_chat_payload
from app.orchestration.coordinator import Coordinator


class ProtocolHandler:
    def __init__(self) -> None:
        self._coord = Coordinator()

    async def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = parse_chat_payload(payload)
        syn, structured, session_id = await self._coord.run(req)
        resp = build_chat_response(session_id, syn, structured)
        return {
            "session_id": resp.session_id,
            "markdown": resp.markdown,
            "structured": resp.structured,
        }
