"""
Shared utilities to avoid circular imports between chat_proto and payment_proto.
"""

from datetime import datetime, timezone
from uuid import uuid4
from uagents_core.contrib.protocols.chat import (
    AgentContent,
    ChatMessage,
    TextContent,
)


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    """Create a text chat message."""
    content: list[AgentContent] = [TextContent(type="text", text=text)]
    if end_session:
        from uagents_core.contrib.protocols.chat import EndSessionContent
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )

