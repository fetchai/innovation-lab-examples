# agent.py - ASI1 Image Generation Agent with Skyfire Payment
import os
import dotenv
from uagents import Agent, Context

# Load .env BEFORE importing modules that read env at import time
dotenv.load_dotenv()

from chat_proto import chat_proto
from payment_proto import payment_proto, set_agent_wallet


agent = Agent(
    name="ASI1ImageAgent",
    port=8021,
    mailbox=True,
    agentverse=os.getenv("AGENTVERSE_URL", "https://agentverse.ai"),
)

# Set the agent wallet for payment operations
set_agent_wallet(agent.wallet)

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"ASI1 Image Agent started: {agent.wallet.address()}")

    skyfire_configured = bool(
        (os.getenv("SKYFIRE_API_KEY") or os.getenv("SELLER_SKYFIRE_API_KEY"))
        and (os.getenv("SKYFIRE_SERVICE_ID") or os.getenv("SELLER_SERVICE_ID"))
        and (os.getenv("SELLER_ACCOUNT_ID") or os.getenv("JWT_AUDIENCE") or os.getenv("SKYFIRE_ACCOUNT_ID"))
    )

    ctx.logger.info("=== ASI1 Image Generation Agent ===")
    ctx.logger.info("💰 Accepted Payments:")
    if skyfire_configured:
        ctx.logger.info("   • $0.001 USDC (via Skyfire)")
    else:
        ctx.logger.info("   • Skyfire USDC: Not configured (set SKYFIRE_API_KEY and SKYFIRE_SERVICE_ID)")
    ctx.logger.info("🎨 Ready to generate images with ASI1!")


# Include protocols
agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()


