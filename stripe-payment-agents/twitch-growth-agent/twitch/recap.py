"""Per-user live-event buffer + on-demand recap.

eventsub.py feeds events in via CommunityBuffer.add(). generate_recap()
summarizes the buffer on demand: who to thank (subs/cheers/raids, listed
deterministically so nothing is hallucinated) plus an LLM pass for highlights
and an optional Discord draft.

In-memory, one buffer per user_id, lock-guarded since the listener writes from
the event loop while recap reads from a worker thread.
"""

import logging
import threading
from collections import deque

logger = logging.getLogger("twitchy.recap")

# Per-user ring-buffer caps (bound memory over a long stream; oldest drop first).
_MAX_CHAT = 500
_MAX_EVENTS = 200

# Cap how much chat we hand the LLM, newest-last, to bound prompt size.
_RECAP_CHAT_WINDOW = 150


class CommunityBuffer:
    """Thread-safe ring buffer of one broadcaster's live events.

    Holds normalized, summary-only fields (not raw Twitch payloads) so the recap
    layer never re-parses EventSub shapes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.chat: "deque[dict]" = deque(maxlen=_MAX_CHAT)
        self.subs: "deque[dict]" = deque(maxlen=_MAX_EVENTS)
        self.cheers: "deque[dict]" = deque(maxlen=_MAX_EVENTS)
        self.raids: "deque[dict]" = deque(maxlen=_MAX_EVENTS)
        self.follows: "deque[dict]" = deque(maxlen=_MAX_EVENTS)
        # Monotonic lifetime counters (NOT reset by ring-buffer eviction), so the
        # 5c/5d reactive monitors can measure deltas between ticks even once the
        # bounded deques are full. clear() resets these too.
        self.total_chat_seen = 0
        self.total_raids_seen = 0
        self.total_subs_seen = 0
        self.total_cheers_seen = 0
        self.total_follows_seen = 0

    def add(self, event_type: str, event: dict) -> None:
        """Append one EventSub notification, keyed by its subscription type.

        Safe to call from the listener's event loop while the recap generator
        reads via snapshot() on another thread.
        """
        with self._lock:
            if event_type == "channel.chat.message":
                self.total_chat_seen += 1
                self.chat.append(
                    {
                        "user": event.get("chatter_user_name", "?"),
                        "text": (event.get("message") or {}).get("text", ""),
                    }
                )
            elif event_type == "channel.subscribe":
                self.total_subs_seen += 1
                self.subs.append(
                    {
                        "user": event.get("user_name", "?"),
                        "tier": event.get("tier", ""),
                        "is_gift": bool(event.get("is_gift")),
                    }
                )
            elif event_type == "channel.cheer":
                self.total_cheers_seen += 1
                self.cheers.append(
                    {
                        "user": event.get("user_name", "?"),
                        "bits": event.get("bits", 0),
                        "message": event.get("message", ""),
                        "is_anonymous": bool(event.get("is_anonymous")),
                    }
                )
            elif event_type == "channel.raid":
                self.total_raids_seen += 1
                self.raids.append(
                    {
                        "from": event.get("from_broadcaster_user_name", "?"),
                        "viewers": event.get("viewers", 0),
                    }
                )
            elif event_type == "channel.follow":
                self.total_follows_seen += 1
                self.follows.append({"user": event.get("user_name", "?")})
            # Unknown types are ignored — the listener still logs them.

    def snapshot(self) -> dict:
        """Return shallow copies of the buffers (consistent, lock-held read)."""
        with self._lock:
            return {
                "chat": list(self.chat),
                "subs": list(self.subs),
                "cheers": list(self.cheers),
                "raids": list(self.raids),
                "follows": list(self.follows),
                "total_chat_seen": self.total_chat_seen,
                "total_raids_seen": self.total_raids_seen,
                "total_subs_seen": self.total_subs_seen,
                "total_cheers_seen": self.total_cheers_seen,
                "total_follows_seen": self.total_follows_seen,
            }

    def clear(self) -> None:
        with self._lock:
            self.chat.clear()
            self.subs.clear()
            self.cheers.clear()
            self.raids.clear()
            self.follows.clear()
            self.total_chat_seen = 0
            self.total_raids_seen = 0
            self.total_subs_seen = 0
            self.total_cheers_seen = 0
            self.total_follows_seen = 0

    def is_empty(self) -> bool:
        with self._lock:
            return not (
                self.chat or self.subs or self.cheers or self.raids or self.follows
            )


_buffers: "dict[str, CommunityBuffer]" = {}
_buffers_lock = threading.Lock()


def get_buffer(user_id: str) -> CommunityBuffer:
    """Return (creating if needed) the live-event buffer for ``user_id``."""
    with _buffers_lock:
        buf = _buffers.get(user_id)
        if buf is None:
            buf = CommunityBuffer()
            _buffers[user_id] = buf
        return buf


_TIER_LABELS = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}


def _fmt_tier(tier: "str | int") -> str:
    return _TIER_LABELS.get(str(tier), f"tier {tier}" if tier else "Prime/Tier 1")


def _thanks_lines(snap: dict) -> "list[str]":
    """Deterministic 'people to thank' list — exact names/amounts, no LLM."""
    lines = []
    for s in snap["subs"]:
        gift = " (gifted)" if s["is_gift"] else ""
        lines.append(f"• {s['user']} — new sub, {_fmt_tier(s['tier'])}{gift}")
    for c in snap["cheers"]:
        who = "An anonymous viewer" if c["is_anonymous"] else c["user"]
        lines.append(f"• {who} — cheered {c['bits']} bits")
    for r in snap["raids"]:
        lines.append(f"• {r['from']} — raided in with {r['viewers']} viewer(s)")
    return lines


_RECAP_SYSTEM_PROMPT = (
    "You are a Twitch live-stream copilot writing a quick recap for a streamer who "
    "stepped away. You are given the recent chat log and event counts. Produce THREE "
    "short sections with these exact markdown headers and nothing before the first one:\n\n"
    "### Unanswered questions\n"
    "Bullet the genuine questions from chat that nobody (especially the streamer) "
    "seems to have answered. Quote the asker's name. If there are none, write 'None spotted.'\n\n"
    "### Highlights & vibe\n"
    "2-4 bullets on the mood, running jokes, or notable moments. Be specific to the chat.\n\n"
    "### Discord draft\n"
    "One short, friendly paragraph the streamer can paste into their Discord to recap "
    "the session for people who missed it. No @everyone.\n\n"
    "Rules: be concise, do NOT invent usernames, bits, or events that aren't in the "
    "data, and do not add any sections beyond the three above."
)


def _build_llm_input(snap: dict) -> str:
    """Render the buffer into a compact text block for the recap LLM."""
    chat = snap["chat"][-_RECAP_CHAT_WINDOW:]
    chat_lines = (
        "\n".join(f"{m['user']}: {m['text']}" for m in chat) or "(no chat messages)"
    )
    counts = (
        f"new subs: {len(snap['subs'])}, cheers: {len(snap['cheers'])}, "
        f"incoming raids: {len(snap['raids'])}, chat messages: {len(snap['chat'])}"
    )
    return f"Event counts — {counts}\n\nRecent chat log (oldest first):\n{chat_lines}"


def _empty_recap_message() -> str:
    return (
        "I haven't captured any live activity yet. I start listening once you're "
        "connected, so go live and your chat, subs, and cheers will collect here. "
        'Ask me "what did I miss?" again once things are rolling. 📺'
    )


def generate_recap(user_id: str, llm=None) -> str:
    """Build a recap: deterministic header + thank-you list, plus an LLM
    narrative. Blocking, call via asyncio.to_thread. Never raises.
    """
    snap = get_buffer(user_id).snapshot()
    total = (
        len(snap["chat"]) + len(snap["subs"]) + len(snap["cheers"]) + len(snap["raids"])
    )
    if total == 0:
        return _empty_recap_message()

    parts = ["🎬 **Here's what you missed**", ""]
    parts.append(
        f"While you were away: **{len(snap['chat'])}** chat messages, "
        f"**{len(snap['subs'])}** new sub(s), **{len(snap['cheers'])}** cheer(s), "
        f"**{len(snap['raids'])}** raid(s) in."
    )

    thanks = _thanks_lines(snap)
    if thanks:
        parts.append("")
        parts.append("**People to thank**")
        parts.extend(thanks)

    narrative = ""
    if llm is not None:
        prompt = f"{_RECAP_SYSTEM_PROMPT}\n\n{_build_llm_input(snap)}"
        try:
            narrative = llm.invoke(prompt).content.strip()
        except Exception as exc:  # noqa: BLE001 - never let the LLM kill the recap
            logger.error("recap LLM failed for %s: %s", user_id, exc)

    if narrative:
        parts.append("")
        parts.append(narrative)

    return "\n".join(parts)
