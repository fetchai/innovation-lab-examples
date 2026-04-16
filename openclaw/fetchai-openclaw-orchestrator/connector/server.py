"""
OpenClaw Connector – local uAgents-based agent.

This agent runs locally on the user's machine and:
  1. Generates / loads an Ed25519 keypair on first run
  2. Pairs with the Fetch Orchestrator Agent
  3. Listens for task dispatch messages
  4. Verifies signatures and local policies
  5. Executes task plans via the executor
  6. Returns results to the orchestrator

Usage:
    python -m connector.server
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("connector")

# ---------------------------------------------------------------------------
# Crypto – generate or load keypair
# ---------------------------------------------------------------------------

from shared.crypto import (  # noqa: E402
    generate_keypair,
    load_keypair,
    public_key_to_hex,
    save_keypair,
)

KEY_DIR = Path(os.getenv("CONNECTOR_KEY_DIR", "./keys"))

if (KEY_DIR / "private.hex").exists():
    logger.info("Loading existing keypair from %s", KEY_DIR)
    _private_key, _public_key = load_keypair(KEY_DIR)
else:
    logger.info("Generating new keypair → %s", KEY_DIR)
    _private_key, _public_key = generate_keypair()
    save_keypair(KEY_DIR, _private_key)

DEVICE_PUBLIC_KEY_HEX = public_key_to_hex(_public_key)
logger.info("Device public key: %s", DEVICE_PUBLIC_KEY_HEX)

# ---------------------------------------------------------------------------
# Auth & Policy singletons
# ---------------------------------------------------------------------------

from connector.auth import RequestAuthenticator  # noqa: E402
from connector.policy import LocalPolicy  # noqa: E402

authenticator = RequestAuthenticator()
local_policy = LocalPolicy()

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

from uagents import Agent, Context  # noqa: E402

_CONNECTOR_SEED = os.getenv("CONNECTOR_AGENT_SEED", "openclaw-connector-dev-seed")
_NETWORK = os.getenv("AGENT_NETWORK", "testnet")  # testnet by default

connector_agent = Agent(
    name="openclaw-connector",
    seed=_CONNECTOR_SEED,
    port=int(os.getenv("CONNECTOR_PORT", "8199")),
    endpoint=[
        f"http://{os.getenv('CONNECTOR_HOST', '127.0.0.1')}:{os.getenv('CONNECTOR_PORT', '8199')}/submit"
    ],
    network=_NETWORK,
)

# ---------------------------------------------------------------------------
# Import message models
# ---------------------------------------------------------------------------

from orchestrator.protocols.models import (  # noqa: E402
    ObjectiveResponse,
    PairDeviceRequest,
    PairDeviceResponse,
    TaskDispatchRequest,
    TaskExecutionResult,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The user must set these or pass via env
_USER_ID = os.getenv("CONNECTOR_USER_ID", "u_dev")
_DEVICE_ID = os.getenv("CONNECTOR_DEVICE_ID", "dev_local")
_ORCHESTRATOR_ADDRESS = os.getenv("ORCHESTRATOR_AGENT_ADDRESS", "")

# ---------------------------------------------------------------------------
# Startup – pair with orchestrator
# ---------------------------------------------------------------------------


@connector_agent.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info("OpenClaw Connector started")
    ctx.logger.info("Agent address : %s", connector_agent.address)
    ctx.logger.info("Network       : %s", _NETWORK)
    ctx.logger.info("Device pubkey : %s", DEVICE_PUBLIC_KEY_HEX)

    if _ORCHESTRATOR_ADDRESS:
        ctx.logger.info(
            "Sending pairing request to orchestrator %s", _ORCHESTRATOR_ADDRESS
        )
        await ctx.send(
            _ORCHESTRATOR_ADDRESS,
            PairDeviceRequest(
                user_id=_USER_ID,
                device_id=_DEVICE_ID,
                public_key_hex=DEVICE_PUBLIC_KEY_HEX,
                capabilities=["weekly_report", "repo_analyzer"],
            ),
        )
    else:
        ctx.logger.warning(
            "ORCHESTRATOR_AGENT_ADDRESS not set – skipping auto-pairing. "
            "Set it in .env to enable automatic pairing on startup."
        )


# ---------------------------------------------------------------------------
# Handle pairing response
# ---------------------------------------------------------------------------


@connector_agent.on_message(PairDeviceResponse)
async def handle_pairing_response(ctx: Context, sender: str, msg: PairDeviceResponse):
    if msg.status == "paired":
        ctx.logger.info("✅  Paired successfully: %s", msg.message)
    else:
        ctx.logger.error("❌  Pairing rejected: %s", msg.message)


# ---------------------------------------------------------------------------
# Handle task dispatch
# ---------------------------------------------------------------------------


@connector_agent.on_message(ObjectiveResponse)
async def handle_objective_response(ctx: Context, sender: str, msg: ObjectiveResponse):
    """Acknowledge receipt of ObjectiveResponse from orchestrator (protocol ack)."""
    ctx.logger.info(
        "Orchestrator acknowledged task %s (status: %s)", msg.task_id, msg.status
    )


@connector_agent.on_message(TaskDispatchRequest, replies={TaskExecutionResult})
async def handle_task_dispatch(ctx: Context, sender: str, msg: TaskDispatchRequest):
    """
    Core handler: verify → policy check → execute → return result.
    """
    from connector.executor import execute_plan
    from shared.schemas import RejectionReason, TaskPlan, TaskStatus

    ctx.logger.info(
        "Task dispatch received: user=%s device=%s", msg.user_id, msg.device_id
    )

    # 1. Verify ownership
    if msg.user_id != _USER_ID or msg.device_id != _DEVICE_ID:
        ctx.logger.warning("User/device mismatch – rejecting")
        await ctx.send(
            sender,
            TaskExecutionResult(
                task_id="",
                status=TaskStatus.REJECTED.value,
                reason=RejectionReason.DEVICE_NOT_PAIRED.value,
            ),
        )
        return

    # 2. Verify signature
    ok, reason = authenticator.verify_dispatch(msg.task_plan_json, msg.signature)
    if not ok:
        ctx.logger.warning("Signature verification failed")
        await ctx.send(
            sender,
            TaskExecutionResult(
                task_id="",
                status=TaskStatus.REJECTED.value,
                reason=(reason or RejectionReason.INVALID_SIGNATURE).value,
            ),
        )
        return

    # 3. Deserialise plan
    try:
        plan = TaskPlan.model_validate_json(msg.task_plan_json)
    except Exception as exc:
        ctx.logger.error("Invalid task plan JSON: %s", exc)
        await ctx.send(
            sender,
            TaskExecutionResult(
                task_id="",
                status=TaskStatus.REJECTED.value,
                reason=RejectionReason.POLICY_VIOLATION.value,
            ),
        )
        return

    # 4. Local policy check
    policy_rejection = local_policy.validate_plan(plan)
    if policy_rejection is not None:
        ctx.logger.warning("Local policy rejected plan: %s", policy_rejection.value)
        await ctx.send(
            sender,
            TaskExecutionResult(
                task_id=plan.task_id,
                status=TaskStatus.REJECTED.value,
                reason=policy_rejection.value,
            ),
        )
        return

    # 5. Execute
    ctx.logger.info("Executing task plan %s (%d steps)", plan.task_id, len(plan.steps))
    result = execute_plan(plan)

    # 6. Return result
    await ctx.send(
        sender,
        TaskExecutionResult(
            task_id=result.task_id,
            status=result.status.value,
            step_results_json=json.dumps(
                [sr.model_dump(mode="json") for sr in result.step_results]
            ),
            outputs=result.outputs,
            reason=result.reason.value if result.reason else "",
        ),
    )
    ctx.logger.info(
        "Task %s completed with status: %s", result.task_id, result.status.value
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    logger.info("Starting OpenClaw Connector agent…")
    connector_agent.run()


if __name__ == "__main__":
    main()
