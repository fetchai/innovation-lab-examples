"""Tests for connector.workflows.repo_analyzer -- GitHub repo health analyzer."""

import os
import subprocess

import pytest

from connector.workflows.repo_analyzer import (
    analyze_repo,
    clone_repo,
    generate_health_report,
    _check_dependencies,
    _check_security_files,
    _compute_health_score,
    _count_files,
    _count_lines_by_language,
    _detect_tests,
    _git_stats,
)
from orchestrator.planner import _extract_github_url


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------


class TestExtractGitHubUrl:
    def test_extract_simple_url(self):
        url = _extract_github_url("Analyze https://github.com/fastapi/fastapi")
        assert url == "https://github.com/fastapi/fastapi"

    def test_extract_url_with_git_suffix(self):
        url = _extract_github_url("Check https://github.com/user/repo.git please")
        assert url == "https://github.com/user/repo"

    def test_no_url_returns_none(self):
        url = _extract_github_url("Analyze my local project")
        assert url is None

    def test_non_github_url_ignored(self):
        url = _extract_github_url("Check https://gitlab.com/user/repo")
        assert url is None


# ---------------------------------------------------------------------------
# clone_repo
# ---------------------------------------------------------------------------


class TestCloneRepo:
    def test_missing_url(self):
        result = clone_repo({"url": ""})
        assert "error" in result

    def test_non_github_url_rejected(self):
        result = clone_repo({"url": "https://gitlab.com/user/repo"})
        assert "error" in result
        assert "GitHub" in result["error"]

    def test_ssh_url_rejected(self):
        result = clone_repo({"url": "git@github.com:user/repo.git"})
        assert "error" in result

    def test_nonexistent_repo(self):
        result = clone_repo(
            {"url": "https://github.com/nonexistent-user-xyz/nonexistent-repo-abc"}
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Helper functions with a fake repo
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path):
    """Create a minimal fake git repo with some files for analysis."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    # Init git
    subprocess.run(["git", "init", str(repo_dir)], capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email", "test@test.com"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.name", "Test"], capture_output=True
    )

    # Create source files
    (repo_dir / "main.py").write_text("print('hello')\nx = 1\ny = 2\n")
    (repo_dir / "utils.py").write_text("def helper():\n    return 42\n")
    (repo_dir / "app.js").write_text("console.log('app');\nmodule.exports = {};\n")

    # Create test files
    (repo_dir / "tests").mkdir()
    (repo_dir / "tests" / "test_main.py").write_text(
        "def test_hello():\n    assert True\n"
    )

    # Create config files
    (repo_dir / "README.md").write_text("# Test Repo\nA test repository.\n")
    (repo_dir / "LICENSE").write_text("MIT License\n")
    (repo_dir / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    (repo_dir / "requirements.txt").write_text("flask>=2.0\nrequests\npydantic\n")
    (repo_dir / "pytest.ini").write_text("[pytest]\n")

    # Git commit
    subprocess.run(["git", "-C", str(repo_dir), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_dir), "commit", "-m", "initial commit"],
        capture_output=True,
    )

    return str(repo_dir)


class TestCountLinesByLanguage:
    def test_counts_python(self, fake_repo):
        langs = _count_lines_by_language(fake_repo)
        assert "Python" in langs
        assert langs["Python"] > 0

    def test_counts_javascript(self, fake_repo):
        langs = _count_lines_by_language(fake_repo)
        assert "JavaScript" in langs


class TestCountFiles:
    def test_counts_files(self, fake_repo):
        stats = _count_files(fake_repo)
        assert stats["total_files"] > 0
        assert stats["total_dirs"] >= 0


class TestGitStats:
    def test_git_stats(self, fake_repo):
        stats = _git_stats(fake_repo)
        assert stats["total_commits"] >= 1
        assert stats["total_contributors"] >= 1
        assert stats["default_branch"] in ("main", "master")


class TestDetectTests:
    def test_detects_pytest(self, fake_repo):
        tests = _detect_tests(fake_repo)
        assert "pytest" in tests["frameworks"]
        assert tests["test_files"] >= 1


class TestCheckDependencies:
    def test_finds_requirements(self, fake_repo):
        deps = _check_dependencies(fake_repo)
        assert "requirements.txt" in deps["files_found"]
        assert deps["total_dependencies"] == 3


class TestCheckSecurityFiles:
    def test_finds_common_files(self, fake_repo):
        security = _check_security_files(fake_repo)
        assert security["has_readme"] is True
        assert security["has_license"] is True
        assert security["has_gitignore"] is True


class TestComputeHealthScore:
    def test_score_range(self):
        score = _compute_health_score(
            languages={"Python": 1000},
            git_stats={
                "total_commits": 50,
                "commits_last_30_days": 10,
                "total_contributors": 3,
            },
            tests={"test_files": 5, "frameworks": ["pytest"]},
            deps={"total_dependencies": 5},
            security={
                "has_readme": True,
                "has_license": True,
                "has_gitignore": True,
                "has_ci": True,
                "findings": [],
            },
            file_stats={"total_files": 20},
        )
        assert 0 <= score <= 10

    def test_no_tests_lowers_score(self):
        score_with = _compute_health_score(
            {"Python": 100},
            {"total_commits": 5, "commits_last_30_days": 2, "total_contributors": 1},
            {"test_files": 10, "frameworks": ["pytest"]},
            {},
            {
                "has_readme": True,
                "has_license": True,
                "has_gitignore": True,
                "has_ci": False,
                "findings": [],
            },
            {},
        )
        score_without = _compute_health_score(
            {"Python": 100},
            {"total_commits": 5, "commits_last_30_days": 2, "total_contributors": 1},
            {"test_files": 0},
            {},
            {
                "has_readme": True,
                "has_license": True,
                "has_gitignore": True,
                "has_ci": False,
                "findings": [],
            },
            {},
        )
        assert score_with > score_without


# ---------------------------------------------------------------------------
# analyze_repo
# ---------------------------------------------------------------------------


class TestAnalyzeRepo:
    def test_analyze_fake_repo(self, fake_repo):
        clone_data = {
            "clone_path": fake_repo,
            "tmpdir": None,  # don't clean up our fixture
            "url": "https://github.com/test/repo",
            "owner": "test",
            "repo_name": "repo",
            "size_mb": 0.1,
        }
        result = analyze_repo({}, clone_data)
        assert "error" not in result
        assert result["total_lines"] > 0
        assert result["health_score"] > 0
        assert result["languages"]

    def test_analyze_no_clone(self):
        result = analyze_repo({}, {})
        assert "error" in result


# ---------------------------------------------------------------------------
# generate_health_report
# ---------------------------------------------------------------------------


class TestGenerateHealthReport:
    def test_generates_report(self, fake_repo):
        clone_data = {
            "clone_path": fake_repo,
            "tmpdir": None,
            "url": "https://github.com/test/repo",
            "owner": "test",
            "repo_name": "repo",
            "size_mb": 0.1,
        }
        analysis = analyze_repo({}, clone_data)
        report = generate_health_report({}, analysis)
        assert "report_text" in report
        assert "test/repo" in report["report_text"]
        assert "Health Score" in report["report_text"]

    def test_report_with_error(self):
        report = generate_health_report({}, {"error": "Something went wrong"})
        assert "Failed" in report["report_text"]


# ---------------------------------------------------------------------------
# Planner integration
# ---------------------------------------------------------------------------


class TestPlannerRepoAnalysis:
    def test_plan_with_github_url(self):
        os.environ.pop("ASI_ONE_API_KEY", None)
        from orchestrator.planner import plan_objective

        plan = plan_objective("Analyze https://github.com/fastapi/fastapi")
        actions = [s.action for s in plan.steps]
        assert "clone_repo" in actions
        assert "analyze_repo" in actions
        assert "generate_health_report" in actions

    def test_plan_extracts_url(self):
        os.environ.pop("ASI_ONE_API_KEY", None)
        from orchestrator.planner import plan_objective

        plan = plan_objective("Check the health of https://github.com/user/repo")
        clone_step = [s for s in plan.steps if s.action == "clone_repo"][0]
        assert clone_step.params["url"] == "https://github.com/user/repo"


# ---------------------------------------------------------------------------
# Policy integration
# ---------------------------------------------------------------------------


class TestPolicyRepoActions:
    def test_fetch_policy_allows_repo_actions(self):
        from orchestrator.policy import FetchPolicy
        from shared.schemas import StepType, TaskPlan, TaskStep

        policy = FetchPolicy()
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="clone_repo",
                    params={"url": "https://github.com/a/b"},
                ),
                TaskStep(type=StepType.LOCAL, action="analyze_repo"),
                TaskStep(type=StepType.LOCAL, action="generate_health_report"),
            ]
        )
        assert policy.validate("u_1", plan) is None

    def test_local_policy_allows_repo_actions(self):
        from connector.policy import LocalPolicy
        from shared.schemas import StepType, TaskPlan, TaskStep

        policy = LocalPolicy()
        plan = TaskPlan(
            steps=[
                TaskStep(
                    type=StepType.LOCAL,
                    action="clone_repo",
                    params={"url": "https://github.com/a/b"},
                ),
                TaskStep(type=StepType.LOCAL, action="analyze_repo"),
                TaskStep(type=StepType.LOCAL, action="generate_health_report"),
            ]
        )
        assert policy.validate_plan(plan) is None


# ---------------------------------------------------------------------------
# Executor integration
# ---------------------------------------------------------------------------


class TestExecutorRepoActions:
    def test_executor_has_repo_actions(self):
        from connector.executor import _ACTIONS

        assert "clone_repo" in _ACTIONS
        assert "analyze_repo" in _ACTIONS
        assert "generate_health_report" in _ACTIONS
