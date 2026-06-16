from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)
from google import genai
from dotenv import load_dotenv

import os
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY environment variable is required")
load_dotenv()

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
        timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)

    # Extract the text content from the ChatMessage
    for item in msg.content:
        if isinstance(item, TextContent):
            user_query = item.text
            ctx.logger.info(
                f"Received research request from {sender[-8:]} for topic: '{user_query}'"
            )

            try:
                # Prompt Engineering for the Agent
                system_instruction = (
                    "You are a concise, highly factual research assistant."
                )
                prompt = f"{system_instruction}\n\nProvide a structured summary about: {user_query}"

                # Call the Gemini API
                response = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )

                # Package the AI-generated response into a ChatMessage
                response_msg = ChatMessage(
                    timestamp=datetime.utcnow(),
                    msg_id=uuid4(),
                    content=[TextContent(type="text", text=response.text)],
                )

                await ctx.send(sender, response_msg)
                ctx.logger.info(
                    "Successfully generated and returned the research summary."
                )

except (genai.APIError, genai.ClientError, genai.QuotaExceededError) as e:
    ctx.logger.error(f"Gemini API Error: {e}")
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
except Exception as e:
    ctx.logger.error(f"Unexpected error: {e}")
    error_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(
                type="text",
                text=f"Agent Error: Unexpected failure. {str(e)}",
            )
        ],
    )
    await ctx.send(sender, error_msg)
            # to handle failure modes appropriately.
            except Exception as e:
                ctx.logger.error(f"Gemini API Error: {e}")

                # Package the error into a ChatMessage
                error_msg = ChatMessage(
                    timestamp=datetime.utcnow(),
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