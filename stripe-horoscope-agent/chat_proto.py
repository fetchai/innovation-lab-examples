from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

ChatHandler = Callable[[Context, str, ChatMessage], Awaitable[None]]


def build_chat_proto(on_chat: ChatHandler) -> Protocol:
    proto = Protocol(spec=chat_protocol_spec)

    @proto.on_message(ChatMessage)
    async def _on_chat(ctx: Context, sender: str, msg: ChatMessage):
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )
        await on_chat(ctx, sender, msg)

    @proto.on_message(ChatAcknowledgement)
    async def _on_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        # Handler required to satisfy chat protocol verification.
        return

    return proto

