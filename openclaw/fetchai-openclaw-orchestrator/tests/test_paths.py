"""Tests for shared path sandbox helpers."""

import os

from orchestrator.planner import _enforce_scan_directory_paths
from shared.paths import demo_projects_dir, is_path_under_demo, normalize_scan_directory_path
from shared.schemas import StepType, TaskPlan, TaskStep


def test_is_path_under_demo_rejects_documents():
    assert is_path_under_demo(os.path.expanduser("~/Documents")) is False


def test_normalize_forces_demo_by_default(monkeypatch):
    monkeypatch.delenv("OPENCLAW_EXTENDED_PATHS", raising=False)
    assert normalize_scan_directory_path(
        os.path.expanduser("~/Documents")
    ) == str(demo_projects_dir())


def test_planner_enforce_rewrites_scan_path(monkeypatch):
    monkeypatch.delenv("OPENCLAW_EXTENDED_PATHS", raising=False)
    plan = TaskPlan(
        steps=[
            TaskStep(
                type=StepType.LOCAL,
                action="scan_directory",
                params={"path": os.path.expanduser("~/Documents")},
            )
        ]
    )
    _enforce_scan_directory_paths(plan)
    assert is_path_under_demo(plan.steps[0].params["path"])
