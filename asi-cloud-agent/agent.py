import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

# Get ASI Cloud API key from environment
ASI_CLOUD_API_KEY = os.getenv("ASICLOUD_API_KEY")

if not ASI_CLOUD_API_KEY:
    raise RuntimeError(
        "Missing ASICLOUD API key. Please set ASICLOUD_API_KEY in your environment."
    )

client = OpenAI(
    api_key=ASI_CLOUD_API_KEY,
    base_url=os.getenv(
        "ASICLOUD_BASE_URL", "https://inference.asicloud.cudos.org/v1"
    ),
)

MODEL_NAME = "asi1-mini"
GENERATION_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 512,
}

SYSTEM_PROMPT = """You are an AI assistant powered by the ASI Cloud asi1-mini model.

Behave professionally, stay factual, and keep responses concise.
Ask for clarification when inputs are ambiguous.
Respect user preferences and mention limitations or safety considerations when relevant.
"""

agent = Agent(name="asi_agent",port=8000,mailbox=True)
chat_proto = Protocol(spec=chat_protocol_spec)


def generate_response(history, user_text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for h in history[-5:]:
        messages.append({"role": h["role"], "content": h["text"]})

    messages.append({"role": "user", "content": user_text})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        **GENERATION_CONFIG,
    )
    return response.choices[0].message.content.strip()


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.storage.set("total_messages", 0)
    ctx.storage.set("conversations", {})


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    try:
        user_text = next(
            (item.text for item in msg.content if isinstance(item, TextContent)), ""
        )

        if not user_text:
            ctx.logger.warning("No text content in message")
            return

        ctx.logger.info(f"📨 Message from {sender}: {user_text[:50]}...")

        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )

        conversations = ctx.storage.get("conversations") or {}
        history = conversations.get(sender, [])

        ctx.logger.info("🤔 Generating response with asi1-mini...")
        response_text = generate_response(history, user_text)
        ctx.logger.info(f"✅ Response generated: {response_text[:100]}...")

        history.append({"role": "user", "text": user_text})
        history.append({"role": "assistant", "text": response_text})
        conversations[sender] = history[-10:]
        ctx.storage.set("conversations", conversations)

        total = ctx.storage.get("total_messages") or 0
        ctx.storage.set("total_messages", total + 1)

        await ctx.send(
            sender,
            ChatMessage(content=[TextContent(text=response_text, type="text")]),
        )
        ctx.logger.info(f"💬 Response sent to {sender}")

    except Exception as exc:
        ctx.logger.error(f"❌ Error processing message: {exc}")
        error_msg = (
            "I ran into a problem while generating a reply. Could you try again?"
        )
        await ctx.send(
            sender, ChatMessage(content=[TextContent(text=error_msg, type="text")])
        )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"✓ Message {msg.acknowledged_msg_id} acknowledged by {sender}")


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()

