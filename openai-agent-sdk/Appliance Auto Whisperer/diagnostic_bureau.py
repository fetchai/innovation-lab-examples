"""
Appliance / Auto Whisperer — Orchestrator Agent

Receives ChatMessage from ASI:One via Agentverse mailbox, runs the full
pipeline (Vision → Parts → Tutorial) and sends a Markdown hero response.

Worker communication (direct REST calls):
  The orchestrator calls worker REST endpoints (/diagnose-parts,
  /find-tutorial) directly via aiohttp POST — both in parallel via
  asyncio.gather().  This avoids a mailbox-poll deadlock: the orchestrator's
  mailbox-poll loop is blocked while handling a message, so envelope-based
  responses queued in Agentverse can never be picked up.  Plain HTTP REST
  calls return the response in the HTTP body immediately.
  If workers are unreachable, the pipeline falls back to calling the
  service functions directly so the agent is always available.

Run order (three separate terminals):
  1. python workers/parts_agent.py
  2. python workers/tutorial_agent.py
  3. python diagnostic_bureau.py   ← this file

  Or use the launcher:  python run.py

Or single-container Docker:
  docker-compose --profile bureau up --build
  (docker-entrypoint.sh starts all 3 processes automatically)
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiohttp
from dotenv import load_dotenv

from uagents import Agent, Context, Protocol
from uagents.registration import AlmanacApiRegistrationPolicy
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from app.services.brightdata.part_price_service import fetch_parts_deterministic
from app.services.openai.vision_part_extractor import (
    extract_part_diagnosis,
    validate_diagnosis,
)
from app.services.youtube.instructor_service import find_best_tutorial_video
from app.uagents_protocol.chat_inbound import extract_diagnostic_inputs
from app.uagents_protocol.final_markdown import format_diagnostic_markdown
from app.uagents_protocol.schemas import (
    PartsSourcingRequest,
    TutorialSearchRequest,
)

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("orchestrator")

# How long to wait for a worker REST call before falling back to direct service calls.
_WORKER_TIMEOUT_S: int = int(os.getenv("WORKER_TIMEOUT_S", "120"))

# Worker REST endpoints — the orchestrator POSTs directly to these URLs.
# Workers expose /diagnose-parts and /find-tutorial as REST handlers.
_PARTS_AGENT_URL = "http://{host}:{port}/diagnose-parts".format(
    host=os.getenv("PARTS_AGENT_HOST", "127.0.0.1"),
    port=os.getenv("PARTS_AGENT_PORT", "8002"),
)
_TUTORIAL_AGENT_URL = "http://{host}:{port}/find-tutorial".format(
    host=os.getenv("TUTORIAL_AGENT_HOST", "127.0.0.1"),
    port=os.getenv("TUTORIAL_AGENT_PORT", "8003"),
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _network() -> str:
    return (
        "mainnet"
        if os.getenv("AGENT_NETWORK", "testnet").lower() == "mainnet"
        else "testnet"
    )


def _agent_port() -> int:
    # Render injects PORT; Docker users can set it too.
    return int(os.getenv("PORT") or os.getenv("ORCHESTRATOR_AGENT_PORT") or "8001")


def _address_from_seed(name: str, seed: str) -> str:
    tmp = Agent(name=name, seed=seed)
    return tmp.address


def _free_port(port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return
    except OSError:
        return
    try:
        import psutil

        try:
            conns = psutil.net_connections(kind="inet")
        except AttributeError:
            conns = psutil.net_connections()
        for conn in conns:
            if conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    log.info(
                        "Freeing port %d — killing PID %d (%s)",
                        port,
                        conn.pid,
                        proc.name(),
                    )
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                return
    except ImportError:
        log.warning("Port %d busy — install psutil or kill the process manually.", port)


# ──────────────────────────────────────────────────────────────────────────────
# Chat Protocol  (Chat protocol handlers + worker response handlers)
# ──────────────────────────────────────────────────────────────────────────────

chat_protocol = Protocol(spec=chat_protocol_spec)

# ── Main pipeline handler ─────────────────────────────────────────────────────


def _chat_reply(text: str, *, end_session: bool = True) -> ChatMessage:
    content: list = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=content,
    )


@chat_protocol.on_message(model=ChatMessage)
async def orchestrator_chat(ctx: Context, sender: str, msg: ChatMessage):
    """
    Pipeline:
      1. ACK immediately
      2. Parse image + context_text from ChatMessage
      3. Send progress message
      4. Vision LLM → identify part
      5. Direct REST calls to worker agents (asyncio.gather, true parallel):
           POST /diagnose-parts  → parts-agent
           POST /find-tutorial   → tutorial-agent
         Plain HTTP avoids the mailbox-poll deadlock inherent in
         send_and_receive when the orchestrator is in mailbox mode.
         Falls back to direct service calls if workers are unavailable.
      6. Format hero Markdown → send reply

    All steps after the ACK are wrapped in a broad try/except so that any
    unhandled error produces a graceful user-facing message, not a silent hang.
    """
    # 1 ── ACK (outside try/except — must always be sent)
    await ctx.send(
        sender,
        ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id,
            timestamp=datetime.now(timezone.utc),
        ),
    )

    try:
        await _run_pipeline(ctx, sender, msg)
    except Exception as exc:  # noqa: BLE001
        log.exception("[orch] Unhandled error in pipeline: %s", exc)
        try:
            await ctx.send(
                sender,
                _chat_reply(
                    "Sorry, something went wrong on my end. "
                    "Please try again in a moment — or check the agent logs for details."
                ),
            )
        except Exception:
            pass


async def _run_pipeline(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Inner pipeline — called by orchestrator_chat inside a broad try/except."""
    # 2 ── Parse inputs
    context_text, image_b64 = await extract_diagnostic_inputs(msg)
    log.info("[orch] context=%r | has_image=%s", context_text, bool(image_b64))

    if not image_b64:
        await ctx.send(
            sender,
            _chat_reply(
                "Please **attach a photo** of the broken part (or paste an image URL) "
                "and include your appliance or vehicle model "
                "(e.g. `Whirlpool WRF535SWHZ00`).",
            ),
        )
        return

    if not context_text:
        await ctx.send(
            sender,
            _chat_reply(
                "Got the photo — please also tell me your **appliance or vehicle model** "
                "(e.g. `Whirlpool WRF535SWHZ00` or `2018 Honda Civic`).",
            ),
        )
        return

    # Truncate for the progress message only — protect against very long inputs
    _preview = context_text[:80] + ("…" if len(context_text) > 80 else "")

    # 3 ── Progress message (prevents ASI:One timeout)
    await ctx.send(
        sender,
        _chat_reply(
            f"Analysing your photo against **{_preview}** — "
            "identifying the part, checking prices and finding a tutorial...",
            end_session=False,
        ),
    )

    # 4 ── Vision LLM
    log.info("[orch] Calling Vision LLM — context=%r", context_text)
    vision = await extract_part_diagnosis(image_b64, context_text)
    verr = validate_diagnosis(vision)
    if verr:
        await ctx.send(
            sender,
            _chat_reply(
                f"Could not identify the part from the photo: {verr}. "
                "Please try a clearer image."
            ),
        )
        return

    brand = vision.get("brand", "")
    model_number = vision.get("model_number", "")
    appliance_type = vision.get("appliance_type", "")

    log.info(
        "[orch] Vision: part=%s (%s) brand=%s model=%s type=%s labor=$%.2f conf=%.0f%%",
        vision["part_name"],
        vision["part_number"],
        brand or "?",
        model_number or "?",
        appliance_type or "?",
        vision["estimated_labor_cost"],
        vision["confidence"] * 100,
    )

    # 5 ── Fan-out: direct REST calls to worker agents (true parallelism)
    #
    # Workers expose REST endpoints (/diagnose-parts, /find-tutorial) on
    # their ASGI servers.  The orchestrator calls them via plain aiohttp POST.
    # This bypasses the uAgents envelope/dispenser pipeline entirely, avoiding
    # a mailbox-poll deadlock that occurs when the orchestrator (in mailbox
    # mode) tries to use send_and_receive: the mailbox-poll loop is blocked
    # while this handler runs, so worker responses queued in Agentverse can
    # never be picked up → 120s timeout.  Direct REST calls don't have this
    # problem because the response comes back in the HTTP body immediately.

    # Tutorial query: brand + appliance type + part name — NOT the raw part
    # number (nobody titles a YouTube video with a part number).
    tut_parts = [
        "how to replace",
        vision["part_name"],
        brand,
        appliance_type,
    ]
    search_query = " ".join(p for p in tut_parts if p).strip()

    log.info(
        "[orch] REST fan-out → parts=%s | tutorial=%s | timeout=%ds",
        _PARTS_AGENT_URL,
        _TUTORIAL_AGENT_URL,
        _WORKER_TIMEOUT_S,
    )

    async def _call_parts() -> dict | None:
        req = PartsSourcingRequest(
            part_name=str(vision["part_name"]),
            part_number=str(vision["part_number"]),
            context_text=context_text,
            brand=brand,
            model_number=model_number,
            appliance_type=appliance_type,
            session_id=str(uuid4()),
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    _PARTS_AGENT_URL,
                    json=req.model_dump(),
                    timeout=aiohttp.ClientTimeout(total=_WORKER_TIMEOUT_S),
                ) as r:
                    if r.status == 200:
                        return await r.json()
                    log.warning(
                        "[orch] parts-agent returned %d: %s", r.status, await r.text()
                    )
        except Exception as exc:
            log.warning("[orch] parts-agent unreachable: %s", exc)
        return None

    async def _call_tutorial() -> dict | None:
        req = TutorialSearchRequest(
            search_query=search_query,
            part_name=str(vision["part_name"]),
            brand=brand,
            appliance_type=appliance_type,
            session_id=str(uuid4()),
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    _TUTORIAL_AGENT_URL,
                    json=req.model_dump(),
                    timeout=aiohttp.ClientTimeout(total=_WORKER_TIMEOUT_S),
                ) as r:
                    if r.status == 200:
                        return await r.json()
                    log.warning(
                        "[orch] tutorial-agent returned %d: %s",
                        r.status,
                        await r.text(),
                    )
        except Exception as exc:
            log.warning("[orch] tutorial-agent unreachable: %s", exc)
        return None

    parts_data, tut_data = await asyncio.gather(_call_parts(), _call_tutorial())

    # Build parts_dict — use worker result if available, else direct fallback
    if parts_data is not None:
        parts_dict = {
            "price_usd": parts_data.get("price_usd", 0),
            "purchase_url": parts_data.get("purchase_url", ""),
            "stock_status": parts_data.get("stock_status", ""),
            "source_site": parts_data.get("source_site", ""),
            "all_sources": parts_data.get("all_sources", []),
            "excel_path": parts_data.get("excel_path", ""),
        }
    else:
        log.warning(
            "[orch] parts-agent unavailable — falling back to direct service call"
        )
        direct_parts = await fetch_parts_deterministic(
            str(vision["part_name"]),
            str(vision["part_number"]),
            context_text,
            brand=brand,
            model_number=model_number,
            appliance_type=appliance_type,
        )
        parts_dict = dict(direct_parts)

    # Build tut_dict — use worker result if available, else direct fallback
    if tut_data is not None:
        tut_dict = {
            "video_url": tut_data.get("video_url", ""),
            "video_title": tut_data.get("video_title", ""),
            "duration_seconds": tut_data.get("duration_seconds", 0),
        }
    else:
        log.warning(
            "[orch] tutorial-agent unavailable — falling back to direct service call"
        )
        vurl, vtitle, vdur = await find_best_tutorial_video(search_query)
        tut_dict = {"video_url": vurl, "video_title": vtitle, "duration_seconds": vdur}

    log.info(
        "[orch] ← results: parts=$%.2f at %s | tutorial='%s'",
        parts_dict["price_usd"],
        parts_dict["source_site"],
        tut_dict["video_title"],
    )

    # 6 ── Hero response
    markdown = format_diagnostic_markdown(vision, parts_dict, tut_dict)
    log.info("[orch] Sending final response to %s", sender)
    await ctx.send(sender, _chat_reply(markdown))


@chat_protocol.on_message(model=ChatAcknowledgement)
async def on_chat_ack(_ctx: Context, _sender: str, _msg: ChatAcknowledgement):
    """No-op — required by Chat Protocol spec."""
    return


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    os.chdir(PROJECT_ROOT)

    port = _agent_port()
    av_key = os.getenv("AGENTVERSE_API_KEY", "").strip()
    seed = os.getenv(
        "ORCHESTRATOR_AGENT_SEED", "repair orchestrator gateway seed phrase four"
    )
    public_endpoint = os.getenv("AGENT_ENDPOINT", "").strip()

    _free_port(port)

    # mailbox (key as value) OR endpoint — never both (pdf-podcast-agent pattern).
    # Passing both triggers "Endpoint overrides mailbox" and disables the mailbox.
    _use_mailbox = bool(av_key) and not public_endpoint
    orchestrator = Agent(
        name="repair-orchestrator",
        seed=seed,
        port=port,
        **(
            {
                "mailbox": av_key,  # Agentverse relay
            }
            if _use_mailbox
            else {
                "endpoint": [
                    public_endpoint or f"http://127.0.0.1:{port}/submit"
                ],  # direct HTTP
            }
        ),
        network=_network(),
        registration_policy=AlmanacApiRegistrationPolicy(),
    )

    orchestrator.include(chat_protocol, publish_manifest=True)

    @orchestrator.on_event("startup")
    async def _startup(_ctx: Context) -> None:
        mode = "mailbox" if _use_mailbox else "direct HTTP"
        log.info("[orch] Ready — routing mode: %s", mode)

    @orchestrator.on_interval(period=30.0)
    async def _heartbeat(_ctx: Context) -> None:
        log.info("[orch] ♥ alive | address=%s", orchestrator.address)

    inspector_url = (
        f"https://agentverse.ai/inspect/"
        f"?uri=http%3A//127.0.0.1%3A{port}"
        f"&address={orchestrator.address}"
    )

    log.info("=" * 60)
    log.info("Appliance / Auto Whisperer  —  Orchestrator")
    log.info("=" * 60)
    log.info("Network    : %s", _network())
    log.info("Mailbox    : %s", "enabled" if _use_mailbox else "disabled")
    log.info("Address    : %s", orchestrator.address)
    log.info("")
    log.info("Workers (start BEFORE this agent):")
    log.info("  parts-agent    REST=%s", _PARTS_AGENT_URL)
    log.info("  tutorial-agent REST=%s", _TUTORIAL_AGENT_URL)
    log.info("")
    log.info(
        "Worker timeout : %.0fs (set WORKER_TIMEOUT_S to adjust)", _WORKER_TIMEOUT_S
    )
    log.info("Fallback       : direct service calls if workers are unreachable")
    log.info("")
    log.info("Inspector / reconnect mailbox if needed:")
    log.info("  %s", inspector_url)
    log.info("=" * 60)

    orchestrator.run()


if __name__ == "__main__":
    main()
