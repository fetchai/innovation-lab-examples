"""Offline unit tests for agent.py — no network, no battle.training key.

Run:  python -m pytest tests/ -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent


def test_parser_defaults_to_demo():
    args = agent.build_parser().parse_args([])
    assert args.mode == "demo"
    assert args.controller == "controller.js"
    assert args.label == "v1"
    assert args.vs == "house:hunter"
    assert args.seed is None
    assert args.enrol is None


def test_parser_full_mode_flags():
    args = agent.build_parser().parse_args(
        [
            "--mode",
            "full",
            "--bot",
            "my-bot",
            "--label",
            "v2",
            "--vs",
            "house:brawler",
            "--seed",
            "12345",
            "--enrol",
            "promotedby-cup-nov-2026",
        ]
    )
    assert args.mode == "full"
    assert args.bot == "my-bot"
    assert args.label == "v2"
    assert args.vs == "house:brawler"
    assert args.seed == 12345
    assert args.enrol == "promotedby-cup-nov-2026"


def test_try_json_parses_and_falls_back():
    assert agent.try_json('{"a": 1}') == {"a": 1}
    assert agent.try_json("not json") == "not json"


def test_summarize_bot_with_rating():
    out = agent.summarize_bot(
        {"name": "aralie", "rating": 1161, "wins": 10, "losses": 5, "draws": 2}
    )
    assert "aralie" in out and "1161" in out and "10-5-2" in out


def test_summarize_bot_nested_theaters_shape():
    # Real get_bot shape (verified live 2026-11-19): stats live under
    # theaters.<theater>, not at the top level.
    out = agent.summarize_bot(
        {
            "name": "ephemeral-falconer",
            "theaters": {
                "armor": {
                    "rating": 2578,
                    "wins": 27,
                    "losses": 1,
                    "draws": 5,
                    "rank": 1,
                }
            },
        }
    )
    assert "ephemeral-falconer" in out and "2578" in out and "27-1-5" in out


def test_summarize_bot_unknown_shape_does_not_crash():
    out = agent.summarize_bot({"unexpected": True})
    assert "unexpected" in out


def test_full_mode_requires_key(monkeypatch):
    monkeypatch.delenv("BATTLE_TRAINING_API_KEY", raising=False)
    args = agent.build_parser().parse_args(["--mode", "full", "--bot", "x"])
    try:
        import asyncio

        asyncio.run(agent.full(session=None, args=args))
    except SystemExit as exc:
        assert "BATTLE_TRAINING_API_KEY" in str(exc)
    else:  # pragma: no cover - the guard must fire before any session use
        raise AssertionError("full() should exit without an API key")


def test_full_mode_requires_controller_file(monkeypatch, tmp_path):
    monkeypatch.setenv("BATTLE_TRAINING_API_KEY", "fake-key-for-test")
    monkeypatch.chdir(tmp_path)
    args = agent.build_parser().parse_args(
        ["--mode", "full", "--bot", "x", "--controller", "missing.js"]
    )
    try:
        import asyncio

        asyncio.run(agent.full(session=None, args=args))
    except SystemExit as exc:
        assert "Controller not found" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("full() should exit without a controller file")


def test_constants_match_live_mcp_server():
    assert agent.MCP_URL == "https://api.battle.training/mcp"
    assert agent.DEFAULT_VS == "house:hunter"
    assert agent.POLL_MAX_TRIES * agent.POLL_INTERVAL_S >= 60


class _FakeContent:
    def __init__(self, text):
        self.text = text


class _FakeResult:
    def __init__(self, text, is_error=False):
        self.content = [_FakeContent(text)]
        self.isError = is_error


class _FakeSession:
    """Minimal stand-in for ClientSession: answers each tool from a script."""

    def __init__(self, script):
        self._script = script
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append(name)
        return self._script[name]


def test_full_mode_scrimmage_non_json_does_not_crash(monkeypatch, tmp_path):
    # Regression test (review 19 Nov): try_json falls back to a raw string
    # when the scrimmage tool returns non-JSON text; full() must print the
    # raw payload and skip the poll instead of raising AttributeError.
    import asyncio

    monkeypatch.setenv("BATTLE_TRAINING_API_KEY", "fake-key-for-test")
    monkeypatch.chdir(tmp_path)
    Path("controller.js").write_text("// fake controller", encoding="utf-8")
    script = {
        "whoami": _FakeResult('{"ok": true}'),
        "get_bot": _FakeResult(
            '{"name": "x", "rating": 100, "wins": 0, "losses": 0, "draws": 0}'
        ),
        "upload_version": _FakeResult("uploaded"),
        "scrimmage": _FakeResult("plain text, not json"),
    }
    session = _FakeSession(script)
    args = agent.build_parser().parse_args(["--mode", "full", "--bot", "x"])
    asyncio.run(agent.full(session=session, args=args))  # must not raise
    assert "get_match" not in session.calls
