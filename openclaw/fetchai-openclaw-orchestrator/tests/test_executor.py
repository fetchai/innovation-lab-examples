"""Tests for connector.executor – task plan execution."""

import tempfile

from connector.executor import execute_plan
from shared.paths import demo_projects_dir
from shared.schemas import StepType, TaskPlan, TaskStatus, TaskStep


def test_execute_summarise_text():
    plan = TaskPlan(
        steps=[
            TaskStep(
                type=StepType.LOCAL,
                action="summarise_text",
                params={"text": "Hello world, this is a test objective."},
            )
        ]
    )
    result = execute_plan(plan)
    assert result.status == TaskStatus.COMPLETED
    assert len(result.step_results) == 1
    assert result.step_results[0].status == TaskStatus.COMPLETED
    assert "summary" in (result.step_results[0].output or {})


def test_execute_unknown_action():
    plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="nonexistent_action")])
    result = execute_plan(plan)
    assert result.status in (TaskStatus.FAILED, TaskStatus.PARTIAL)
    assert result.step_results[0].status == TaskStatus.FAILED
    assert "Unknown action" in (result.step_results[0].error or "")


def test_execute_mixed_steps():
    """One good step + one unknown → PARTIAL."""
    plan = TaskPlan(
        steps=[
            TaskStep(
                type=StepType.LOCAL,
                action="summarise_text",
                params={"text": "ok"},
            ),
            TaskStep(type=StepType.LOCAL, action="bogus"),
        ]
    )
    result = execute_plan(plan)
    assert result.status == TaskStatus.PARTIAL
    assert result.step_results[0].status == TaskStatus.COMPLETED
    assert result.step_results[1].status == TaskStatus.FAILED


def test_scan_directory_nonexistent_path():
    missing = demo_projects_dir() / "_nonexistent_subdir_xyz"
    plan = TaskPlan(
        steps=[
            TaskStep(
                type=StepType.LOCAL,
                action="scan_directory",
                params={"path": str(missing)},
            )
        ]
    )
    result = execute_plan(plan)
    # Should complete but output an error
    assert result.status == TaskStatus.COMPLETED
    scan_out = result.step_results[0].output
    assert "error" in scan_out


def test_pipeline_chaining(monkeypatch):
    """scan_directory → generate_report should chain outputs."""
    monkeypatch.setenv("OPENCLAW_EXTENDED_PATHS", "1")
    with tempfile.TemporaryDirectory() as tmpdir:
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": tmpdir},
                ),
                TaskStep(
                    type=StepType.LOCAL,
                    action="generate_report",
                    params={"format": "text"},
                ),
            ]
        )
        result = execute_plan(plan)
        assert result.status == TaskStatus.COMPLETED
        report_out = result.step_results[1].output
        assert "report_text" in report_out
