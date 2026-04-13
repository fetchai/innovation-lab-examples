"""
Parts-Sourcing Worker Agent — run in its own terminal.

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
  Set PARTS_AGENT_HOST when running in Docker so the endpoint hostname
  matches the container name (e.g. "parts-agent") instead of "127.0.0.1".
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

from app.services.brightdata.part_price_service import fetch_parts_deterministic
from app.uagents_protocol.schemas import (
    PartSource,
    PartsSourcingRequest,
    PartsSourcingResponse,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("parts-agent")

# ── Agent ─────────────────────────────────────────────────────────────────────

PORT = int(os.getenv("PARTS_AGENT_PORT", "8002"))
SEED = os.getenv("PARTS_AGENT_SEED", "parts sourcing worker agent seed phrase one")
HOST = os.getenv("PARTS_AGENT_HOST", "127.0.0.1")

# Workers always use a direct HTTP endpoint — no mailbox.
# The orchestrator resolves this address from the Almanac and POSTs aiohttp
# directly here.  Only the orchestrator uses Agentverse mailbox (for ASI:One).
parts_agent = Agent(
    name="parts-sourcing-agent",
    seed=SEED,
    port=PORT,
    endpoint=[f"http://{HOST}:{PORT}/submit"],
    registration_policy=AlmanacApiRegistrationPolicy(),
)

# ── Protocol ──────────────────────────────────────────────────────────────────

parts_protocol = Protocol(name="PartsSourcingProtocol", version="0.3.0")


@parts_protocol.on_message(model=PartsSourcingRequest, replies=PartsSourcingResponse)
async def handle_parts_request(ctx: Context, sender: str, msg: PartsSourcingRequest):
    resp = await _do_parts_lookup(msg)
    await ctx.send(sender, resp)
    log.info("[parts] Response sent back to orchestrator")


parts_agent.include(parts_protocol, publish_manifest=False)

# ── REST endpoint (used by orchestrator for reliable direct HTTP calls) ───────


async def _do_parts_lookup(msg: PartsSourcingRequest) -> PartsSourcingResponse:
    """Shared logic for both protocol handler and REST endpoint."""
    log.info(
        "[parts] Request received: part=%s (%s) brand=%s model=%s",
        msg.part_name,
        msg.part_number,
        msg.brand or "?",
        msg.model_number or "?",
    )
    try:
        d = await fetch_parts_deterministic(
            msg.part_name,
            msg.part_number,
            msg.context_text,
            brand=msg.brand,
            model_number=msg.model_number,
            appliance_type=msg.appliance_type,
        )
        excel_path = str(d.get("excel_path") or "")
        raw_sources: list[dict] = d.get("all_sources", [])  # type: ignore[assignment]
        all_sources = [
            PartSource(
                source_site=str(s.get("source_site") or ""),
                price_usd=float(s.get("price_usd") or 0),
                purchase_url=str(s.get("purchase_url") or ""),
                stock_status=str(s.get("stock_status") or ""),
                match_type=str(s.get("match_type") or "exact"),
                suggestion=str(s.get("suggestion") or ""),
            )
            for s in raw_sources
        ]
        resp = PartsSourcingResponse(
            price_usd=float(d.get("price_usd") or 0),  # type: ignore[arg-type]
            purchase_url=str(d.get("purchase_url") or ""),
            stock_status=str(d.get("stock_status") or ""),
            source_site=str(d.get("source_site") or ""),
            all_sources=all_sources,
            excel_path=excel_path,
            session_id=msg.session_id,
        )
        log.info(
            "[parts] Done — $%.2f at %s (%d sources)",
            d["price_usd"],
            d["source_site"],
            len(all_sources),
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[parts] Service error — sending empty response: %s", exc)
        resp = PartsSourcingResponse(
            price_usd=0.0,
            purchase_url="",
            stock_status="error",
            source_site="error",
            all_sources=[],
            excel_path="",
            session_id=msg.session_id,
        )
    return resp


@parts_agent.on_rest_post(
    "/diagnose-parts", PartsSourcingRequest, PartsSourcingResponse
)
async def handle_rest_parts(
    ctx: Context, req: PartsSourcingRequest
) -> PartsSourcingResponse:
    return await _do_parts_lookup(req)


# ── Entry point ───────────────────────────────────────────────────────────────


@parts_agent.on_event("startup")
async def startup(ctx: Context):
    log.info("Parts-Sourcing Agent ready")
    log.info("  Address      : %s", ctx.agent.address)
    log.info("  Endpoint     : http://%s:%d/submit", HOST, PORT)
    log.info("  REST (orch)  : POST http://%s:%d/diagnose-parts", HOST, PORT)
    log.info("  Mode         : direct HTTP (orchestrator POSTs here directly)")


if __name__ == "__main__":
    log.info("Starting parts-sourcing-agent on port %d ...", PORT)
    parts_agent.run()
