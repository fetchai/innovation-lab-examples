import asyncio
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    chat_protocol_spec,
)

# --- THE FIX: Manually jumpstart the asyncio event loop for Python 3.12+ ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# --- 1. Initialize the User Agent ---
user_agent = Agent(
    name="user_client",
    port=8001,
    seed="user_client_secret_seed",
    endpoint=["http://127.0.0.1:8001/submit"],
)

# Initialize the chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

# YOUR TARGET ADDRESS
TARGET_AGENT_ADDRESS = (
    "agent1qtjys8khgg88v6gvjudrlxdp7njxn9utettjclyj68pfevm7df9e6nsseng"
)

# --- 2. Define the Triggers and Handlers ---
@user_agent.on_event("startup")
async def send_research_request(ctx: Context):
    topic = "The architecture of transformer-based Large Language Models"
    ctx.logger.info(f"Sending research request for: {topic}")

    # Package the prompt into a TextContent object inside a ChatMessage
    research_message = ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=topic)]
    )
    
    # Send the request to the Gemini Agent
    await ctx.send(TARGET_AGENT_ADDRESS, research_message)

@chat_proto.on_message(ChatMessage)
async def handle_response(ctx: Context, sender: str, msg: ChatMessage):
    # Extract the summary text from the incoming ChatMessage
    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info("\n=== Received Research Summary ===")
            ctx.logger.info(item.text)
            ctx.logger.info("=================================\n")
            
    # Send an acknowledgment back to the Gemini agent
    ack = ChatAcknowledgement(
        timestamp=datetime.utcnow(),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)

@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender} for message: {msg.acknowledged_msg_id}")

# Include the protocol in your agent
user_agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    user_agent.run()