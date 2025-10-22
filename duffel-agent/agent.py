# agent.py
from __future__ import annotations

import os
import sys
from pathlib import Path

import dotenv
from uagents import Agent, Context

# Ensure project root on sys.path so local packages can be imported
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load environment variables (.env in CWD, project root, parent)
dotenv.load_dotenv()
try:
    dotenv.load_dotenv(ROOT / ".env")
    dotenv.load_dotenv(ROOT.parent / ".env")
except Exception:
    pass

# Protocols
from protocols.chat_proto import chat_proto
from protocols.payment_proto import payment_proto, set_agent_wallet

# Optional: Skyfire helper (for logging / sanity check)
from tools.skyfire import get_skyfire_service_id

# Config
AGENT_NAME = os.getenv("AGENT_NAME", "DuffelFlightsAgent")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8030"))
AGENTVERSE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai")
AGENT_SEED = os.getenv("AGENT_SEED", "Duffel_agent_flights_seed_live_Innovation_Lab")

# Create the agent instance
agent = Agent(
    name=AGENT_NAME,
    port=AGENT_PORT,
    mailbox=True,
    agentverse=AGENTVERSE_URL,
    seed=AGENT_SEED,
)

# Supply wallet to payment protocol for verification
set_agent_wallet(agent.wallet)

@agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"{AGENT_NAME} is up. Wallet address: {agent.wallet.address()}")
    ssi = get_skyfire_service_id()
    if ssi:
        ctx.logger.info(f"Detected Skyfire service ID: {ssi}")
    else:
        ctx.logger.info("No Skyfire service ID configured (SELLER_SERVICE_ID missing).")

# Include protocols and publish their manifests
agent.include(chat_proto, publish_manifest=True)
agent.include(payment_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()