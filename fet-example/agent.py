# agent.py - Gemini Imagen Image Generation Agent with Payment Protocol
import os
from dotenv import load_dotenv
from uagents import Agent, Context

load_dotenv()

from chat_proto import chat_proto
from payment import payment_proto, set_agent_wallet

agent = Agent(
    name=os.getenv("AGENT_NAME", "Fet Example Agent"),
    seed=os.getenv("AGENT_SEED_PHRASE", "gemini-imagen-agent"),
    port=int(os.getenv("AGENT_PORT", "8000")),
    mailbox=True,
)

agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)
set_agent_wallet(agent.wallet)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Agent started: {agent.wallet.address()}")
    ctx.logger.info("=== Gemini Imagen Image Generation Agent ===")
    ctx.logger.info("💰 Accepted: 0.1 FET (direct)")
    ctx.logger.info("🎨 Images via Gemini Imagen (GEMINI_API_KEY)")
    ctx.logger.info("📧 Chat to request image generation")


if __name__ == "__main__":
    agent.run()
