import asyncio

try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from uagents import Agent, Context, Bureau
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
from uuid import uuid4
from datetime import datetime, timezone

# Import the pharmacy agent we just built
from agent import agent as pharmacy_agent

# Create a mock user agent
user = Agent(name="user", seed="mock_user_seed_123")


@user.on_event("startup")
async def on_startup(ctx: Context):
    query = "Find me a pharmacy near London"
    ctx.logger.info(f"User asking: '{query}'")

    # Send message to pharmacy agent
    await ctx.send(
        pharmacy_agent.address,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=query)],
        ),
    )


@user.on_message(ChatMessage)
async def handle_reply(ctx: Context, sender: str, msg: ChatMessage):
    # Print the reply from the pharmacy agent
    for item in msg.content:
        if isinstance(item, TextContent):
            print("\n" + "=" * 50)
            print("🏥 REPLY FROM PHARMACY AGENT:")
            print("=" * 50)
            print(item.text)
            print("=" * 50 + "\n")


# Run both agents together in a Bureau
bureau = Bureau()
bureau.add(pharmacy_agent)
bureau.add(user)

if __name__ == "__main__":
    print("Starting local test...")
    bureau.run()
