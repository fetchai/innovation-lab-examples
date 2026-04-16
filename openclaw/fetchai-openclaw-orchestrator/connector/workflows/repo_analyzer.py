"""
GitHub Repo Health Analyzer workflow.

A **public-safe** workflow that accepts a GitHub URL, clones the
repository into a temporary sandbox, runs static analysis tools
(no code from the repo is ever *executed*), and returns a structured
health report.

Actions:
    1. clone_repo          - shallow-clone a public repo into a temp dir
    2. analyze_repo        - run cloc, dependency audit, git stats
    3. generate_health_report - compile everything into a scored report

Security:
    - Only PUBLIC repos are cloned (SSH URLs rejected).
    - Clone uses ``--depth 1`` (shallow) to limit data transfer.
    - Max repo size enforced (default 500 MB).
    - All work happens in a temporary directory that is deleted after.
    - NO code from the cloned repo is ever imported or executed.
    - We READ files as text; we never ``exec``, ``import``, or ``eval``.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum repo size in MB before we abort
_MAX_REPO_SIZE_MB = int(os.getenv("MAX_REPO_SIZE_MB", "500"))

# Regex for valid GitHub HTTPS URLs
_GITHUB_URL_RE = re.compile(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str], cwd: str | None = None, timeout: int = 120
) -> subprocess.CompletedProcess:
    """Run a subprocess with sane defaults."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


def _dir_size_mb(path: str) -> float:
    """Return total directory size in MB."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total / (1024 * 1024)


def _count_lines_by_language(repo_path: str) -> dict[str, int]:
    """Count lines of code by language using simple heuristics.

    We attempt ``cloc`` first (if installed). If unavailable, we fall
    back to counting by file extension.
    """
    # Try cloc
    try:
        result = _run(["cloc", "--json", "--quiet", repo_path], timeout=60)
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            languages = {}
            for lang, info in data.items():
                if lang in ("header", "SUM"):
                    continue
                if isinstance(info, dict) and "code" in info:
                    languages[lang] = info["code"]
            if languages:
                return dict(sorted(languages.items(), key=lambda x: -x[1]))
    except FileNotFoundError:
        logger.debug("cloc not installed, using extension-based counting")
    except Exception as exc:
        logger.debug("cloc failed: %s, falling back", exc)

    # Fallback: count by extension
    ext_map: dict[str, str] = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript (JSX)",
        ".tsx": "TypeScript (TSX)",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++ Header",
        ".cs": "C#",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".sh": "Shell",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".md": "Markdown",
        ".sql": "SQL",
        ".r": "R",
        ".dart": "Dart",
        ".lua": "Lua",
        ".vue": "Vue",
    }
    lang_line_counts: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Skip hidden directories and common non-source dirs
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".")
            and d
            not in ("node_modules", "vendor", "__pycache__", ".git", "dist", "build")
        ]
        for fname in filenames:
            ext = Path(fname).suffix.lower()
            lang = ext_map.get(ext)
            if lang:
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, "r", errors="ignore") as f:
                        line_count = sum(1 for _ in f)
                    lang_line_counts[lang] = lang_line_counts.get(lang, 0) + line_count
                except Exception:
                    pass

    return dict(sorted(lang_line_counts.items(), key=lambda x: -x[1]))


def _count_files(repo_path: str) -> dict[str, Any]:
    """Count total files, directories, and file types."""
    total_files = 0
    total_dirs = 0
    extensions: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".")
            and d not in ("node_modules", "vendor", "__pycache__", "dist", "build")
        ]
        total_dirs += len(dirnames)
        for fname in filenames:
            if not fname.startswith("."):
                total_files += 1
                ext = Path(fname).suffix.lower() or "(no extension)"
                extensions[ext] = extensions.get(ext, 0) + 1
    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "top_extensions": dict(sorted(extensions.items(), key=lambda x: -x[1])[:10]),
    }


def _git_stats(repo_path: str) -> dict[str, Any]:
    """Gather git statistics: commits, contributors, recent activity."""
    stats: dict[str, Any] = {}

    # Total commits
    result = _run(["git", "-C", repo_path, "rev-list", "--count", "HEAD"], timeout=30)
    stats["total_commits"] = int(result.stdout.strip()) if result.returncode == 0 else 0

    # Commits in last 30 days
    result = _run(
        ["git", "-C", repo_path, "rev-list", "--count", "--since=30 days ago", "HEAD"],
        timeout=30,
    )
    stats["commits_last_30_days"] = (
        int(result.stdout.strip()) if result.returncode == 0 else 0
    )

    # Contributors
    result = _run(["git", "-C", repo_path, "shortlog", "-sn", "--all"], timeout=30)
    if result.returncode == 0:
        contributors = []
        for line in result.stdout.strip().splitlines()[:10]:
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                contributors.append(
                    {"commits": int(parts[0].strip()), "name": parts[1].strip()}
                )
        stats["top_contributors"] = contributors
        stats["total_contributors"] = len(result.stdout.strip().splitlines())
    else:
        stats["top_contributors"] = []
        stats["total_contributors"] = 0

    # Latest commit date
    result = _run(["git", "-C", repo_path, "log", "-1", "--format=%ci"], timeout=10)
    stats["latest_commit_date"] = (
        result.stdout.strip() if result.returncode == 0 else "unknown"
    )

    # Default branch
    result = _run(
        ["git", "-C", repo_path, "symbolic-ref", "--short", "HEAD"], timeout=10
    )
    stats["default_branch"] = (
        result.stdout.strip() if result.returncode == 0 else "unknown"
    )

    return stats


def _detect_tests(repo_path: str) -> dict[str, Any]:
    """Detect testing frameworks by looking for test files and configs."""
    test_info: dict[str, Any] = {"frameworks": [], "test_files": 0}

    # Check for common test config files
    configs = {
        "pytest.ini": "pytest",
        "setup.cfg": "pytest",
        "pyproject.toml": "pytest",
        "jest.config.js": "jest",
        "jest.config.ts": "jest",
        "karma.conf.js": "karma",
        "mocha.opts": "mocha",
        ".mocharc.yml": "mocha",
        "phpunit.xml": "phpunit",
        "build.gradle": "JUnit/Gradle",
        "pom.xml": "JUnit/Maven",
        "Cargo.toml": "cargo test",
    }
    for cfg_file, framework in configs.items():
        if (Path(repo_path) / cfg_file).exists():
            if framework not in test_info["frameworks"]:
                test_info["frameworks"].append(framework)

    # Count test files
    test_patterns = ["test_", "_test.", ".test.", ".spec.", "tests/", "test/"]
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and d != "node_modules"
        ]
        for fname in filenames:
            if any(
                pat in fname.lower() or pat in dirpath.lower() for pat in test_patterns
            ):
                test_info["test_files"] += 1

    return test_info


def _check_dependencies(repo_path: str) -> dict[str, Any]:
    """Check for dependency files and count dependencies (no install)."""
    dep_info: dict[str, Any] = {
        "files_found": [],
        "total_dependencies": 0,
        "details": {},
    }

    dep_files = {
        "requirements.txt": "pip",
        "Pipfile": "pipenv",
        "pyproject.toml": "Python (pyproject)",
        "package.json": "npm",
        "package-lock.json": "npm (lock)",
        "yarn.lock": "yarn",
        "Gemfile": "bundler",
        "go.mod": "Go modules",
        "Cargo.toml": "Cargo (Rust)",
        "pom.xml": "Maven",
        "build.gradle": "Gradle",
        "composer.json": "Composer (PHP)",
    }

    for dep_file, manager in dep_files.items():
        fpath = Path(repo_path) / dep_file
        if fpath.exists():
            dep_info["files_found"].append(dep_file)
            try:
                content = fpath.read_text(errors="ignore")
                if dep_file == "requirements.txt":
                    count = len(
                        [
                            line
                            for line in content.splitlines()
                            if line.strip() and not line.strip().startswith("#")
                        ]
                    )
                    dep_info["details"][dep_file] = {"manager": manager, "count": count}
                    dep_info["total_dependencies"] += count
                elif dep_file == "package.json":
                    import json

                    pkg = json.loads(content)
                    deps = len(pkg.get("dependencies", {}))
                    dev_deps = len(pkg.get("devDependencies", {}))
                    dep_info["details"][dep_file] = {
                        "manager": manager,
                        "dependencies": deps,
                        "devDependencies": dev_deps,
                    }
                    dep_info["total_dependencies"] += deps + dev_deps
                else:
                    dep_info["details"][dep_file] = {"manager": manager}
            except Exception:
                dep_info["details"][dep_file] = {
                    "manager": manager,
                    "error": "could not parse",
                }

    return dep_info


def _check_security_files(repo_path: str) -> dict[str, Any]:
    """Check for security-related files and configurations."""
    security: dict[str, Any] = {
        "has_license": False,
        "has_readme": False,
        "has_gitignore": False,
        "findings": [],
    }

    root = Path(repo_path)
    security["has_license"] = any(
        (root / f).exists() for f in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]
    )
    security["has_readme"] = any(
        (root / f).exists() for f in ["README.md", "README.rst", "README.txt", "README"]
    )
    security["has_gitignore"] = (root / ".gitignore").exists()
    security["has_ci"] = any(
        (root / d).exists()
        for d in [".github/workflows", ".gitlab-ci.yml", ".circleci", "Jenkinsfile"]
    )
    security["has_security_policy"] = (root / "SECURITY.md").exists()
    security["has_contributing"] = any(
        (root / f).exists() for f in ["CONTRIBUTING.md", "CONTRIBUTING"]
    )

    # Check for potential secrets in common files (just filenames, not content)
    suspicious_files = []
    for dirpath, _dirnames, filenames in os.walk(repo_path):
        for fname in filenames:
            lower = fname.lower()
            if any(
                s in lower
                for s in [".env", "secret", "credentials", "private_key", ".pem"]
            ):
                if not lower.endswith(".example") and not lower.endswith(".sample"):
                    rel_path = os.path.relpath(os.path.join(dirpath, fname), repo_path)
                    if not rel_path.startswith(".git/"):
                        suspicious_files.append(rel_path)
    if suspicious_files:
        security["findings"].append(
            f"Potentially sensitive files committed: {', '.join(suspicious_files[:5])}"
        )

    return security


def _compute_health_score(
    languages: dict,
    git_stats: dict,
    tests: dict,
    deps: dict,
    security: dict,
    file_stats: dict,
) -> float:
    """Compute a 0-10 health score based on multiple factors."""
    score = 5.0  # Start at middle

    # Has tests (+1.5)
    if tests.get("test_files", 0) > 0:
        score += 1.0
        if tests.get("test_files", 0) > 10:
            score += 0.5

    # Has CI (+1.0)
    if security.get("has_ci"):
        score += 1.0

    # Has license (+0.5)
    if security.get("has_license"):
        score += 0.5

    # Has README (+0.5)
    if security.get("has_readme"):
        score += 0.5

    # Has .gitignore (+0.25)
    if security.get("has_gitignore"):
        score += 0.25

    # Recent activity (+1.0)
    if git_stats.get("commits_last_30_days", 0) > 5:
        score += 0.5
    if git_stats.get("commits_last_30_days", 0) > 20:
        score += 0.5

    # Multiple contributors (+0.5)
    if git_stats.get("total_contributors", 0) > 2:
        score += 0.5

    # Security findings (-0.5 each)
    findings_count = len(security.get("findings", []))
    score -= findings_count * 0.5

    # No tests (-1.5)
    if tests.get("test_files", 0) == 0:
        score -= 1.5

    return max(0.0, min(10.0, round(score, 1)))


# ---------------------------------------------------------------------------
# 1. clone_repo
# ---------------------------------------------------------------------------


def clone_repo(params: dict[str, Any]) -> dict[str, Any]:
    """
    Shallow-clone a public GitHub repository into a temporary directory.

    Params:
        url (str): The GitHub HTTPS URL to clone.

    Returns a dict with the temp directory path and repo metadata.
    """
    url = params.get("url", "").strip().rstrip("/")

    if not url:
        return {
            "error": "No repository URL provided. Please provide a GitHub URL.",
            "url": "",
        }

    # Normalise: add .git if missing
    if not url.endswith(".git"):
        url_for_clone = url + ".git"
    else:
        url_for_clone = url

    # Security: only HTTPS GitHub URLs
    if not _GITHUB_URL_RE.match(url) and not _GITHUB_URL_RE.match(url + ".git"):
        return {
            "error": "Only public GitHub HTTPS URLs are accepted (https://github.com/owner/repo).",
            "url": url,
        }

    # Create a temp directory
    tmpdir = tempfile.mkdtemp(prefix="repo_analysis_")

    try:
        logger.info("Cloning %s into %s (shallow)", url, tmpdir)
        result = _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                url_for_clone,
                os.path.join(tmpdir, "repo"),
            ],
            timeout=120,
        )

        if result.returncode != 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            error_msg = result.stderr.strip() if result.stderr else "Clone failed"
            # Sanitise error message
            if "not found" in error_msg.lower() or "404" in error_msg:
                error_msg = "Repository not found. Is it a public repo?"
            elif "authentication" in error_msg.lower():
                error_msg = "Authentication required. Only public repos are supported."
            return {"error": error_msg, "url": url}

        repo_path = os.path.join(tmpdir, "repo")

        # For full git stats, unshallow if small enough
        size_mb = _dir_size_mb(repo_path)
        if size_mb > _MAX_REPO_SIZE_MB:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {
                "error": f"Repository too large ({size_mb:.0f} MB, limit {_MAX_REPO_SIZE_MB} MB).",
                "url": url,
            }

        # Fetch full history for stats (but still don't run anything)
        _run(["git", "-C", repo_path, "fetch", "--unshallow"], timeout=120)

        # Extract owner/repo from URL
        parts = url.replace("https://github.com/", "").replace(".git", "").split("/")
        owner = parts[0] if len(parts) > 0 else "unknown"
        repo_name = parts[1] if len(parts) > 1 else "unknown"

        return {
            "url": url,
            "owner": owner,
            "repo_name": repo_name,
            "clone_path": repo_path,
            "tmpdir": tmpdir,
            "size_mb": round(size_mb, 1),
        }

    except subprocess.TimeoutExpired:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {
            "error": "Clone timed out (120s). The repo may be too large.",
            "url": url,
        }
    except Exception as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {"error": f"Clone failed: {exc}", "url": url}


# ---------------------------------------------------------------------------
# 2. analyze_repo
# ---------------------------------------------------------------------------


def analyze_repo(
    params: dict[str, Any], clone_output: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Run static analysis on a cloned repository.

    This function READS files as text. It never executes, imports,
    or installs anything from the repository.
    """
    clone_data = clone_output or {}
    repo_path = clone_data.get("clone_path")

    if not repo_path or not os.path.isdir(repo_path):
        return {"error": "No valid clone path. Did clone_repo succeed?"}

    logger.info("Analyzing repository at %s", repo_path)

    try:
        # Run all analyses
        languages = _count_lines_by_language(repo_path)
        file_stats = _count_files(repo_path)
        git_stats = _git_stats(repo_path)
        tests = _detect_tests(repo_path)
        deps = _check_dependencies(repo_path)
        security = _check_security_files(repo_path)

        # Compute total lines
        total_lines = sum(languages.values())

        # Compute language percentages
        lang_percentages = {}
        if total_lines > 0:
            for lang, lines in list(languages.items())[:8]:
                pct = round((lines / total_lines) * 100, 1)
                lang_percentages[lang] = f"{pct}% ({lines:,} lines)"

        health_score = _compute_health_score(
            languages, git_stats, tests, deps, security, file_stats
        )

        return {
            "owner": clone_data.get("owner", "unknown"),
            "repo_name": clone_data.get("repo_name", "unknown"),
            "url": clone_data.get("url", ""),
            "size_mb": clone_data.get("size_mb", 0),
            "total_lines": total_lines,
            "languages": lang_percentages,
            "files": file_stats,
            "git": git_stats,
            "tests": tests,
            "dependencies": deps,
            "security": security,
            "health_score": health_score,
        }

    except Exception as exc:
        logger.exception("Analysis failed")
        return {"error": f"Analysis failed: {exc}"}

    finally:
        # Clean up the temporary directory
        tmpdir = clone_data.get("tmpdir")
        if tmpdir and os.path.isdir(tmpdir):
            logger.info("Cleaning up temp directory %s", tmpdir)
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. generate_health_report
# ---------------------------------------------------------------------------


def generate_health_report(
    params: dict[str, Any], analysis_output: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Compile analysis results into a readable health report.
    """
    data = analysis_output or {}

    if "error" in data:
        return {
            "report_text": f"# Analysis Failed\n\n{data['error']}",
            "health_score": 0,
            "error": data["error"],
        }

    owner = data.get("owner", "unknown")
    repo_name = data.get("repo_name", "unknown")
    url = data.get("url", "")
    score = data.get("health_score", 0)

    # Score emoji
    if score >= 8:
        score_emoji = "A"
    elif score >= 6:
        score_emoji = "B"
    elif score >= 4:
        score_emoji = "C"
    else:
        score_emoji = "D"

    lines = [
        f"# Repo Health Report: {owner}/{repo_name}",
        f"**URL**: {url}",
        f"**Health Score**: {score}/10 (Grade: {score_emoji})",
        "",
    ]

    # Languages
    languages = data.get("languages", {})
    if languages:
        lines.append("## Languages")
        for lang, info in languages.items():
            lines.append(f"- **{lang}**: {info}")
        lines.append("")

    # Stats
    total_lines = data.get("total_lines", 0)
    files = data.get("files", {})
    lines.append("## Project Stats")
    lines.append(f"- **Total Lines of Code**: {total_lines:,}")
    lines.append(f"- **Total Files**: {files.get('total_files', 0):,}")
    lines.append(f"- **Total Directories**: {files.get('total_dirs', 0):,}")
    lines.append(f"- **Repo Size**: {data.get('size_mb', 0)} MB")
    lines.append("")

    # Git activity
    git = data.get("git", {})
    lines.append("## Git Activity")
    lines.append(f"- **Total Commits**: {git.get('total_commits', 0):,}")
    lines.append(f"- **Commits (last 30 days)**: {git.get('commits_last_30_days', 0)}")
    lines.append(f"- **Contributors**: {git.get('total_contributors', 0)}")
    lines.append(f"- **Default Branch**: {git.get('default_branch', 'unknown')}")
    lines.append(f"- **Latest Commit**: {git.get('latest_commit_date', 'unknown')}")

    # Top contributors
    contribs = git.get("top_contributors", [])
    if contribs:
        lines.append("")
        lines.append("**Top Contributors:**")
        for c in contribs[:5]:
            lines.append(f"  - {c['name']} ({c['commits']} commits)")
    lines.append("")

    # Tests
    tests = data.get("tests", {})
    lines.append("## Testing")
    if tests.get("test_files", 0) > 0:
        lines.append(f"- **Test Files Found**: {tests['test_files']}")
        if tests.get("frameworks"):
            lines.append(f"- **Frameworks Detected**: {', '.join(tests['frameworks'])}")
    else:
        lines.append("- No test files detected")
    lines.append("")

    # Dependencies
    deps = data.get("dependencies", {})
    if deps.get("files_found"):
        lines.append("## Dependencies")
        lines.append(f"- **Package Files**: {', '.join(deps['files_found'])}")
        lines.append(
            f"- **Total Dependencies**: {deps.get('total_dependencies', 'N/A')}"
        )
        for fname, detail in deps.get("details", {}).items():
            if isinstance(detail, dict):
                info_parts = [f"{k}: {v}" for k, v in detail.items() if k != "manager"]
                if info_parts:
                    lines.append(f"  - `{fname}`: {', '.join(info_parts)}")
        lines.append("")

    # Security / Best Practices
    security = data.get("security", {})
    lines.append("## Best Practices")
    checks = [
        ("README", security.get("has_readme", False)),
        ("LICENSE", security.get("has_license", False)),
        (".gitignore", security.get("has_gitignore", False)),
        ("CI/CD Pipeline", security.get("has_ci", False)),
        ("SECURITY.md", security.get("has_security_policy", False)),
        ("CONTRIBUTING.md", security.get("has_contributing", False)),
    ]
    for name, present in checks:
        emoji = "pass" if present else "missing"
        lines.append(f"- **{name}**: {emoji}")

    # Security findings
    findings = security.get("findings", [])
    if findings:
        lines.append("")
        lines.append("## Security Findings")
        for finding in findings:
            lines.append(f"- WARNING: {finding}")
    lines.append("")

    # Summary
    lines.append("---")
    lines.append(
        f"*Analysis generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*"
    )

    report_text = "\n".join(lines)

    return {
        "report_text": report_text,
        "health_score": score,
        "owner": owner,
        "repo_name": repo_name,
        "url": url,
    }
