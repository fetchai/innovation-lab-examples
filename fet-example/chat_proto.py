from datetime import datetime, timezone
from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from payment import (
    request_payment_from_user,
    generate_image_after_payment,
)
from shared import create_text_chat


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
    
    # Process text content for payment gating and prompt collection
    
    for item in msg.content:
        if isinstance(item, TextContent):
            text = item.text.strip()
            session_id = str(ctx.session)
            awaiting_key = f"{sender}:{session_id}:awaiting_prompt"
            verified_key = f"{sender}:{session_id}:verified_payment"

            # If we are awaiting a prompt after a verified payment, consume exactly one prompt
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

            # Always request payment (no free images for anyone)
            ctx.logger.info(f"Requesting payment from {sender} for image generation")
            payment_description = "Please complete the payment to generate this image."
            # Persist prompt so we don't ask again after payment
            ctx.storage.set(f"prompt:{sender}:{session_id}", text)
            ctx.storage.set("current_prompt", text)
            # Clear any previous recorded marker for this session (new payment request)
            ctx.storage.remove(f"{sender}:{session_id}:request_recorded")
            # Attach the explanation as the description/metadata of the payment request
            await request_payment_from_user(ctx, sender, description=payment_description)
            return


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Got an acknowledgement from {sender} for {msg.acknowledged_msg_id}"
    )
