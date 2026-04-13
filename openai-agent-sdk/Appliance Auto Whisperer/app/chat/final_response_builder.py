from __future__ import annotations

from typing import Any

from app.chat.markdown_formatter import synthesis_to_markdown
from app.models.messages import ChatResponse
from app.models.synthesis import SynthesisResult


def build_chat_response(
    session_id: str, syn: SynthesisResult, structured: dict[str, Any]
) -> ChatResponse:
    md = synthesis_to_markdown(syn, structured)
    return ChatResponse(session_id=session_id, markdown=md, structured=structured)
