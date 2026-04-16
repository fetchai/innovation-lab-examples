"""
Objective intake protocol.

Handles inbound objectives from ASI:One, runs the planner and
policy engine, dispatches to the paired OpenClaw Connector, and
returns results.
"""

from __future__ import annotations

import json
import logging

from uagents import Context, Protocol

from orchestrator.planner import plan_objective
from orchestrator.protocols.models import (
    ObjectiveRequest,
    ObjectiveResponse,
    TaskDispatchRequest,
    TaskExecutionResult,
)
from shared.schemas import RejectionReason

logger = logging.getLogger(__name__)

objective_protocol = Protocol(name="objective-intake", version="0.1.0")


@objective_protocol.on_message(ObjectiveRequest, replies={ObjectiveResponse})
async def handle_objective(ctx: Context, sender: str, msg: ObjectiveRequest):
    """
    1. Validate user pairing
    2. Plan the objective
    3. Enforce Fetch-side policies
    4. Dispatch to connector
    5. Return result to ASI:One
    """
    from orchestrator.agent import pairing_store, fetch_policy, orchestrator_private_key
    from shared.crypto import sign_payload

    ctx.logger.info(
        "Received objective from user %s: %.80s", msg.user_id, msg.objective
    )

    # --- 1. Check pairing ---------------------------------------------------
    devices = pairing_store.devices_for_user(msg.user_id)
    if not devices:
        ctx.logger.warning("No paired device for user %s", msg.user_id)
        await ctx.send(
            sender,
            ObjectiveResponse(
                user_id=msg.user_id,
                task_id="",
                status="rejected",
                reason=RejectionReason.DEVICE_NOT_PAIRED.value,
                message="No paired device found. Please pair a device first.",
            ),
        )
        return

    # Use first paired device (MVP: single-device)
    device = devices[0]

    # --- 2. Plan -------------------------------------------------------------
    plan = plan_objective(msg.objective)

    # --- 3. Policy -----------------------------------------------------------
    rejection = fetch_policy.validate(msg.user_id, plan)
    if rejection is not None:
        await ctx.send(
            sender,
            ObjectiveResponse(
                user_id=msg.user_id,
                task_id=plan.task_id,
                status="rejected",
                reason=rejection.value,
                message=f"Policy check failed: {rejection.value}",
            ),
        )
        return

    # --- 4. Dispatch to connector -------------------------------------------
    plan_dict = plan.model_dump(mode="json")
    plan_json = json.dumps(plan_dict, sort_keys=True, default=str)

    signature = ""
    if orchestrator_private_key is not None:
        signature = sign_payload(orchestrator_private_key, plan_dict)

    dispatch = TaskDispatchRequest(
        user_id=msg.user_id,
        device_id=device.device_id,
        task_plan_json=plan_json,
        signature=signature,
    )

    # Store pending task so we can correlate the reply
    pending = ctx.storage.get("pending_tasks") or "{}"
    pending_dict: dict = json.loads(pending)
    pending_dict[plan.task_id] = {
        "sender": sender,
        "user_id": msg.user_id,
    }
    ctx.storage.set("pending_tasks", json.dumps(pending_dict))

    # Look up the connector agent address in storage
    connector_address = ctx.storage.get(f"connector:{msg.user_id}:{device.device_id}")
    if connector_address:
        ctx.logger.info(
            "Dispatching task %s to connector %s", plan.task_id, connector_address
        )
        await ctx.send(connector_address, dispatch)
    else:
        ctx.logger.error("Connector address unknown for device %s", device.device_id)
        await ctx.send(
            sender,
            ObjectiveResponse(
                user_id=msg.user_id,
                task_id=plan.task_id,
                status="rejected",
                reason="connector_unreachable",
                message="Connector agent address not registered.",
            ),
        )


@objective_protocol.on_message(TaskExecutionResult, replies={ObjectiveResponse})
async def handle_execution_result(ctx: Context, sender: str, msg: TaskExecutionResult):
    """
    Receive execution results from the connector.

    Routes the result back to the original requester — either as an
    ``ObjectiveResponse`` (agent-to-agent) or a ``ChatMessage``
    (if the task was initiated via ASI:One chat).

    IMPORTANT: We must ALWAYS send an ``ObjectiveResponse`` back to the
    connector (the sender) to satisfy the protocol reply contract,
    even when the task was chat-originated.
    """
    ctx.logger.info("Execution result for task %s: %s", msg.task_id, msg.status)

    # Always acknowledge the connector with an ObjectiveResponse first
    await ctx.send(
        sender,
        ObjectiveResponse(
            user_id="system",
            task_id=msg.task_id,
            status=msg.status,
            reason=msg.reason or "",
            message=f"Task {msg.task_id} result acknowledged.",
        ),
    )

    # --- Check if this was a chat-originated task ----------------------------
    chat_pending = ctx.storage.get("chat_pending") or "{}"
    chat_dict: dict = json.loads(chat_pending)
    chat_meta = chat_dict.pop(msg.task_id, None)
    if chat_meta is not None:
        ctx.storage.set("chat_pending", json.dumps(chat_dict))
        await _relay_to_chat(ctx, chat_meta, msg)
        return

    # --- Otherwise it's a standard ObjectiveRequest flow ---------------------
    pending = ctx.storage.get("pending_tasks") or "{}"
    pending_dict: dict = json.loads(pending)
    task_meta = pending_dict.pop(msg.task_id, None)
    ctx.storage.set("pending_tasks", json.dumps(pending_dict))

    if task_meta is None:
        ctx.logger.warning("No pending request for task %s – ignoring", msg.task_id)
        return

    await ctx.send(
        task_meta["sender"],
        ObjectiveResponse(
            user_id=task_meta["user_id"],
            task_id=msg.task_id,
            status=msg.status,
            outputs=msg.outputs,
            reason=msg.reason,
            message=f"Task {msg.task_id} finished with status: {msg.status}",
        ),
    )


async def _relay_to_chat(ctx: Context, chat_meta: dict, msg: TaskExecutionResult):
    """Format a TaskExecutionResult and send it back as a ChatMessage."""
    from orchestrator.protocols.chat import send_chat_reply

    lines: list[str] = []

    if msg.status == "rejected":
        lines.append(f"Task `{msg.task_id}` was rejected.")
        if msg.reason:
            lines.append(f"Reason: {msg.reason}")
        await send_chat_reply(ctx, chat_meta["sender"], "\n".join(lines))
        return

    # --- Check if outputs contain a report (weekly or health) ----------------
    report_text = None
    if msg.outputs:
        report_text = msg.outputs.get("generate_report", {}).get(
            "report_text"
        ) or msg.outputs.get("generate_health_report", {}).get("report_text")

    if report_text:
        # The report IS the primary output - send it directly
        lines.append(report_text)
    else:
        # Generic output formatting
        lines.append(f"Task `{msg.task_id}` completed ({msg.status}).")
        if msg.outputs:
            lines.append("")
            for key, value in msg.outputs.items():
                if isinstance(value, dict):
                    for k, v in value.items():
                        if isinstance(v, str) and len(v) > 300:
                            lines.append(f"- {k}: {v[:300]}...")
                        else:
                            lines.append(f"- {k}: {v}")
                else:
                    lines.append(f"- {key}: {value}")

    await send_chat_reply(ctx, chat_meta["sender"], "\n".join(lines))
