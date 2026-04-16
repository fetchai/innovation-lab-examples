"""
Task plan executor for the OpenClaw Connector.

Translates a :class:`TaskPlan` into concrete local actions, executes
them sequentially, and collects results.

Execution rules (from the design doc):
  • Steps run sequentially
  • Failures are reported per step
  • No automatic retries without user consent
  • Task plans are treated as immutable
"""

from __future__ import annotations

import logging
from typing import Any, Callable, cast

from shared.schemas import (
    ExecutionResult,
    StepResult,
    TaskPlan,
    TaskStatus,
)
from connector.workflows.weekly_report import (
    generate_report,
    post_summary,
    scan_directory,
)
from connector.workflows.repo_analyzer import (
    analyze_repo,
    clone_repo,
    generate_health_report,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action registry
# ---------------------------------------------------------------------------

ActionFn = Callable[[dict[str, Any]], dict[str, Any]]

# Two-arg variants accept (params, previous_output)
ActionFn2 = Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]]

_ACTIONS: dict[str, ActionFn | ActionFn2] = {
    # Weekly report workflow
    "scan_directory": scan_directory,
    "generate_report": generate_report,
    "post_summary": post_summary,
    # Repo analyzer workflow
    "clone_repo": clone_repo,
    "analyze_repo": analyze_repo,
    "generate_health_report": generate_health_report,
}


def register_action(name: str, fn: ActionFn | ActionFn2) -> None:
    """Register a custom action handler."""
    _ACTIONS[name] = fn


# ---------------------------------------------------------------------------
# Summarise text (simple fallback)
# ---------------------------------------------------------------------------


def _summarise_text(params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "")
    # Trivial summarisation: first 200 chars
    return {"summary": text[:200]}


_ACTIONS["summarise_text"] = _summarise_text


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def execute_plan(plan: TaskPlan) -> ExecutionResult:
    """
    Execute every step in *plan* sequentially and return an
    :class:`ExecutionResult`.
    """
    step_results: list[StepResult] = []
    overall_status = TaskStatus.COMPLETED
    aggregated_outputs: dict[str, Any] = {}
    previous_output: dict[str, Any] | None = None

    for idx, step in enumerate(plan.steps):
        logger.info(
            "[%s] Step %d/%d – %s:%s",
            plan.task_id,
            idx + 1,
            len(plan.steps),
            step.type.value,
            step.action,
        )

        handler = _ACTIONS.get(step.action)
        if handler is None:
            sr = StepResult(
                action=step.action,
                status=TaskStatus.FAILED,
                error=f"Unknown action: {step.action}",
            )
            step_results.append(sr)
            overall_status = TaskStatus.PARTIAL
            logger.error("Unknown action '%s' – skipping", step.action)
            previous_output = None
            continue

        try:
            # Some handlers accept previous output (pipeline chaining)
            import inspect

            sig = inspect.signature(handler)
            handler_fn = cast(Callable[..., dict[str, Any]], handler)
            if len(sig.parameters) >= 2:
                output = handler_fn(step.params, previous_output)
            else:
                output = handler_fn(step.params)

            sr = StepResult(
                action=step.action,
                status=TaskStatus.COMPLETED,
                output=output,
            )
            previous_output = output
            aggregated_outputs[step.action] = output

        except Exception as exc:
            logger.exception("Step %s failed", step.action)
            sr = StepResult(
                action=step.action,
                status=TaskStatus.FAILED,
                error=str(exc),
            )
            overall_status = TaskStatus.PARTIAL
            # Do not abort – report per-step and continue (design doc §6)
            # Clear pipeline context so the next step does not receive stale output
            # from a prior successful step after this failure.
            previous_output = None

        step_results.append(sr)

    # If every step failed, mark overall as failed
    if all(s.status == TaskStatus.FAILED for s in step_results):
        overall_status = TaskStatus.FAILED

    return ExecutionResult(
        task_id=plan.task_id,
        status=overall_status,
        step_results=step_results,
        outputs=aggregated_outputs,
    )
