"""Tests for shared.schemas – data model validation."""

from shared.schemas import (
    DeviceRecord,
    ExecutionResult,
    Objective,
    PairingRequest,
    StepType,
    TaskConstraints,
    TaskPlan,
    TaskStatus,
    TaskStep,
)


def test_task_step_creation():
    step = TaskStep(
        type=StepType.LOCAL, action="scan_directory", params={"path": "~/projects"}
    )
    assert step.type == StepType.LOCAL
    assert step.action == "scan_directory"
    assert step.params["path"] == "~/projects"


def test_task_plan_defaults():
    plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="scan_directory")])
    assert plan.task_id.startswith("task_")
    assert plan.constraints.no_delete is True
    assert plan.constraints.require_user_confirmation is True
    assert plan.created_at is not None


def test_task_plan_serialisation_roundtrip():
    plan = TaskPlan(
        steps=[
            TaskStep(
                type=StepType.LOCAL,
                action="scan_directory",
                params={"path": "~/projects"},
            ),
            TaskStep(
                type=StepType.EXTERNAL,
                action="post_summary",
                params={"target": "slack"},
            ),
        ],
        constraints=TaskConstraints(no_delete=True, max_duration_seconds=120),
    )
    json_str = plan.model_dump_json()
    restored = TaskPlan.model_validate_json(json_str)
    assert restored.task_id == plan.task_id
    assert len(restored.steps) == 2
    assert restored.constraints.max_duration_seconds == 120


def test_execution_result():
    result = ExecutionResult(
        task_id="task_001",
        status=TaskStatus.COMPLETED,
        outputs={"summary": "hello"},
    )
    assert result.status == TaskStatus.COMPLETED
    assert result.reason is None


def test_objective():
    obj = Objective(user_id="u_1", objective="Generate report")
    assert obj.user_id == "u_1"


def test_pairing_request():
    req = PairingRequest(
        user_id="u_1",
        device_id="dev_1",
        public_key_hex="a" * 64,
    )
    assert req.capabilities == ["weekly_report"]


def test_device_record_defaults():
    rec = DeviceRecord(
        user_id="u_1",
        device_id="dev_1",
        public_key_hex="b" * 64,
        capabilities=["weekly_report"],
    )
    assert rec.paired_at is not None
