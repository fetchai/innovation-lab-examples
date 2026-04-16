#!/usr/bin/env python3
"""
Set up a demo projects directory with fake git repos for testing.

This creates a safe, isolated test environment so the weekly report
workflow never touches real system directories or git history.

Run:
    python scripts/setup_demo.py
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_projects"

# Fake repos with sample commit messages
FAKE_REPOS = {
    "weather-agent": [
        "feat: add temperature forecasting endpoint",
        "fix: handle missing API key gracefully",
        "docs: update README with setup instructions",
        "refactor: extract weather parser into module",
        "test: add unit tests for forecast engine",
    ],
    "marketplace-ui": [
        "feat: implement agent search page",
        "style: update card layout for agent listings",
        "fix: pagination off-by-one error",
        "chore: upgrade dependencies to latest",
    ],
    "data-pipeline": [
        "feat: add CSV export for reports",
        "feat: implement daily aggregation task",
        "fix: timezone handling in scheduler",
    ],
}


def create_demo_repos():
    """Create fake git repos with sample commits."""
    DEMO_DIR.mkdir(exist_ok=True)

    for repo_name, commits in FAKE_REPOS.items():
        repo_path = DEMO_DIR / repo_name

        if repo_path.exists():
            print(f"  ⏭  {repo_name} already exists — skipping")
            continue

        repo_path.mkdir(parents=True)

        # Init git repo
        subprocess.run(
            ["git", "init"],
            cwd=str(repo_path),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "demo@example.com"],
            cwd=str(repo_path),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Demo User"],
            cwd=str(repo_path),
            capture_output=True,
            check=True,
        )

        # Create commits (backdated within the last 7 days)
        now = datetime.now(timezone.utc)
        for i, message in enumerate(commits):
            # Spread commits over the last 7 days
            commit_date = now - timedelta(days=6 - i, hours=10 - i)
            date_str = commit_date.strftime("%Y-%m-%dT%H:%M:%S%z")
            if not date_str.endswith("+0000"):
                date_str = commit_date.strftime("%Y-%m-%dT%H:%M:%S+0000")

            # Create a dummy file change for each commit
            dummy = repo_path / f"file_{i}.txt"
            dummy.write_text(f"# {message}\n")

            subprocess.run(
                ["git", "add", "."],
                cwd=str(repo_path),
                capture_output=True,
                check=True,
            )

            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = date_str
            env["GIT_COMMITTER_DATE"] = date_str

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(repo_path),
                capture_output=True,
                check=True,
                env=env,
            )

        print(f"  ✅ {repo_name} — {len(commits)} commits")

    print(f"\nDemo directory: {DEMO_DIR}")


if __name__ == "__main__":
    print("Setting up demo projects directory…\n")
    create_demo_repos()
    print("\n✅ Done! Use DEMO_PROJECTS_DIR=./demo_projects to test workflows.")
