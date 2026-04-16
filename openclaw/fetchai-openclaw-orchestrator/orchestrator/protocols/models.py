"""
uAgents message models for the Orchestrator ↔ ASI:One and
Orchestrator ↔ OpenClaw Connector protocols.

These are thin wrappers that the uAgents framework uses for
on-the-wire serialisation.  Business-logic schemas live in
``shared.schemas``.
"""

from __future__ import annotations

from typing import Any

from uagents import Model


# ---------------------------------------------------------------------------
# ASI:One → Orchestrator
# ---------------------------------------------------------------------------


class ObjectiveRequest(Model):
    """User objective forwarded by ASI:One."""

    user_id: str
    objective: str
    metadata: dict[str, Any] = {}


class ObjectiveResponse(Model):
    """Result returned to ASI:One."""

    user_id: str
    task_id: str
    status: str  # completed | failed | rejected | partial
    outputs: dict[str, Any] = {}
    reason: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Device pairing (Connector → Orchestrator)
# ---------------------------------------------------------------------------


class PairDeviceRequest(Model):
    """Sent by the local connector to register its public key."""

    user_id: str
    device_id: str
    public_key_hex: str
    capabilities: list[str] = []


class PairDeviceResponse(Model):
    """Returned by the orchestrator."""

    user_id: str
    device_id: str
    status: str  # paired | rejected
    message: str = ""


# ---------------------------------------------------------------------------
# Task dispatch (Orchestrator → Connector)
# ---------------------------------------------------------------------------


class TaskDispatchRequest(Model):
    """Signed task plan sent to the OpenClaw Connector."""

    user_id: str
    device_id: str
    task_plan_json: str  # JSON-encoded TaskPlan
    signature: str  # hex-encoded Ed25519 signature


class TaskExecutionResult(Model):
    """Execution outcome returned by the connector."""

    task_id: str
    status: str  # completed | failed | rejected | partial
    step_results_json: str = "[]"
    outputs: dict[str, Any] = {}
    reason: str = ""
