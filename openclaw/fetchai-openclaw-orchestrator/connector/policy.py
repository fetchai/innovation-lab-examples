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

from shared.paths import default_allowed_scan_paths
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


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass
class LocalPolicy:
    """Execution-time policy checked by the connector."""

    allowed_actions: set[str] = field(
        default_factory=lambda: set(DEFAULT_ALLOWED_ACTIONS)
    )
    allowed_paths: list[str] = field(default_factory=default_allowed_scan_paths)
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
        if step.action != "scan_directory":
            return None

        raw_path = step.params.get("path")
        if raw_path is None:
            return None

        resolved = str(Path(os.path.expanduser(str(raw_path))).resolve())
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
