"""Per-chat-window session reset - the same fix quiz-agent calls the "hackflow
pattern": ``ctx.storage`` is keyed only by ``sender``, and ASI:One reuses the
same ``sender`` address across a user's separate chat conversations. Without
this, a brand-new chat window would silently resume an already-paid session
left over from a previous, unrelated conversation instead of asking to pay
again. ``ctx.session`` changes per chat window, so this is what actually
decides "is this a fresh conversation", not whether the agent process itself
was restarted.
"""

from __future__ import annotations

import pytest

pytest.importorskip("uagents")

from session_state import (
    AWAITING_PACKAGE,
    UNINITIALIZED,
    check_new_window_and_reset,
    get_state,
    save_state,
)


class _FakeStorage:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value


class FakeContext:
    def __init__(self, session: str) -> None:
        self.session = session
        self.storage = _FakeStorage()


SENDER = "agent1qsomeuser"


def test_same_window_does_not_reset_a_paid_session() -> None:
    ctx = FakeContext(session="window-1")
    state = get_state(ctx, SENDER)
    state["state"] = AWAITING_PACKAGE
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)

    # First call in this window just records it - no reset yet.
    check_new_window_and_reset(ctx, SENDER)
    assert get_state(ctx, SENDER)["stripe_paid"] is True

    # A second message in the SAME window must not lose the paid state.
    check_new_window_and_reset(ctx, SENDER)
    reloaded = get_state(ctx, SENDER)
    assert reloaded["stripe_paid"] is True
    assert reloaded["state"] == AWAITING_PACKAGE


def test_new_window_resets_an_already_paid_session() -> None:
    ctx = FakeContext(session="window-1")
    state = get_state(ctx, SENDER)
    state["state"] = AWAITING_PACKAGE
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)
    check_new_window_and_reset(ctx, SENDER)  # records window-1 as seen

    # A brand-new chat conversation for the same sender gets a new ctx.session.
    ctx.session = "window-2"
    check_new_window_and_reset(ctx, SENDER)

    reloaded = get_state(ctx, SENDER)
    assert reloaded["stripe_paid"] is False
    assert reloaded["state"] == UNINITIALIZED


def test_restarting_the_process_without_a_new_window_keeps_the_paid_session() -> None:
    """Restarting ``python agent.py`` must NOT wipe every user's paid session -
    only a genuinely new chat window (a new ``ctx.session``) should. A process
    restart with the same on-disk storage and the same window resumes exactly
    where the conversation left off.
    """
    ctx = FakeContext(session="window-1")
    state = get_state(ctx, SENDER)
    state["state"] = AWAITING_PACKAGE
    state["stripe_paid"] = True
    save_state(ctx, SENDER, state)
    check_new_window_and_reset(ctx, SENDER)

    # Simulate "process restarted" by constructing a fresh FakeContext instance
    # that reuses the same underlying storage dict and the same window id.
    restarted_ctx = FakeContext(session="window-1")
    restarted_ctx.storage = ctx.storage

    check_new_window_and_reset(restarted_ctx, SENDER)
    reloaded = get_state(restarted_ctx, SENDER)
    assert reloaded["stripe_paid"] is True
    assert reloaded["state"] == AWAITING_PACKAGE
