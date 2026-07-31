"""Reactive copilot: watches the live buffer on a timer and offers one
confirm-gated action when it spots something — never a generic panel.

evaluate() flags moderation moments (raid, message flood) and names one chat
setting to recommend. evaluate_announcement() flags celebration moments (big
cheer, sub milestone) and draft_announcement() writes the offer text.

Guards against being annoying: a baseline-on-first-sight (no firing on the
first observation) and a per-user cooldown. Read-only over the recap buffer —
no Twitch calls here.
"""

import logging
import time

from .recap import get_buffer

logger = logging.getLogger("twitchy.reactive")

# Not exact-duplicate detection — Twitch blocks repeat lines within ~30s, so
# spammers vary them slightly. A 40+ message burst in one tick is spam regardless.
SPAM_MSGS_PER_TICK = 40
OFFER_COOLDOWN_SECONDS = 180

BIG_CHEER_BITS = 1000
SUB_MILESTONES = (5, 10, 25, 50, 100, 200, 500, 1000)
FOLLOW_THRESHOLD = 3
ANNOUNCE_COOLDOWN_SECONDS = 300

# In-process per-user state; chat-settings and announcements track separate
# baselines/cooldowns so they don't interfere with each other.
_last_seen: "dict[str, dict]" = {}
_last_offer_at: "dict[str, float]" = {}
_last_seen_ann: "dict[str, dict]" = {}
_last_announce_at: "dict[str, float]" = {}


def evaluate(user_id: str) -> "dict | None":
    """Check for a trouble moment and update tick counters. Call every tick
    even on cooldown so the deltas stay current. Raid beats spam.
    """
    snap = get_buffer(user_id).snapshot()
    chat_total = snap["total_chat_seen"]
    raid_total = snap["total_raids_seen"]

    first_sight = user_id not in _last_seen
    prev = _last_seen.get(user_id, {"chat": chat_total, "raids": raid_total})
    _last_seen[user_id] = {"chat": chat_total, "raids": raid_total}
    if first_sight:
        # Record a baseline only — never fire on the very first observation.
        return None

    new_raids = raid_total - prev["raids"]
    new_msgs = chat_total - prev["chat"]

    if new_raids > 0:
        return {
            "kind": "raid",
            # What was noticed (shown as the companion text above the card).
            "noticed": "📣 A raid just landed in your chat — expect a wave of new viewers.",
            # The single, specific setting to recommend, as an update_chat_settings
            # kwarg, plus a friendly label for the card/confirmation.
            "setting": "follower_mode",
            "label": "Followers-only mode",
        }

    if new_msgs >= SPAM_MSGS_PER_TICK:
        return {
            "kind": "spam",
            "noticed": "🚨 Your chat is moving fast — a burst of messages just came through.",
            "setting": "slow_mode",
            "label": "Slow mode",
        }

    return None


def on_cooldown(user_id: str, now: "float | None" = None) -> bool:
    """True if we offered ``user_id`` a chat-settings nudge too recently."""
    now = time.time() if now is None else now
    return now - _last_offer_at.get(user_id, 0.0) < OFFER_COOLDOWN_SECONDS


def mark_offered(user_id: str, now: "float | None" = None) -> None:
    _last_offer_at[user_id] = time.time() if now is None else now


def _milestone_crossed(old: int, new: int) -> "int | None":
    """Highest SUB_MILESTONES value crossed between old and new, or None."""
    crossed = [m for m in SUB_MILESTONES if old < m <= new]
    return crossed[-1] if crossed else None


def evaluate_announcement(user_id: str) -> "dict | None":
    """Check for an announce-worthy moment and update counters. Own baseline,
    separate from evaluate()'s. Big cheer beats sub milestone beats new follow.
    """
    snap = get_buffer(user_id).snapshot()
    subs_total = snap["total_subs_seen"]
    cheers_total = snap["total_cheers_seen"]
    follows_total = snap["total_follows_seen"]

    first_sight = user_id not in _last_seen_ann
    prev = _last_seen_ann.get(
        user_id, {"subs": subs_total, "cheers": cheers_total, "follows": follows_total}
    )
    _last_seen_ann[user_id] = {
        "subs": subs_total,
        "cheers": cheers_total,
        "follows": follows_total,
    }
    if first_sight:
        return None

    new_cheers = cheers_total - prev["cheers"]
    if new_cheers > 0:
        # Inspect only the cheers added since the last tick for a big one.
        recent = snap["cheers"][-new_cheers:]
        big = max(
            (c for c in recent if int(c.get("bits", 0)) >= BIG_CHEER_BITS),
            key=lambda c: int(c.get("bits", 0)),
            default=None,
        )
        if big:
            who = (
                "an anonymous viewer"
                if big.get("is_anonymous")
                else big.get("user", "someone")
            )
            return {"kind": "big_cheer", "user": who, "bits": int(big.get("bits", 0))}

    milestone = _milestone_crossed(prev["subs"], subs_total)
    if milestone:
        return {"kind": "sub_milestone", "count": milestone}

    new_follows = follows_total - prev.get("follows", follows_total)
    if new_follows >= FOLLOW_THRESHOLD:
        latest = snap["follows"][-1] if snap["follows"] else {}
        return {
            "kind": "new_follow",
            "user": latest.get("user", "someone"),
            "count": new_follows,
        }

    return None


_ANNOUNCE_SYSTEM_PROMPT = (
    "You write a single short, upbeat Twitch chat announcement (one or two sentences, "
    "max ~200 characters). No hashtags, no @everyone, no quotes around it. Return ONLY "
    "the announcement text and nothing else."
)


def draft_announcement(moment: dict, llm=None) -> str:
    """Write the announcement text for a moment. Blocking, call via to_thread.
    Falls back to a template on any LLM failure; capped at 500 chars.
    """
    kind = moment.get("kind")
    if kind == "big_cheer":
        context = (
            f"A viewer ({moment['user']}) just cheered {moment['bits']} bits. "
            "Thank them warmly by name and hype up the chat."
        )
        fallback = f"Huge thanks to {moment['user']} for the {moment['bits']} bits! You're amazing 💜"
    elif kind == "sub_milestone":
        context = (
            f"The stream just hit {moment['count']} new subscribers this session. "
            "Celebrate the milestone and thank everyone who subbed."
        )
        fallback = f"We just hit {moment['count']} subs this stream — thank you all so much! 🎉"
    elif kind == "new_follow":
        context = (
            f"A viewer ({moment['user']}) just followed the channel. "
            "Give them a short, warm welcome shout-out by name."
        )
        fallback = (
            f"Welcome our newest follower, {moment['user']}! Thanks for the follow 🎉"
        )
    else:
        return ""

    if llm is not None:
        try:
            text = llm.invoke(f"{_ANNOUNCE_SYSTEM_PROMPT}\n\n{context}").content.strip()
            if text:
                return text[:500]
        except Exception as exc:  # noqa: BLE001 - fall back rather than drop the moment
            logger.error("announcement draft LLM failed for %s: %s", kind, exc)
    return fallback


def announce_on_cooldown(user_id: str, now: "float | None" = None) -> bool:
    """True if we offered ``user_id`` an announcement too recently."""
    now = time.time() if now is None else now
    return now - _last_announce_at.get(user_id, 0.0) < ANNOUNCE_COOLDOWN_SECONDS


def mark_announced(user_id: str, now: "float | None" = None) -> None:
    _last_announce_at[user_id] = time.time() if now is None else now


def reset(user_id: str) -> None:
    """Forget a user's monitor state (e.g. when their listener stops)."""
    _last_seen.pop(user_id, None)
    _last_offer_at.pop(user_id, None)
    _last_seen_ann.pop(user_id, None)
    _last_announce_at.pop(user_id, None)
