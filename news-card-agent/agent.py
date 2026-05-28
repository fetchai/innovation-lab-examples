"""News-card agent entrypoint (no payment protocol)."""

import os

from dotenv import load_dotenv
from uagents import Agent, Context

load_dotenv()

from chat_proto import chat_proto  # noqa: E402  (load env before importing)
from news_client import active_backend  # noqa: E402


agent = Agent(
    name=os.getenv("AGENT_NAME", "News Card Agent"),
    seed=os.getenv("AGENT_SEED_PHRASE", "news-card-agent-seed"),
    port=int(os.getenv("AGENT_PORT", "8000")),
    mailbox=True,
)

agent.include(chat_proto, publish_manifest=True)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Agent started: {agent.address}")
    ctx.logger.info("=== News Card Agent ===")
    ctx.logger.info(f"News backend: {active_backend()}")
    ctx.logger.info(
        "ASI1 LLM: "
        + (
            "enabled"
            if (os.getenv("ASI_ONE_API_KEY") or os.getenv("ASI1_API_KEY"))
            else "disabled (fallback summaries)"
        )
    )
    ctx.logger.info("Chat with the agent to receive a news card.")


if __name__ == "__main__":
    agent.run()
