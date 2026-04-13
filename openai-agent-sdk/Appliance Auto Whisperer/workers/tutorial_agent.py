"""
Tutorial-Search Worker Agent — run in its own terminal.

Quickstart (three terminals):
  Terminal 1:  python workers/parts_agent.py
  Terminal 2:  python workers/tutorial_agent.py
  Terminal 3:  python diagnostic_bureau.py   ← orchestrator

  Or use the launcher:  python run.py

Routing:
  Workers ALWAYS use a direct HTTP submit endpoint (matching pdf-podcast-agent).
  The orchestrator resolves this address from the Almanac and POSTs directly
  via aiohttp — no Agentverse relay needed for worker-to-worker traffic.
  Only the orchestrator uses a mailbox (to receive from ASI:One).
  Set TUTORIAL_AGENT_HOST when running in Docker so the endpoint hostname
  matches the container name (e.g. "tutorial-agent") instead of "127.0.0.1".
"""

import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from uagents import Agent, Context, Protocol
from uagents.registration import AlmanacApiRegistrationPolicy

from app.services.youtube.instructor_service import find_best_tutorial_video
from app.uagents_protocol.schemas import TutorialSearchRequest, TutorialSearchResponse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("tutorial-agent")

# ── Agent ─────────────────────────────────────────────────────────────────────

PORT = int(os.getenv("TUTORIAL_AGENT_PORT", "8003"))
SEED = os.getenv("TUTORIAL_AGENT_SEED", "tutorial youtube worker agent seed two")
HOST = os.getenv("TUTORIAL_AGENT_HOST", "127.0.0.1")

# Workers always use a direct HTTP endpoint — no mailbox.
# The orchestrator resolves this address from the Almanac and POSTs aiohttp
# directly here.  Only the orchestrator uses Agentverse mailbox (for ASI:One).
tutorial_agent = Agent(
    name="tutorial-agent",
    seed=SEED,
    port=PORT,
    endpoint=[f"http://{HOST}:{PORT}/submit"],
    registration_policy=AlmanacApiRegistrationPolicy(),
)

# ── Protocol ──────────────────────────────────────────────────────────────────

instructor_protocol = Protocol(name="TutorialSearchProtocol", version="0.3.0")


async def _do_tutorial_search(msg: TutorialSearchRequest) -> TutorialSearchResponse:
    """Shared logic for both protocol handler and REST endpoint."""
    # Use the pre-built search_query from the orchestrator (which already
    # includes brand + appliance type + part name, no raw part number).
    query = msg.search_query
    log.info(
        "[tutorial] Request received: query=%s (brand=%s, type=%s)",
        query[:80],
        msg.brand or "?",
        msg.appliance_type or "?",
    )
    try:
        vurl, title, dur = await find_best_tutorial_video(query)
        resp = TutorialSearchResponse(
            video_url=vurl,
            video_title=title,
            duration_seconds=dur,
            session_id=msg.session_id,
        )
        log.info("[tutorial] Done — '%s' %s", title, vurl)
    except Exception as exc:  # noqa: BLE001
        log.exception("[tutorial] Service error — sending empty response: %s", exc)
        resp = TutorialSearchResponse(
            video_url="",
            video_title="Tutorial unavailable",
            duration_seconds=0,
            session_id=msg.session_id,
        )
    return resp


@instructor_protocol.on_message(
    model=TutorialSearchRequest, replies=TutorialSearchResponse
)
async def handle_tutorial_request(
    ctx: Context, sender: str, msg: TutorialSearchRequest
):
    resp = await _do_tutorial_search(msg)
    await ctx.send(sender, resp)
    log.info("[tutorial] Response sent back to orchestrator")


tutorial_agent.include(instructor_protocol, publish_manifest=False)

# ── REST endpoint (used by orchestrator for reliable direct HTTP calls) ───────


@tutorial_agent.on_rest_post(
    "/find-tutorial", TutorialSearchRequest, TutorialSearchResponse
)
async def handle_rest_tutorial(
    ctx: Context, req: TutorialSearchRequest
) -> TutorialSearchResponse:
    return await _do_tutorial_search(req)


# ── Entry point ───────────────────────────────────────────────────────────────


@tutorial_agent.on_event("startup")
async def startup(ctx: Context):
    log.info("Tutorial Agent ready")
    log.info("  Address      : %s", ctx.agent.address)
    log.info("  Endpoint     : http://%s:%d/submit", HOST, PORT)
    log.info("  REST (orch)  : POST http://%s:%d/find-tutorial", HOST, PORT)
    log.info("  Mode         : direct HTTP (orchestrator POSTs here directly)")


if __name__ == "__main__":
    log.info("Starting tutorial-agent on port %d ...", PORT)
    tutorial_agent.run()
