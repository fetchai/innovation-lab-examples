"""
Fetch-side policy engine.

Enforces planning-time rules *before* a task plan is dispatched:
  • User ownership validation
  • Quota / rate limits
  • Workflow allowlist
  • (Future) paid feature gating
"""

from __future__ import annotations
from pathlib import Path

import logging
import time
from dataclasses import dataclass, field

from shared.schemas import RejectionReason, TaskPlan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_ACTIONS: set[str] = {
    # Weekly report workflow
    "scan_directory",
    "generate_report",
    "summarise_text",
    "post_summary",
    # Repo analyzer workflow
    "clone_repo",
    "analyze_repo",
    "generate_health_report",
}

DEFAULT_RATE_LIMIT_PER_MINUTE = 10
DEFAULT_MAX_STEPS_PER_PLAN = 20


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------


@dataclass
class FetchPolicy:
    """Configurable policy for the orchestrator."""

    allowed_actions: set[str] = field(
        default_factory=lambda: set(DEFAULT_ALLOWED_ACTIONS)
    )
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    max_steps_per_plan: int = DEFAULT_MAX_STEPS_PER_PLAN

    # simple in-memory sliding-window rate limiter
    _timestamps: dict[str, list[float]] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Public checks
    # ------------------------------------------------------------------

    def check_rate_limit(self, user_id: str) -> RejectionReason | None:
        now = time.time()
        window = self._timestamps.setdefault(user_id, [])
        # prune outside the 60-second window
        self._timestamps[user_id] = [ts for ts in window if now - ts < 60]
        if len(self._timestamps[user_id]) >= self.rate_limit_per_minute:
            logger.warning("Rate limit exceeded for user %s", user_id)
            return RejectionReason.QUOTA_EXCEEDED
        self._timestamps[user_id].append(now)
        return None

    def check_plan(self, plan: TaskPlan) -> RejectionReason | None:
        if len(plan.steps) > self.max_steps_per_plan:
            logger.warning(
                "Plan %s has %d steps (max %d)",
                plan.task_id,
                len(plan.steps),
                self.max_steps_per_plan,
            )
            return RejectionReason.POLICY_VIOLATION

        for step in plan.steps:

            if step.action not in self.allowed_actions:
                logger.warning("Action '%s' not in allowlist", step.action)
                return RejectionReason.ACTION_NOT_ALLOWED

            if step.action == "scan_directory":
             raw_path = step.params.get("path")

             if raw_path:
                 demo_dir = Path("./demo_projects").resolve()
                 requested = Path(raw_path).expanduser().resolve()

                 try:
                    requested.relative_to(demo_dir)
                 except ValueError:
                    logger.warning("Path '%s' outside demo sandbox", requested)
                    return RejectionReason.PATH_NOT_ALLOWED
        return None

    def validate(self, user_id: str, plan: TaskPlan) -> RejectionReason | None:
        """Run all policy checks.  Returns *None* on success."""
        return self.check_rate_limit(user_id) or self.check_plan(plan)
