"""
Objective → TaskPlan planner.

Uses ASI:One LLM (https://docs.asi1.ai) for intelligent objective parsing
when available.  Falls back to keyword matching if the API key is missing
or the call fails.

Reference:  https://docs.asi1.ai/documentation/getting-started/overview
"""

from __future__ import annotations

import json
import logging
import os
import re

from shared.schemas import StepType, TaskConstraints, TaskPlan, TaskStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ASI:One LLM client (lazy-initialised)
# ---------------------------------------------------------------------------

_ASI_ONE_API_KEY = os.getenv("ASI_ONE_API_KEY", "")
_ASI_ONE_BASE_URL = os.getenv("ASI_ONE_BASE_URL", "https://api.asi1.ai/v1")
_ASI_ONE_MODEL = os.getenv("ASI_ONE_MODEL", "asi1")

_openai_client = None


def _get_llm_client():
    """Return an OpenAI-compatible client pointed at ASI:One, or None."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    if not _ASI_ONE_API_KEY:
        return None
    try:
        from openai import OpenAI

        _openai_client = OpenAI(
            api_key=_ASI_ONE_API_KEY,
            base_url=_ASI_ONE_BASE_URL,
        )
        logger.info("ASI:One LLM client initialised (%s)", _ASI_ONE_BASE_URL)
        return _openai_client
    except Exception as exc:
        logger.warning("Failed to initialise ASI:One LLM client: %s", exc)
        return None


# ---------------------------------------------------------------------------
# LLM-based planner
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a task planner for the OpenClaw execution system.
Given a user objective, produce a JSON task plan with the following structure:

{
  "steps": [
    {
      "type": "local" or "external",
      "action": "<action_name>",
      "params": { ... }
    }
  ],
  "constraints": {
    "no_delete": true,
    "require_user_confirmation": true
  }
}

Available LOCAL actions:

  WEEKLY REPORT WORKFLOW:
  - scan_directory: params {"path": "./demo_projects"} (always use ./demo_projects)
  - generate_report: params {"format": "pdf"|"markdown"|"text"}
  - summarise_text: params {"text": "<text_to_summarise>"}

  GITHUB REPO HEALTH ANALYZER:
  - clone_repo: params {"url": "<github_https_url>"}
  - analyze_repo: params {} (uses output of clone_repo)
  - generate_health_report: params {} (uses output of analyze_repo)

Available EXTERNAL actions:
  - post_summary: params {"target": "slack"|"email"}

Rules:
  - ONLY output valid JSON, no explanation or markdown.
  - Choose the most appropriate actions for the objective.
  - Use "local" type for local file/data operations.
  - Use "external" type for sending/posting/sharing.
  - Always set no_delete: true and require_user_confirmation: true.
  - ALWAYS use "./demo_projects" as the path for scan_directory. Never use real user paths.
  - For GitHub repo analysis: use clone_repo, then analyze_repo, then generate_health_report.
  - The URL for clone_repo must be a public GitHub HTTPS URL (https://github.com/owner/repo).
  - Extract the GitHub URL from the user's message if present.
"""


def _plan_with_llm(objective: str) -> TaskPlan | None:
    """Attempt to plan using ASI:One LLM. Returns None on failure."""
    client = _get_llm_client()
    if client is None:
        return None

    try:
        response = client.chat.completions.create(
            model=_ASI_ONE_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": objective},
            ],
            temperature=0.1,
            max_tokens=512,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        plan_data = json.loads(raw)

        steps = []
        for s in plan_data.get("steps", []):
            steps.append(
                TaskStep(
                    type=StepType(s.get("type", "local")),
                    action=s["action"],
                    params=s.get("params", {}),
                )
            )

        if not steps:
            logger.warning("LLM returned zero steps — falling back to keywords")
            return None

        constraints_data = plan_data.get("constraints", {})
        constraints = TaskConstraints(
            no_delete=constraints_data.get("no_delete", True),
            require_user_confirmation=constraints_data.get(
                "require_user_confirmation", True
            ),
        )

        plan = TaskPlan(steps=steps, constraints=constraints)
        logger.info(
            "LLM planned task %s with %d steps for: %.60s…",
            plan.task_id,
            len(steps),
            objective,
        )
        return plan

    except Exception as exc:
        logger.warning(
            "ASI:One LLM planning failed: %s — falling back to keywords", exc
        )
        return None


# ---------------------------------------------------------------------------
# Keyword → step templates (fallback)
# ---------------------------------------------------------------------------

_REPORT_KEYWORDS = re.compile(
    r"\b(report|summary|summarise|summarize|digest|weekly|daily)\b", re.I
)
_SCAN_KEYWORDS = re.compile(r"\b(scan|list|find|search|directory|project)\b", re.I)
_POST_KEYWORDS = re.compile(r"\b(post|send|publish|share|slack|email|notify)\b", re.I)
_GITHUB_URL_RE = re.compile(r"https://github\.com/[\w.\-]+/[\w.\-]+")
_REPO_ANALYZE_KEYWORDS = re.compile(
    r"\b(analyze|analyse|review|audit|health|check|score|inspect)\b", re.I
)


def _extract_github_url(text: str) -> str | None:
    """Extract the first GitHub URL from the text."""
    match = _GITHUB_URL_RE.search(text)
    if match:
        url = match.group(0).rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        return url
    return None


def _plan_with_keywords(objective: str) -> TaskPlan:
    """Keyword-based fallback planner (no LLM required)."""
    steps: list[TaskStep] = []

    # Check for GitHub repo analysis first
    github_url = _extract_github_url(objective)
    if github_url:
        # GitHub Repo Health Analyzer workflow
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="clone_repo",
                params={"url": github_url},
            )
        )
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="analyze_repo",
                params={},
            )
        )
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="generate_health_report",
                params={},
            )
        )
        # Plan done for repo analysis
        plan = TaskPlan(
            steps=steps,
            constraints=TaskConstraints(
                no_delete=True,
                require_user_confirmation=True,
            ),
        )
        logger.info(
            "Keyword-planned repo analysis %s for: %.60s...",
            plan.task_id,
            objective,
        )
        return plan

    # Also match "analyze repo" style without URL (ask for it)
    if (
        _REPO_ANALYZE_KEYWORDS.search(objective)
        and re.search(r"\brepo\b", objective, re.I)
        and not github_url
    ):
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="clone_repo",
                params={"url": ""},  # will prompt for URL
            )
        )
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="analyze_repo",
                params={},
            )
        )
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="generate_health_report",
                params={},
            )
        )
        plan = TaskPlan(
            steps=steps,
            constraints=TaskConstraints(no_delete=True, require_user_confirmation=True),
        )
        logger.info("Keyword-planned repo analysis (no URL) %s", plan.task_id)
        return plan

    # 1. Scanning step
    if _SCAN_KEYWORDS.search(objective):
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="scan_directory",
                params={"path": "./demo_projects"},
            )
        )

    # 2. Report generation step
    if _REPORT_KEYWORDS.search(objective):
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="generate_report",
                params={"format": "pdf"},
            )
        )

    # 3. External posting step
    if _POST_KEYWORDS.search(objective):
        target = "slack"
        if re.search(r"\bemail\b", objective, re.I):
            target = "email"
        steps.append(
            TaskStep(
                type=StepType.EXTERNAL,
                action="post_summary",
                params={"target": target},
            )
        )

    # Fallback -- generic summarise
    if not steps:
        steps.append(
            TaskStep(
                type=StepType.LOCAL,
                action="summarise_text",
                params={"text": objective},
            )
        )

    plan = TaskPlan(
        steps=steps,
        constraints=TaskConstraints(
            no_delete=True,
            require_user_confirmation=True,
        ),
    )
    logger.info(
        "Keyword-planned task %s with %d steps for: %.60s…",
        plan.task_id,
        len(steps),
        objective,
    )
    return plan


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def plan_objective(objective: str) -> TaskPlan:
    """
    Convert a natural-language *objective* into a :class:`TaskPlan`.

    Strategy:
      1. Try ASI:One LLM for intelligent planning
      2. Fall back to keyword matching if LLM unavailable or fails
    """
    # Try LLM first
    plan = _plan_with_llm(objective)
    
    if plan is not None:

        for step in plan.steps:
            if step.action == "scan_directory":
                step.params["path"] = "./demo_projects"

        return plan

    # Fallback to keywords
    return _plan_with_keywords(objective)
