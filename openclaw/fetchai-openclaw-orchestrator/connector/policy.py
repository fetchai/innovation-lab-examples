"""
Local execution policy engine for the OpenClaw Connector.

Enforces execution-time rules:
  • Path sandboxing
  • Action allowlist
  • Confirmation requirements
  • No background execution
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from shared.schemas import RejectionReason, TaskPlan, TaskStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
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

_DEMO_DIR = os.getenv("DEMO_PROJECTS_DIR", "./demo_projects")

DEFAULT_ALLOWED_PATHS: list[str] = [
    os.path.expanduser("~/projects"),
    os.path.expanduser("~/Documents"),
    "/tmp",
    str(Path(_DEMO_DIR).resolve()),  # demo directory (safe testing)
    str(Path(".").resolve()),  # current working directory
]


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass
class LocalPolicy:
    """Execution-time policy checked by the connector."""

    allowed_actions: set[str] = field(
        default_factory=lambda: set(DEFAULT_ALLOWED_ACTIONS)
    )
    allowed_paths: list[str] = field(
        default_factory=lambda: list(DEFAULT_ALLOWED_PATHS)
    )
    require_user_confirmation: bool = True
    allow_background_execution: bool = False

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_action(self, step: TaskStep) -> RejectionReason | None:
        if step.action not in self.allowed_actions:
            logger.warning("Action '%s' not in local allowlist", step.action)
            return RejectionReason.ACTION_NOT_ALLOWED
        return None

    def check_path(self, step: TaskStep) -> RejectionReason | None:
        raw_path = step.params.get("path")
        if raw_path is None:
            return None  # no path param → OK

        resolved = str(Path(os.path.expanduser(raw_path)).resolve())
        for allowed in self.allowed_paths:
            allowed_resolved = str(Path(allowed).resolve())
            if resolved.startswith(allowed_resolved):
                return None

        logger.warning("Path '%s' not within allowed sandboxes", resolved)
        return RejectionReason.PATH_NOT_ALLOWED

    def validate_plan(self, plan: TaskPlan) -> RejectionReason | None:
        """Run all local policy checks on the plan.  Returns *None* on success."""
        for step in plan.steps:
            rejection = self.check_action(step) or self.check_path(step)
            if rejection is not None:
                return rejection
        return None
