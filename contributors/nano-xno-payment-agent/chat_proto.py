"""Chat protocol that requests Nano (XNO) payment before processing a job."""

from datetime import datetime, timezone

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from payment import request_payment_from_user

chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    ctx.logger.info(f"Got a message from {sender}: {msg.content}")
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
        ),
    )

    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info(
                f"[nano] Requesting XNO payment to process job: {item.text.strip()[:60]}"
            )
            await request_payment_from_user(
                ctx,
                sender,
                description="Pay in Nano (XNO) to process this job.",
            )
            return


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )
