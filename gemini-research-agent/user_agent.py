import asyncio
from uagents import Agent, Context, Model

# --- THE FIX: Manually jumpstart the asyncio event loop for Python 3.12+ ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


# --- 1. Define the Message Data Models locally ---
class ResearchRequest(Model):
    topic: str


class ResearchResponse(Model):
    summary: str


# --- 2. Initialize the User Agent ---
user_agent = Agent(
    name="user_client",
    port=8001,
    seed="user_client_secret_seed",
    endpoint=["http://127.0.0.1:8001/submit"],
)

# YOUR TARGET ADDRESS
TARGET_AGENT_ADDRESS = (
    "agent1qtjys8khgg88v6gvjudrlxdp7njxn9utettjclyj68pfevm7df9e6nsseng"
)


# --- 3. Define the Triggers and Handlers ---
@user_agent.on_event("startup")
async def send_research_request(ctx: Context):
    topic = "The architecture of transformer-based Large Language Models"
    ctx.logger.info(f"Sending research request for: {topic}")

    # Send the request to the Gemini Agent
    await ctx.send(TARGET_AGENT_ADDRESS, ResearchRequest(topic=topic))


@user_agent.on_message(model=ResearchResponse)
async def handle_response(ctx: Context, sender: str, msg: ResearchResponse):
    ctx.logger.info("\n=== Received Research Summary ===")
    ctx.logger.info(msg.summary)
    ctx.logger.info("=================================\n")


if __name__ == "__main__":
    user_agent.run()
