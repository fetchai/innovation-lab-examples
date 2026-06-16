import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from google import genai
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

# Load environment variables
load_dotenv()

# Validate API Key
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY environment variable is required")

# --- 1. Initialize the Agent ---
research_agent = Agent(
    name="gemini_researcher",
    port=8000,
    seed="gemini_researcher_secret_seed",
    endpoint=["http://127.0.0.1:8000/submit"],
)

# Initialize the chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# Initialize the Gemini Client
gemini_client = genai.Client()


# --- 2. Define the Message Handlers ---
@chat_proto.on_message(ChatMessage)
async def handle_research_request(ctx: Context, sender: str, msg: ChatMessage):
    # Send an immediate acknowledgment that the message was received
    ack = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)

    # Safely extract the text content
    user_query = None
    for item in msg.content:
        if isinstance(item, TextContent):
            user_query = item.text
            break

    if not user_query:
        ctx.logger.warning("Received ChatMessage with no text content")
        return

    ctx.logger.info(
        f"Received research request from {sender[-8:]} for topic: '{user_query}'"
    )

    try:
        # Prompt Engineering for the Agent
        system_instruction = "You are a concise, highly factual research assistant."
        prompt = (
            f"{system_instruction}\n\nProvide a structured summary about: {user_query}"
        )

        # Call the Gemini API
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        # Package the AI-generated response into a ChatMessage
        response_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response.text)],
        )

        await ctx.send(sender, response_msg)
        ctx.logger.info("Successfully generated and returned the research summary.")

    except Exception as e:
        # Check if it's a known Gemini API Error based on class name
        error_type = type(e).__name__
        if error_type in ["APIError", "ClientError", "QuotaExceededError"]:
            ctx.logger.error(f"Gemini API Error: {e}")
        else:
            ctx.logger.error(f"Unexpected error: {e}")

        # Package the error into a ChatMessage
        error_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(
                    type="text",
                    text=f"Agent Error: Could not process request. {str(e)}",
                )
            ],
        )
        await ctx.send(sender, error_msg)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(
        f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}"
    )


# Include the protocol in your agent
research_agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    research_agent.run()
