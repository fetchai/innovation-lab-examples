"""Tests for orchestrator.planner – objective → task plan conversion."""

import os

# Ensure LLM is NOT used during unit tests (keyword fallback only)
os.environ.pop("ASI_ONE_API_KEY", None)

from orchestrator.planner import plan_objective


def test_weekly_report_objective():
    plan = plan_objective("Generate my weekly dev report and post a summary")
    actions = [s.action for s in plan.steps]
    assert "generate_report" in actions
    assert "post_summary" in actions


def test_scan_and_report():
    plan = plan_objective("Scan my projects directory and generate a report")
    actions = [s.action for s in plan.steps]
    assert "scan_directory" in actions
    assert "generate_report" in actions


def test_post_to_email():
    plan = plan_objective("Send the report via email")
    steps = [s for s in plan.steps if s.action == "post_summary"]
    assert len(steps) == 1
    assert steps[0].params["target"] == "email"


def test_unknown_objective_falls_back():
    plan = plan_objective("Do something completely random")
    assert len(plan.steps) >= 1
    assert plan.steps[0].action == "summarise_text"


def test_plan_has_constraints():
    plan = plan_objective("Weekly report please")
    assert plan.constraints.no_delete is True
    assert plan.constraints.require_user_confirmation is True


def test_plan_task_id_generated():
    plan = plan_objective("test")
    assert plan.task_id.startswith("task_")
