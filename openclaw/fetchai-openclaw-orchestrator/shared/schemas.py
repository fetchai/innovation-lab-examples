"""
Canonical data schemas for the Fetch-OpenClaw integration.

These Pydantic models are shared by both the Orchestrator Agent
and the OpenClaw Connector so the wire format is defined in one place.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StepType(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    PARTIAL = "partial"


class RejectionReason(str, Enum):
    DEVICE_NOT_PAIRED = "device_not_paired"
    INVALID_SIGNATURE = "invalid_signature"
    POLICY_VIOLATION = "policy_violation"
    QUOTA_EXCEEDED = "quota_exceeded"
    ACTION_NOT_ALLOWED = "action_not_allowed"
    PATH_NOT_ALLOWED = "path_not_allowed"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Objective (ASI:One → Orchestrator)
# ---------------------------------------------------------------------------


class Objective(BaseModel):
    """Inbound objective from ASI:One."""

    user_id: str
    objective: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Task plan
# ---------------------------------------------------------------------------


class TaskStep(BaseModel):
    """A single declarative step inside a task plan."""

    type: StepType
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class TaskConstraints(BaseModel):
    """Execution constraints attached to a task plan."""

    no_delete: bool = True
    require_user_confirmation: bool = True
    allowed_paths: list[str] = Field(default_factory=list)
    max_duration_seconds: int = 300


class TaskPlan(BaseModel):
    """Immutable task plan produced by the orchestrator's planner."""

    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    steps: list[TaskStep]
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Task dispatch (Orchestrator → Connector)
# ---------------------------------------------------------------------------


class TaskDispatch(BaseModel):
    """Signed envelope sent from Orchestrator to OpenClaw Connector."""

    user_id: str
    device_id: str
    task_plan: TaskPlan
    signature: str  # hex-encoded Ed25519 signature


# ---------------------------------------------------------------------------
# Execution result (Connector → Orchestrator)
# ---------------------------------------------------------------------------


class StepResult(BaseModel):
    """Outcome of a single step."""

    action: str
    status: TaskStatus
    output: Any = None
    error: str | None = None


class ExecutionResult(BaseModel):
    """Aggregate execution result returned by the connector."""

    task_id: str
    status: TaskStatus
    step_results: list[StepResult] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    reason: RejectionReason | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Device pairing
# ---------------------------------------------------------------------------


class PairingRequest(BaseModel):
    """Sent by the local connector to register with the orchestrator."""

    user_id: str
    device_id: str
    public_key_hex: str  # hex-encoded Ed25519 public key
    capabilities: list[str] = Field(default_factory=lambda: ["weekly_report"])


class PairingResponse(BaseModel):
    """Returned by the orchestrator after pairing."""

    user_id: str
    device_id: str
    status: str  # "paired" | "rejected"
    message: str = ""


class DeviceRecord(BaseModel):
    """Stored by the orchestrator for each paired device."""

    user_id: str
    device_id: str
    public_key_hex: str
    capabilities: list[str]
    paired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
