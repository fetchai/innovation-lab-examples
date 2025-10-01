from datetime import datetime, timezone
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    AgentContent,
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content: list[AgentContent] = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


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

    from payment_proto import request_payment_from_user, generate_image_after_payment

    for item in msg.content:
        if isinstance(item, TextContent):
            text = item.text.strip()
            session_id = str(ctx.session)
            awaiting_key = f"{sender}:{session_id}:awaiting_prompt"
            verified_key = f"{sender}:{session_id}:verified_payment"

            if (ctx.storage.has(awaiting_key) or ctx.storage.get(awaiting_key)) and (
                ctx.storage.has(verified_key) or ctx.storage.get(verified_key)
            ):
                ctx.logger.info("Consuming prompt post-payment and generating one image")
                ctx.storage.remove(awaiting_key)
                ctx.storage.remove(verified_key)
                ctx.storage.set(f"prompt:{sender}:{session_id}", text)
                ctx.storage.set("requesting_user", sender)
                await generate_image_after_payment(ctx, sender)
                return

            if text.lower().startswith(("hello", "hi", "hey")) and len(text) < 20:
                await ctx.send(sender, create_text_chat("Hello! Please complete a small payment first, then I'll ask for your image prompt."))
                await request_payment_from_user(ctx, sender)
                return

            await ctx.send(sender, create_text_chat("Please complete the payment first. After that, I'll ask for your prompt and generate one image."))
            await request_payment_from_user(ctx, sender)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )


