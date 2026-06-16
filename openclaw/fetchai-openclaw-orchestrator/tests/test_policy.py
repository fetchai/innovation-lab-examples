"""Tests for both Fetch-side and local policy engines."""

import os

from connector.policy import LocalPolicy
from orchestrator.policy import FetchPolicy
from shared.paths import demo_projects_dir
from shared.schemas import (
    RejectionReason,
    StepType,
    TaskPlan,
    TaskStep,
)


# =========================================================================
# Fetch-side policy
# =========================================================================


class TestFetchPolicy:
    def test_allowed_plan_passes(self):
        policy = FetchPolicy()
        plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="scan_directory")])
        assert policy.validate("u_1", plan) is None

    def test_disallowed_action_rejected(self):
        policy = FetchPolicy()
        plan = TaskPlan(
            steps=[TaskStep(type=StepType.LOCAL, action="delete_everything")]
        )
        assert policy.validate("u_1", plan) == RejectionReason.ACTION_NOT_ALLOWED

    def test_too_many_steps_rejected(self):
        policy = FetchPolicy(max_steps_per_plan=2)
        plan = TaskPlan(
            steps=[
                TaskStep(type=StepType.LOCAL, action="scan_directory"),
                TaskStep(type=StepType.LOCAL, action="generate_report"),
                TaskStep(type=StepType.LOCAL, action="summarise_text"),
            ]
        )
        assert policy.validate("u_1", plan) == RejectionReason.POLICY_VIOLATION

    def test_rate_limit(self):
        policy = FetchPolicy(rate_limit_per_minute=2)
        plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="scan_directory")])
        assert policy.validate("u_1", plan) is None
        assert policy.validate("u_1", plan) is None
        assert policy.validate("u_1", plan) == RejectionReason.QUOTA_EXCEEDED

    def test_scan_directory_outside_demo_rejected(self):
        policy = FetchPolicy()
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": os.path.expanduser("~/Documents")},
                )
            ]
        )
        assert policy.validate("u_1", plan) == RejectionReason.PATH_NOT_ALLOWED

    def test_scan_directory_under_demo_passes(self):
        policy = FetchPolicy()
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": str(demo_projects_dir())},
                )
            ]
        )
        assert policy.validate("u_1", plan) is None


# =========================================================================
# Local policy
# =========================================================================


class TestLocalPolicy:
    def test_allowed_action_passes(self):
        policy = LocalPolicy()
        plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="scan_directory")])
        assert policy.validate_plan(plan) is None

    def test_disallowed_action_rejected(self):
        policy = LocalPolicy()
        plan = TaskPlan(steps=[TaskStep(type=StepType.LOCAL, action="rm_rf")])
        assert policy.validate_plan(plan) == RejectionReason.ACTION_NOT_ALLOWED

    def test_path_outside_sandbox_rejected(self):
        policy = LocalPolicy(allowed_paths=["/tmp"])
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": "/etc/passwd"},
                )
            ]
        )
        assert policy.validate_plan(plan) == RejectionReason.PATH_NOT_ALLOWED

    def test_path_inside_sandbox_passes(self):
        policy = LocalPolicy(allowed_paths=["/tmp"])
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": "/tmp/mydata"},
                )
            ]
        )
        assert policy.validate_plan(plan) is None

    def test_default_policy_rejects_documents_path(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_EXTENDED_PATHS", raising=False)
        policy = LocalPolicy()
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": os.path.expanduser("~/Documents")},
                )
            ]
        )
        assert policy.validate_plan(plan) == RejectionReason.PATH_NOT_ALLOWED

    def test_default_policy_allows_demo_path(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_EXTENDED_PATHS", raising=False)
        policy = LocalPolicy()
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="scan_directory",
                    params={"path": str(demo_projects_dir())},
                )
            ]
        )
        assert policy.validate_plan(plan) is None
