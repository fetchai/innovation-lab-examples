"""
CardioAgent: a live cardiovascular fitness test agent on Agentverse + ASI:One.

The agent guides users through a 3-minute test using live heart rate readings
that a companion `bridge_agent.py` POSTs to a local REST endpoint. (Agentverse
mailbox routing is too slow for 1Hz streaming, so the same-machine bridge uses
a direct localhost POST; the mailbox is used only for the ASI:One chat.)

Run:
    python agent.py

Then, on the same machine, run the bridge agent (which talks to the Garmin
watch over BLE and POSTs readings to this agent):

    python bridge_agent.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load env vars BEFORE importing modules that read them at import time.
load_dotenv()

from uagents import Agent, Context  # noqa: E402

from chat_handler import chat_proto  # noqa: E402
from models import HRAck, HRReading  # noqa: E402
import session_state  # noqa: E402


AGENT_SEED = os.environ.get("AGENT_SEED", "cardio-agent-default-seed-change-me")


agent = Agent(
    name="cardio-test-agent",
    seed=AGENT_SEED,
    port=8001,
    mailbox=True,
)

agent.include(chat_proto, publish_manifest=True)


# Receive HR readings via a fast local REST endpoint instead of agent-to-agent
# messaging. Agent messaging routes via Agentverse mailbox which is too slow
# for 1Hz streaming data; the bridge runs on the same machine, so direct
# localhost POST is both faster and simpler.
@agent.on_rest_post("/bpm", HRReading, HRAck)
async def receive_bpm(ctx: Context, req: HRReading) -> HRAck:
    """REST endpoint that the local bridge POSTs heart rate readings to."""
    session_state.receive_bpm(req.bpm, req.rr_intervals, req.ts)
    return HRAck(ok=True)


@agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info("CardioAgent online")
    ctx.logger.info(f"Agent address: {agent.address}")
    ctx.logger.info(
        "Copy this address into your bridge_agent .env as CARDIOPULSE_ADDRESS, "
        "then run `python bridge_agent.py` on the machine with the watch."
    )


if __name__ == "__main__":
    agent.run()
