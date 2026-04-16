"""
Main entry point for the Fetch Orchestrator Agent.

This file is what gets deployed to Agentverse (or run locally for
development).  It wires together:

  • Chat protocol      – ASI:One integration (AgentChatProtocol)
  • Pairing protocol   – device registration
  • Objective protocol  – objective intake → plan → dispatch → result
  • Policy engine       – Fetch-side guardrails
  • Storage             – device records

Usage (local dev):
    python -m orchestrator.agent

For Agentverse deployment the contents of this file are uploaded
via the hosting API.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Shared singletons (imported by protocol handlers)
# ---------------------------------------------------------------------------

from orchestrator.policy import FetchPolicy  # noqa: E402
from orchestrator.storage import PairingStore  # noqa: E402

pairing_store = PairingStore()
fetch_policy = FetchPolicy()

# Orchestrator signing key (optional – loaded from env)
orchestrator_private_key = None

_SEED = os.getenv("ORCHESTRATOR_AGENT_SEED")
_NETWORK = os.getenv("AGENT_NETWORK", "testnet")  # testnet by default

# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

from uagents import Agent  # noqa: E402

_USE_MAILBOX = os.getenv("USE_MAILBOX", "true").lower() in ("1", "true", "yes")

agent = Agent(
    name="openclaw-orchestrator",
    seed=_SEED or "openclaw-orchestrator-dev-seed",
    port=int(os.getenv("ORCHESTRATOR_PORT", "8200")),
    **(
        {
            "mailbox": True,
        }
        if _USE_MAILBOX
        else {
            "endpoint": [
                f"http://127.0.0.1:{os.getenv('ORCHESTRATOR_PORT', '8200')}/submit"
            ],
        }
    ),
    network=_NETWORK,
)

# ---------------------------------------------------------------------------
# Register protocols
# ---------------------------------------------------------------------------

from orchestrator.protocols.chat import chat_proto  # noqa: E402
from orchestrator.protocols.objective import objective_protocol  # noqa: E402
from orchestrator.protocols.pairing import pairing_protocol  # noqa: E402

agent.include(chat_proto, publish_manifest=True)
agent.include(pairing_protocol, publish_manifest=True)
agent.include(objective_protocol, publish_manifest=True)

# ---------------------------------------------------------------------------
# Startup hook
# ---------------------------------------------------------------------------


@agent.on_event("startup")
async def on_startup(ctx):
    ctx.logger.info("Orchestrator agent started")
    ctx.logger.info("Agent address : %s", agent.address)
    ctx.logger.info("Network       : %s", _NETWORK)
    ctx.logger.info(
        "Mailbox       : %s",
        "enabled (Agentverse relay)" if _USE_MAILBOX else "disabled (local endpoint)",
    )
    ctx.logger.info("Protocols     : chat (ASI:One), pairing, objective-intake")
    llm_status = (
        "ASI:One (%s)" % os.getenv("ASI_ONE_MODEL", "asi1")
        if os.getenv("ASI_ONE_API_KEY")
        else "keyword fallback (no ASI_ONE_API_KEY)"
    )
    ctx.logger.info("Planner       : %s", llm_status)


# ---------------------------------------------------------------------------
# CLI entry point (local dev)
# ---------------------------------------------------------------------------


def main():
    logger.info("Starting Fetch Orchestrator Agent (local dev)…")
    agent.run()


if __name__ == "__main__":
    main()
