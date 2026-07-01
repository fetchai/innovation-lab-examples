"""Unit tests for reactive.py — threshold detection and cooldown logic.

All tests use a patched get_buffer so no EventSub listener or DB is needed.
State dicts are cleared before each test to avoid inter-test bleed.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

import twitch.reactive as reactive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides):
    defaults = {
        "total_chat_seen": 0,
        "total_raids_seen": 0,
        "total_subs_seen": 0,
        "total_cheers_seen": 0,
        "total_follows_seen": 0,
        "cheers": [],
        "follows": [],
    }
    defaults.update(overrides)
    return defaults


def _mock_buffer(snap: dict):
    buf = MagicMock()
    buf.snapshot.return_value = snap
    return buf


@pytest.fixture(autouse=True)
def clear_state():
    """Reset all module-level per-user dicts before every test."""
    reactive._last_seen.clear()
    reactive._last_offer_at.clear()
    reactive._last_seen_ann.clear()
    reactive._last_announce_at.clear()
    yield


# ---------------------------------------------------------------------------
# evaluate() — moderation moments
# ---------------------------------------------------------------------------


class TestEvaluate:
    def _call(self, user_id, snap):
        with patch("twitch.reactive.get_buffer", return_value=_mock_buffer(snap)):
            return reactive.evaluate(user_id)

    def test_first_call_returns_none(self):
        snap = _make_snapshot(total_chat_seen=100, total_raids_seen=0)
        result = self._call("u1", snap)
        assert result is None

    def test_no_event_returns_none(self):
        snap = _make_snapshot(total_chat_seen=5, total_raids_seen=0)
        self._call("u1", snap)  # baseline
        result = self._call("u1", snap)  # same counts
        assert result is None

    def test_raid_detected(self):
        snap0 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)
        snap1 = _make_snapshot(total_chat_seen=0, total_raids_seen=1)
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is not None
        assert result["kind"] == "raid"
        assert result["setting"] == "follower_mode"

    def test_raid_beats_spam(self):
        spam_count = reactive.SPAM_MSGS_PER_TICK + 10
        snap0 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)
        snap1 = _make_snapshot(total_chat_seen=spam_count, total_raids_seen=1)
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result["kind"] == "raid"

    def test_spam_detected_at_threshold(self):
        threshold = reactive.SPAM_MSGS_PER_TICK
        snap0 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)
        snap1 = _make_snapshot(total_chat_seen=threshold, total_raids_seen=0)
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is not None
        assert result["kind"] == "spam"
        assert result["setting"] == "slow_mode"

    def test_spam_not_detected_below_threshold(self):
        snap0 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)
        snap1 = _make_snapshot(
            total_chat_seen=reactive.SPAM_MSGS_PER_TICK - 1, total_raids_seen=0
        )
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is None

    def test_users_tracked_independently(self):
        snap_a0 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)
        snap_b0 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)
        snap_a1 = _make_snapshot(
            total_chat_seen=reactive.SPAM_MSGS_PER_TICK, total_raids_seen=0
        )
        snap_b1 = _make_snapshot(total_chat_seen=0, total_raids_seen=0)

        with patch("twitch.reactive.get_buffer", return_value=_mock_buffer(snap_a0)):
            reactive.evaluate("uA")
        with patch("twitch.reactive.get_buffer", return_value=_mock_buffer(snap_b0)):
            reactive.evaluate("uB")

        with patch("twitch.reactive.get_buffer", return_value=_mock_buffer(snap_a1)):
            res_a = reactive.evaluate("uA")
        with patch("twitch.reactive.get_buffer", return_value=_mock_buffer(snap_b1)):
            res_b = reactive.evaluate("uB")

        assert res_a is not None and res_a["kind"] == "spam"
        assert res_b is None


# ---------------------------------------------------------------------------
# on_cooldown / mark_offered
# ---------------------------------------------------------------------------


class TestCooldown:
    def test_no_offer_yet_not_on_cooldown(self):
        assert not reactive.on_cooldown("u1", now=time.time())

    def test_just_offered_is_on_cooldown(self):
        now = time.time()
        reactive.mark_offered("u1", now=now)
        assert reactive.on_cooldown("u1", now=now)

    def test_cooldown_expires(self):
        past = time.time() - reactive.OFFER_COOLDOWN_SECONDS - 1
        reactive.mark_offered("u1", now=past)
        assert not reactive.on_cooldown("u1", now=time.time())

    def test_announce_cooldown_independent(self):
        now = time.time()
        reactive.mark_offered("u1", now=now)
        # Chat-settings cooldown is active, but announce cooldown is untouched.
        assert not reactive.announce_on_cooldown("u1", now=now)

    def test_announce_cooldown_triggered_by_mark_announced(self):
        now = time.time()
        reactive.mark_announced("u1", now=now)
        assert reactive.announce_on_cooldown("u1", now=now)

    def test_announce_cooldown_expires(self):
        past = time.time() - reactive.ANNOUNCE_COOLDOWN_SECONDS - 1
        reactive.mark_announced("u1", now=past)
        assert not reactive.announce_on_cooldown("u1", now=time.time())


# ---------------------------------------------------------------------------
# evaluate_announcement()
# ---------------------------------------------------------------------------


class TestEvaluateAnnouncement:
    def _call(self, user_id, snap):
        with patch("twitch.reactive.get_buffer", return_value=_mock_buffer(snap)):
            return reactive.evaluate_announcement(user_id)

    def test_first_call_returns_none(self):
        snap = _make_snapshot(
            total_subs_seen=5, total_cheers_seen=1, total_follows_seen=2
        )
        assert self._call("u1", snap) is None

    def test_big_cheer_detected(self):
        bits = reactive.BIG_CHEER_BITS
        snap0 = _make_snapshot(total_cheers_seen=0, cheers=[])
        snap1 = _make_snapshot(
            total_cheers_seen=1,
            cheers=[{"user": "alice", "bits": bits, "is_anonymous": False}],
        )
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is not None
        assert result["kind"] == "big_cheer"
        assert result["bits"] == bits
        assert result["user"] == "alice"

    def test_cheer_below_threshold_ignored(self):
        bits = reactive.BIG_CHEER_BITS - 1
        snap0 = _make_snapshot(total_cheers_seen=0, cheers=[])
        snap1 = _make_snapshot(
            total_cheers_seen=1,
            cheers=[{"user": "bob", "bits": bits, "is_anonymous": False}],
        )
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is None

    def test_anonymous_cheer_detected(self):
        bits = reactive.BIG_CHEER_BITS
        snap0 = _make_snapshot(total_cheers_seen=0, cheers=[])
        snap1 = _make_snapshot(
            total_cheers_seen=1,
            cheers=[{"user": "", "bits": bits, "is_anonymous": True}],
        )
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is not None
        assert result["user"] == "an anonymous viewer"

    def test_sub_milestone_detected(self):
        milestone = reactive.SUB_MILESTONES[0]
        snap0 = _make_snapshot(total_subs_seen=milestone - 1)
        snap1 = _make_snapshot(total_subs_seen=milestone)
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is not None
        assert result["kind"] == "sub_milestone"
        assert result["count"] == milestone

    def test_sub_no_milestone_crossed(self):
        milestone = reactive.SUB_MILESTONES[0]
        snap0 = _make_snapshot(total_subs_seen=milestone)
        snap1 = _make_snapshot(total_subs_seen=milestone)
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is None

    def test_new_follow_detected(self):
        snap0 = _make_snapshot(total_follows_seen=0, follows=[])
        snap1 = _make_snapshot(
            total_follows_seen=reactive.FOLLOW_THRESHOLD,
            follows=[{"user": "carol"}],
        )
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result is not None
        assert result["kind"] == "new_follow"
        assert result["user"] == "carol"

    def test_big_cheer_beats_sub_milestone(self):
        bits = reactive.BIG_CHEER_BITS
        milestone = reactive.SUB_MILESTONES[0]
        snap0 = _make_snapshot(
            total_subs_seen=milestone - 1, total_cheers_seen=0, cheers=[]
        )
        snap1 = _make_snapshot(
            total_subs_seen=milestone,
            total_cheers_seen=1,
            cheers=[{"user": "dave", "bits": bits, "is_anonymous": False}],
        )
        self._call("u1", snap0)
        result = self._call("u1", snap1)
        assert result["kind"] == "big_cheer"


# ---------------------------------------------------------------------------
# draft_announcement()
# ---------------------------------------------------------------------------


class TestDraftAnnouncement:
    def test_fallback_when_no_llm(self):
        moment = {"kind": "big_cheer", "user": "alice", "bits": 100}
        text = reactive.draft_announcement(moment, llm=None)
        assert "alice" in text
        assert "100" in text

    def test_llm_result_used(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Thanks for the cheer!"
        moment = {"kind": "sub_milestone", "count": 5}
        text = reactive.draft_announcement(moment, llm=mock_llm)
        assert text == "Thanks for the cheer!"

    def test_llm_failure_falls_back(self):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("timeout")
        moment = {"kind": "new_follow", "user": "eve", "count": 1}
        text = reactive.draft_announcement(moment, llm=mock_llm)
        assert "eve" in text

    def test_unknown_kind_returns_empty(self):
        text = reactive.draft_announcement({"kind": "unknown"}, llm=None)
        assert text == ""

    def test_output_capped_at_500_chars(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "x" * 600
        moment = {"kind": "sub_milestone", "count": 3}
        text = reactive.draft_announcement(moment, llm=mock_llm)
        assert len(text) <= 500


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_all_state_for_user(self):
        now = time.time()
        reactive._last_seen["u1"] = {"chat": 10, "raids": 0}
        reactive._last_offer_at["u1"] = now
        reactive._last_seen_ann["u1"] = {"subs": 5, "cheers": 0, "follows": 2}
        reactive._last_announce_at["u1"] = now

        reactive.reset("u1")

        assert "u1" not in reactive._last_seen
        assert "u1" not in reactive._last_offer_at
        assert "u1" not in reactive._last_seen_ann
        assert "u1" not in reactive._last_announce_at

    def test_reset_unknown_user_is_safe(self):
        reactive.reset("nonexistent")  # must not raise
