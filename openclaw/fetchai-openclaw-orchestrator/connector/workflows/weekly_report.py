"""
Weekly report workflow – the MVP demo workflow.

Implements the three actions referenced in the design document:
  1. scan_directory  – list recent git activity under a path
  2. generate_report – compile findings into a text/PDF report
  3. post_summary    – (stub) post a summary to an external target

All actions are *local-only* and run under the user's OS permissions.

**Security**: By default, scans the demo_projects directory (not real
user directories).  Set ``DEMO_PROJECTS_DIR`` in .env to control
the scan target.
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from shared.paths import normalize_scan_directory_path

logger = logging.getLogger(__name__)

# Default scan path — uses demo directory to avoid leaking real data
_DEFAULT_SCAN_PATH = os.getenv("DEMO_PROJECTS_DIR", "./demo_projects")


# ---------------------------------------------------------------------------
# 1. scan_directory
# ---------------------------------------------------------------------------


def scan_directory(params: dict[str, Any]) -> dict[str, Any]:
    """
    Walk *path* looking for git repos and gather recent commit messages
    from the last 7 days.

    Defaults to the demo projects directory for safe testing.
    """
    raw_path = params.get("path", _DEFAULT_SCAN_PATH)
    resolved_path = normalize_scan_directory_path(str(raw_path))
    if str(raw_path) != resolved_path:
        logger.info(
            "scan_directory path normalized from %s to %s",
            raw_path,
            resolved_path,
        )

    root = Path(resolved_path).resolve()

    if not root.exists():
        return {"error": f"Path does not exist: {root}", "scanned_path": str(root)}

    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    repos: list[dict[str, Any]] = []

    for candidate in sorted(root.iterdir()):
        git_dir = candidate / ".git"
        if not git_dir.is_dir():
            continue

        try:
            result = subprocess.run(
                ["git", "-C", str(candidate), "log", f"--since={since}", "--oneline"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            commits = [
                line.strip()
                for line in result.stdout.strip().splitlines()
                if line.strip()
            ]
            repos.append({"repo": candidate.name, "commits": commits})
        except Exception as exc:
            repos.append({"repo": candidate.name, "error": str(exc)})

    return {"root": str(root), "repos": repos, "since": since}


# ---------------------------------------------------------------------------
# 2. generate_report
# ---------------------------------------------------------------------------


def generate_report(
    params: dict[str, Any], scan_output: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Build a plain-text report from scan results.

    A real implementation would generate a PDF; for the MVP we produce
    a Markdown string and optionally write it to disk.
    """
    fmt = params.get("format", "text")
    repos = (scan_output or {}).get("repos", [])
    since = (scan_output or {}).get("since", "N/A")

    lines = [
        "# Weekly Dev Report",
        f"**Period**: {since} → {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
    ]

    if not repos:
        lines.append("_No repositories found or no commits in the period._")
    else:
        for repo in repos:
            lines.append(f"## {repo['repo']}")
            if "error" in repo:
                lines.append(f"  ⚠️  {repo['error']}")
            elif repo.get("commits"):
                for c in repo["commits"]:
                    lines.append(f"  - {c}")
            else:
                lines.append("  _No commits this week._")
            lines.append("")

    report_text = "\n".join(lines)

    # Persist report to the demo/output directory
    report_path: str | None = None
    output_dir = Path(_DEFAULT_SCAN_PATH).resolve()
    if output_dir.exists():
        report_file = (
            output_dir
            / f"weekly_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
        )
        report_file.write_text(report_text)
        report_path = str(report_file)
        logger.info("Report written to %s", report_path)

    return {
        "report_text": report_text,
        "report_path": report_path,
        "format": fmt,
    }


# ---------------------------------------------------------------------------
# 3. post_summary  (stub)
# ---------------------------------------------------------------------------


def post_summary(
    params: dict[str, Any], report_output: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Post a summary to an external target.

    This is a **stub** for the MVP – it logs the intent but does not
    actually call Slack / email APIs.
    """
    target = params.get("target", "slack")
    summary = (report_output or {}).get("report_text", "")[:500]

    logger.info("POST_SUMMARY [stub] target=%s summary_length=%d", target, len(summary))

    return {
        "target": target,
        "posted": False,
        "stub": True,
        "summary": summary,
        "message": f"Summary ready for {target} (integration not configured).",
    }
