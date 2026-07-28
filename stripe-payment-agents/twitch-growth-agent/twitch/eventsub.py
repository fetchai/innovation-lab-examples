"""Twitch EventSub WebSocket listener — a persistent connection that streams
live chat/sub/cheer/raid/follow events for a connected user. Read-only: tokens
come from twitch_oauth.get_token_for_user, never stored or refreshed here.

Run standalone for one user:
    python -m twitch.eventsub <asi1_sender_id>

Docs: https://dev.twitch.tv/docs/eventsub/handling-websocket-events/
"""

import asyncio
import json
import logging
import os
import sys

import requests
import websockets
from websockets.asyncio.client import connect

from .oauth import (
    HELIX_BASE,
    NotConnectedError,
    _auth_headers,
    get_broadcaster_id,
    get_token_for_user,
)

logger = logging.getLogger("twitchy.eventsub")

DEFAULT_WS_URL = "wss://eventsub.wss.twitch.tv/ws"

# Extra slack on top of Twitch's keepalive_timeout before treating silence as dead.
_KEEPALIVE_GRACE_SECONDS = 10


def _subscriptions_for(broadcaster_id: str) -> "list[dict]":
    """Build the EventSub subscription request bodies for one broadcaster."""
    return [
        {
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": broadcaster_id,
                "user_id": broadcaster_id,
            },
        },
        {
            "type": "channel.subscribe",
            "version": "1",
            "condition": {"broadcaster_user_id": broadcaster_id},
        },
        {
            "type": "channel.cheer",
            "version": "1",
            "condition": {"broadcaster_user_id": broadcaster_id},
        },
        {
            "type": "channel.raid",
            "version": "1",
            "condition": {"to_broadcaster_user_id": broadcaster_id},
        },
        {
            # v2 needs moderator_user_id too (the broadcaster moderating themself).
            "type": "channel.follow",
            "version": "2",
            "condition": {
                "broadcaster_user_id": broadcaster_id,
                "moderator_user_id": broadcaster_id,
            },
        },
    ]


def _create_subscriptions(token: str, broadcaster_id: str, session_id: str) -> int:
    """POST each EventSub subscription over the websocket transport.

    Returns the number of subscriptions Twitch accepted. Failures are logged
    per-subscription (one bad type doesn't abort the others); a 409 means the
    subscription already exists for this session and is treated as fine.
    """
    headers = {**_auth_headers(token), "Content-Type": "application/json"}
    transport = {"method": "websocket", "session_id": session_id}
    accepted = 0
    for sub in _subscriptions_for(broadcaster_id):
        body = {**sub, "transport": transport}
        try:
            resp = requests.post(
                f"{HELIX_BASE}/eventsub/subscriptions",
                headers=headers,
                json=body,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001 - network hiccup shouldn't kill the listener
            logger.error("subscribe %s failed (network): %s", sub["type"], exc)
            continue

        # Create EventSub Subscription returns 202 Accepted on success.
        if resp.status_code == 202:
            accepted += 1
            logger.info("subscribed: %s", sub["type"])
        elif resp.status_code == 409:
            accepted += 1
            logger.info("already subscribed: %s", sub["type"])
        else:
            logger.error(
                "subscribe %s rejected (HTTP %s): %s",
                sub["type"],
                resp.status_code,
                resp.text.strip(),
            )
    return accepted


def _summarize_event(event_type: str, event: dict) -> str:
    """One-line, human-readable summary of an event's key fields for logging."""
    if event_type == "channel.chat.message":
        text = (event.get("message") or {}).get("text", "")
        return f"chat | {event.get('chatter_user_name', '?')}: {text}"
    if event_type == "channel.subscribe":
        gift = " (gift)" if event.get("is_gift") else ""
        return (
            f"sub  | {event.get('user_name', '?')} tier {event.get('tier', '?')}{gift}"
        )
    if event_type == "channel.cheer":
        who = "anonymous" if event.get("is_anonymous") else event.get("user_name", "?")
        return f"cheer| {who} cheered {event.get('bits', '?')} bits: {event.get('message', '')}"
    if event_type == "channel.raid":
        return (
            f"raid | incoming from {event.get('from_broadcaster_user_name', '?')} "
            f"with {event.get('viewers', '?')} viewers"
        )
    if event_type == "channel.follow":
        return f"follow| {event.get('user_name', '?')} followed"
    return f"{event_type} | {json.dumps(event)[:200]}"


class EventSubListener:
    """Persistent EventSub WebSocket listener for one connected user.

    run() maintains the connection across reconnects/timeouts. Pass
    on_event(event_type, event) to route events somewhere; defaults to log-only.
    """

    def __init__(self, sender: str, on_event=None):
        self.sender = sender
        self.on_event = on_event
        self.token = get_token_for_user(sender)
        self.broadcaster_id, self.login = get_broadcaster_id(self.token)

    async def run(self) -> None:
        """Connect and process events forever, handling reconnects.

        A session_reconnect URL is reused without re-subscribing; a fresh
        connection gets a new session and re-subscribes after its welcome.
        """
        logger.info(
            "starting EventSub for %s (broadcaster_id=%s)",
            self.login,
            self.broadcaster_id,
        )
        reconnect_url = None
        while True:
            url = reconnect_url or DEFAULT_WS_URL
            need_subscribe = reconnect_url is None
            reconnect_url = None  # consumed for this attempt
            try:
                reconnect_url = await self._connection_loop(url, need_subscribe)
            except (websockets.ConnectionClosed, asyncio.TimeoutError, OSError) as exc:
                # Dropped or went silent -> reconnect fresh (and re-subscribe).
                logger.warning("connection lost (%s); reconnecting in 1s", exc)
                await asyncio.sleep(1)

    async def _connection_loop(self, url: str, need_subscribe: bool) -> "str | None":
        """Pump messages on one websocket until it drops or asks to reconnect.

        Returns a reconnect URL if Twitch sent session_reconnect, else None.
        Raises on connection drop / keepalive timeout.
        """
        keepalive_timeout = (
            30  # default until the welcome message gives us the real value
        )
        async with connect(url, max_size=None) as ws:
            while True:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=keepalive_timeout + _KEEPALIVE_GRACE_SECONDS
                )
                msg = json.loads(raw)
                meta = msg.get("metadata", {})
                payload = msg.get("payload", {})
                msg_type = meta.get("message_type")

                if msg_type == "session_welcome":
                    session = payload.get("session", {})
                    session_id = session.get("id")
                    keepalive_timeout = (
                        session.get("keepalive_timeout_seconds") or keepalive_timeout
                    )
                    logger.info(
                        "session_welcome: id=%s keepalive=%ss",
                        session_id,
                        keepalive_timeout,
                    )
                    if need_subscribe:
                        count = await asyncio.to_thread(
                            _create_subscriptions,
                            self.token,
                            self.broadcaster_id,
                            session_id,
                        )
                        logger.info(
                            "%d subscription(s) active; listening for events", count
                        )
                        need_subscribe = False

                elif msg_type == "session_keepalive":
                    # Heartbeat only; receiving it resets our silence timer.
                    logger.debug("keepalive")

                elif msg_type == "notification":
                    sub = payload.get("subscription", {})
                    event_type = sub.get("type", "?")
                    event = payload.get("event", {})
                    logger.info("EVENT %s", _summarize_event(event_type, event))
                    if self.on_event is not None:
                        try:
                            self.on_event(event_type, event)
                        except Exception as exc:  # noqa: BLE001 - callback must not kill the loop
                            logger.error("on_event callback raised: %s", exc)

                elif msg_type == "session_reconnect":
                    new_url = (payload.get("session") or {}).get("reconnect_url")
                    logger.info("session_reconnect -> switching connection")
                    return new_url

                elif msg_type == "revocation":
                    sub = payload.get("subscription", {})
                    logger.warning(
                        "subscription revoked: %s (%s)",
                        sub.get("type"),
                        sub.get("status"),
                    )

                else:
                    logger.debug("unhandled message_type=%s: %s", msg_type, raw[:200])


async def listen_for_user(sender: str, on_event=None) -> None:
    """Convenience entrypoint: build a listener for ``sender`` and run it."""
    listener = EventSubListener(sender, on_event=on_event)
    await listener.run()


class ListenerManager:
    """Runs at most one EventSub listener per user. ensure_started() is
    idempotent and non-fatal (no token just skips quietly). on_event_factory
    builds the per-user callback that routes events to storage.
    """

    def __init__(self, on_event_factory=None):
        self._on_event_factory = on_event_factory
        self._tasks: "dict[str, asyncio.Task]" = {}

    def ensure_started(self, user_id: str) -> None:
        existing = self._tasks.get(user_id)
        if existing is not None and not existing.done():
            return
        on_event = self._on_event_factory(user_id) if self._on_event_factory else None
        self._tasks[user_id] = asyncio.create_task(self._run_one(user_id, on_event))
        logger.info("listener task created for %s (in-process)", user_id)

    async def _run_one(self, user_id: str, on_event) -> None:
        try:
            listener = await asyncio.to_thread(EventSubListener, user_id, on_event)
            await listener.run()
        except NotConnectedError:
            logger.info("user %s has no Twitch token; not starting a listener", user_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - one user's failure mustn't crash the agent
            logger.error("EventSub listener for %s stopped: %s", user_id, exc)

    def active_users(self) -> "list[str]":
        """User ids with a currently-running listener task."""
        return [uid for uid, task in self._tasks.items() if not task.done()]

    async def stop_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()


def _list_known_senders() -> "list[tuple[str, str]]":
    """List (sender, twitch_user_id) pairs for picking a sender when run standalone."""
    import sqlite3

    from twitch.store import DB_PATH

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT asi1_sender_id, twitch_user_id FROM tokens ORDER BY updated_at DESC"
        ).fetchall()
        conn.close()
        return [(r["asi1_sender_id"], r["twitch_user_id"]) for r in rows]
    except Exception:  # noqa: BLE001
        return []


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    sender = sys.argv[1] if len(sys.argv) > 1 else os.getenv("EVENTSUB_TEST_SENDER")
    if not sender:
        print("Usage: python -m twitch.eventsub <asi1_sender_id>")
        print(
            "   or: EVENTSUB_TEST_SENDER=<asi1_sender_id> python -m twitch.eventsub\n"
        )
        known = _list_known_senders()
        if known:
            print("Connected senders in the token DB:")
            for s, tid in known:
                print(f"  {s}   (twitch_user_id={tid})")
        else:
            print("No connected users found in the token DB yet.")
        sys.exit(1)

    try:
        asyncio.run(listen_for_user(sender))
    except NotConnectedError as exc:
        print(f"That user isn't connected to Twitch: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
