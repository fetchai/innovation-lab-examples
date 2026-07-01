"""Multi-user Twitch OAuth + channel actions.

The growth report reads public data with an app access token (growth_pipeline.py).
Every write action (title/category/tags, announcements, chat settings, raids,
clips) needs the calling user's own token, obtained via the Authorization
Code grant and stored encrypted per-user in oauth_store.py, keyed by Twitch
user id and looked up by the ASI:One sender.

OAuth core: build_authorize_url(sender) -> (url, state); handle_oauth_callback
exchanges the code and stores tokens; get_token_for_user auto-refreshes.

The hosted HTTP callback lives in twitch/callback.py.
"""

import logging
import os
import time
import urllib.parse

import requests
from dotenv import load_dotenv

from . import store as oauth_store

load_dotenv()

logger = logging.getLogger(__name__)

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
HELIX_BASE = "https://api.twitch.tv/helix"

# Must exactly match a redirect URI registered in the Twitch dev console.
REDIRECT_URI = os.getenv("TWITCH_REDIRECT_URI", "http://localhost:3000/callback")

# All requested in one consent screen. broadcast=channel setup,
# announcements/chat_settings/raids/clips=the actions, the rest feed the recap.
SCOPES = [
    "channel:manage:broadcast",
    "moderator:manage:announcements",
    "moderator:manage:chat_settings",
    "channel:manage:raids",
    "clips:edit",
    "user:read:chat",
    "channel:read:subscriptions",
    "bits:read",
    "moderator:read:followers",
]

# Refresh a little before the real expiry to avoid edge-of-expiry failures.
_EXPIRY_SKEW_SECONDS = 60


class NotConnectedError(Exception):
    """Raised when a user has no stored Twitch token (needs to connect first)."""


# Returned by every write action when the user has no token, instead of
# touching the Twitch API — never falls back to any other token.
NEEDS_CONNECT = "NEEDS_CONNECT"


def _token_request(extra: dict) -> dict:
    """POST to the Twitch token endpoint and return the JSON token response."""
    resp = requests.post(
        TOKEN_URL,
        params={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, **extra},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    return _token_request(
        {"code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI}
    )


def refresh_tokens(refresh_token: str) -> dict:
    """Exchange a refresh token for a fresh access + refresh token pair."""
    return _token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )


def build_authorize_url(
    sender: str, pending: "dict | None" = None
) -> "tuple[str, str]":
    """Build the Twitch consent URL for sender; returns (authorize_url, state).
    The signed state links Twitch's redirect back to this conversation;
    pending optionally stashes a request to resume after auth.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET are not set.")
    state = oauth_store.make_state()
    oauth_store.save_state(state, sender, pending)
    query = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}", state


def handle_oauth_callback(code: str, state: str) -> dict:
    """Validate state, exchange the code, fetch the Twitch user id, store tokens.

    Returns {"sender", "twitch_user_id", "login", "pending"}. Raises on any
    invalid/expired state or token-exchange failure.
    """
    if not state or not oauth_store.verify_state_sig(state):
        raise ValueError("invalid OAuth state signature")
    mapping = oauth_store.pop_state(state)
    if not mapping:
        raise ValueError("unknown or expired OAuth state")

    sender = mapping["sender"]
    tok = exchange_code_for_tokens(code)
    access = tok["access_token"]
    twitch_user_id, login = get_broadcaster_id(access)

    oauth_store.upsert_tokens(
        twitch_user_id=twitch_user_id,
        asi1_sender_id=sender,
        access_token=access,
        refresh_token=tok.get("refresh_token", ""),
        expires_at=time.time() + int(tok.get("expires_in", 0)),
        scopes=tok.get("scope", []),
    )
    return {
        "sender": sender,
        "twitch_user_id": twitch_user_id,
        "login": login,
        "pending": mapping.get("pending"),
    }


def get_token_for_user(user_id: "str | None" = None) -> str:
    """Return a valid access token for this sender, refreshing near expiry.
    Raises NotConnectedError if they haven't connected Twitch yet.
    """
    if not user_id:
        raise NotConnectedError("no user id provided")
    row = oauth_store.get_tokens_by_sender(user_id)
    if not row:
        raise NotConnectedError(f"no Twitch token stored for {user_id}")

    if time.time() >= row["expires_at"] - _EXPIRY_SKEW_SECONDS:
        tok = refresh_tokens(row["refresh_token"])
        access = tok["access_token"]
        oauth_store.update_access_token(
            twitch_user_id=row["twitch_user_id"],
            access_token=access,
            refresh_token=tok.get("refresh_token", row["refresh_token"]),
            expires_at=time.time() + int(tok.get("expires_in", 0)),
        )
        return access
    return row["access_token"]


def is_connected(user_id: "str | None") -> bool:
    """Cheap read-only check used by the upfront connect gate, before showing
    a feature card. get_token_for_user + NEEDS_CONNECT remains the backstop.
    """
    if not user_id:
        return False
    return oauth_store.get_tokens_by_sender(user_id) is not None


def _auth_headers(token: str) -> dict:
    """Standard Helix auth headers for a user token."""
    return {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {token}"}


def get_broadcaster_id(token: str) -> "tuple[str, str]":
    """Resolve (broadcaster_id, login) for the token's user. Raises on failure."""
    resp = requests.get(f"{HELIX_BASE}/users", headers=_auth_headers(token), timeout=30)
    resp.raise_for_status()
    users = resp.json().get("data", [])
    if not users:
        raise RuntimeError(
            "couldn't resolve the authenticated Twitch user from the token"
        )
    return users[0]["id"], users[0].get("login", users[0]["id"])


def setup_channel(
    title: str,
    game_name: str,
    tags: "list[str] | None" = None,
    user_id: "str | None" = None,
) -> str:
    """Set title/category/tags via Modify Channel Information. Never raises —
    returns a friendly success or error string.
    """
    try:
        token = get_token_for_user(user_id)
        auth_headers = _auth_headers(token)

        # Omit fields the user didn't provide — an empty string would blank them.
        title = (title or "").strip()
        game_name = (game_name or "").strip()
        clean_tags = [t for t in (tags or []) if t and str(t).strip()]

        if not title and not game_name and not clean_tags:
            return (
                "Error: nothing to update — give me a title, a category/game, "
                "and/or tags to set."
            )

        broadcaster_id, login = get_broadcaster_id(token)

        body: dict = {}
        if title:
            body["title"] = title
        if game_name:
            games_resp = requests.get(
                f"{HELIX_BASE}/games",
                headers=auth_headers,
                params={"name": game_name},
                timeout=30,
            )
            games_resp.raise_for_status()
            games = games_resp.json().get("data", [])
            if not games:
                return (
                    f"Error: Twitch category/game '{game_name}' was not found. "
                    "Use the exact name as it appears on Twitch (e.g. 'Just Chatting')."
                )
            body["game_id"] = games[0]["id"]
        if clean_tags:
            body["tags"] = clean_tags

        patch_resp = requests.patch(
            f"{HELIX_BASE}/channels",
            headers={**auth_headers, "Content-Type": "application/json"},
            params={"broadcaster_id": broadcaster_id},
            json=body,
            timeout=30,
        )

        # Modify Channel Information returns 204 No Content on success.
        if patch_resp.status_code == 204:
            parts = []
            if title:
                parts.append(f"title -> '{title}'")
            if game_name:
                parts.append(f"category -> '{game_name}'")
            if clean_tags:
                parts.append(f"tags -> {clean_tags}")
            return f"Channel '{login}' updated successfully: " + ", ".join(parts) + "."

        return (
            f"Error: Twitch rejected the update (HTTP {patch_resp.status_code}): "
            f"{patch_resp.text.strip()}"
        )
    except NotConnectedError:
        # No token for this user -> do NOT call Twitch, do NOT use any other
        # token. Signal the agent to send the connect prompt.
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error setting up channel: {exc}"


_ANNOUNCEMENT_COLORS = {"blue", "green", "orange", "purple", "primary"}
_ANNOUNCEMENT_MAX_LEN = 500


def send_announcement(
    message: str, color: str = "primary", user_id: "str | None" = None
) -> str:
    """Post a highlighted chat announcement. Never raises."""
    try:
        if not message or not message.strip():
            return "Error: announcement message is empty."

        color = (color or "primary").strip().lower()
        if color not in _ANNOUNCEMENT_COLORS:
            color = "primary"

        if len(message) > _ANNOUNCEMENT_MAX_LEN:
            message = message[:_ANNOUNCEMENT_MAX_LEN]

        token = get_token_for_user(user_id)
        broadcaster_id, login = get_broadcaster_id(token)

        query_params = {
            "broadcaster_id": broadcaster_id,
            "moderator_id": broadcaster_id,
        }
        body = {"message": message, "color": color}

        resp = requests.post(
            f"{HELIX_BASE}/chat/announcements",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            params=query_params,
            json=body,
            timeout=30,
        )

        if resp.status_code == 204:
            return f"Announcement posted to '{login}' chat (color: {color}): \"{message}\"."

        return (
            f"Error: Twitch rejected the announcement (HTTP {resp.status_code}): "
            f"{resp.text.strip()}"
        )
    except NotConnectedError:
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error sending announcement: {exc}"


def get_chat_settings(user_id: "str | None" = None) -> "dict | str":
    """Fetch current chat room modes. Returns the settings dict, NEEDS_CONNECT,
    or a friendly error string (never raises).
    """
    try:
        token = get_token_for_user(user_id)
        broadcaster_id, _login = get_broadcaster_id(token)

        query_params = {
            "broadcaster_id": broadcaster_id,
            "moderator_id": broadcaster_id,
        }
        resp = requests.get(
            f"{HELIX_BASE}/chat/settings",
            headers=_auth_headers(token),
            params=query_params,
            timeout=30,
        )

        if resp.status_code == 200:
            return (resp.json().get("data") or [{}])[0]

        return (
            f"Error: Twitch rejected the chat settings fetch (HTTP {resp.status_code}): "
            f"{resp.text.strip()}"
        )
    except NotConnectedError:
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error fetching chat settings: {exc}"


def update_chat_settings(
    slow_mode: "bool | None" = None,
    slow_mode_wait_seconds: "int | None" = None,
    follower_mode: "bool | None" = None,
    follower_mode_duration: "int | None" = None,
    subscriber_mode: "bool | None" = None,
    emote_mode: "bool | None" = None,
    unique_chat_mode: "bool | None" = None,
    user_id: "str | None" = None,
) -> str:
    """Toggle chat room modes. Every parameter is optional — only the ones
    you pass are sent. Returns a friendly string (never raises).
    """
    try:
        candidates = {
            "slow_mode": slow_mode,
            "slow_mode_wait_time": slow_mode_wait_seconds,
            "follower_mode": follower_mode,
            "follower_mode_duration": follower_mode_duration,
            "subscriber_mode": subscriber_mode,
            "emote_mode": emote_mode,
            "unique_chat_mode": unique_chat_mode,
        }
        body = {key: value for key, value in candidates.items() if value is not None}
        if not body:
            return (
                "Error: no chat settings provided — pass at least one mode to change."
            )

        token = get_token_for_user(user_id)
        broadcaster_id, login = get_broadcaster_id(token)

        query_params = {
            "broadcaster_id": broadcaster_id,
            "moderator_id": broadcaster_id,
        }

        resp = requests.patch(
            f"{HELIX_BASE}/chat/settings",
            headers={**_auth_headers(token), "Content-Type": "application/json"},
            params=query_params,
            json=body,
            timeout=30,
        )

        # Update Chat Settings returns 200 with the updated settings on success.
        if resp.status_code == 200:
            updated = (resp.json().get("data") or [{}])[0]
            summary = ", ".join(
                f"{key} -> {updated.get(key, body[key])}" for key in body
            )
            return f"Chat settings updated for '{login}': {summary}."

        return (
            f"Error: Twitch rejected the chat settings update (HTTP {resp.status_code}): "
            f"{resp.text.strip()}"
        )
    except NotConnectedError:
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error updating chat settings: {exc}"


def _resolve_game_id(token: str, game_name: str) -> "str | None":
    """Resolve a Twitch game/category id from its name, or None if not found."""
    resp = requests.get(
        f"{HELIX_BASE}/games",
        headers=_auth_headers(token),
        params={"name": game_name},
        timeout=30,
    )
    resp.raise_for_status()
    games = resp.json().get("data", [])
    return games[0]["id"] if games else None


def find_raid_candidates(
    game_name: str, max_viewers: int = 50, limit: int = 15, user_id: "str | None" = None
) -> "list[dict] | str":
    """Live channels in game_name at/under max_viewers (excluding yourself),
    ranked by viewer count descending, capped at limit. Returns a friendly
    message string if the category isn't found or nothing suitable is live.
    """
    try:
        token = get_token_for_user(user_id)
        my_id, _ = get_broadcaster_id(token)

        game_id = _resolve_game_id(token, game_name)
        if not game_id:
            return (
                f"Error: Twitch category/game '{game_name}' was not found. "
                "Use the exact name as it appears on Twitch (e.g. 'Just Chatting')."
            )

        resp = requests.get(
            f"{HELIX_BASE}/streams",
            headers=_auth_headers(token),
            params={"game_id": game_id, "first": "100", "type": "live"},
            timeout=30,
        )
        resp.raise_for_status()
        streams = resp.json().get("data", [])

        candidates = [
            s
            for s in streams
            if s.get("user_id") != my_id
            and int(s.get("viewer_count", 0)) <= max_viewers
        ]
        if not candidates:
            return (
                f"No suitable raid target found in '{game_name}' with "
                f"{max_viewers} or fewer viewers right now. Try a higher "
                "max_viewers or a different category."
            )

        candidates.sort(key=lambda s: int(s.get("viewer_count", 0)), reverse=True)
        return [
            {
                "broadcaster_id": s["user_id"],
                "user_login": s["user_login"],
                "user_name": s["user_name"],
                "viewer_count": int(s.get("viewer_count", 0)),
            }
            for s in candidates[:limit]
        ]
    except NotConnectedError:
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error finding a raid target: {exc}"


def find_raid_target(game_name: str, max_viewers: int = 50) -> "dict | str":
    """Wrapper over find_raid_candidates() returning just the top entry."""
    result = find_raid_candidates(game_name, max_viewers=max_viewers)
    if isinstance(result, str):
        return result
    return result[0]


# Raid attempt outcome classification, so callers can decide whether retrying a
# DIFFERENT target makes sense.
_RAID_SUCCESS = "success"  # raid started
_RAID_NOT_ALLOWED = (
    "not_allowed"  # target-specific: their settings block raids -> try next
)
_RAID_NOT_LIVE = "not_live"  # our problem: not streaming -> stop, retry won't help
_RAID_RATE_LIMITED = "rate_limited"  # HTTP 429: out of raid budget -> stop hard
_RAID_ERROR = "error"  # other error -> stop


def _attempt_raid(
    token: str, my_id: str, login: str, target_broadcaster_id: str
) -> "tuple[str, str]":
    """POST a single raid attempt; returns (_RAID_* status, friendly_message).
    Only _RAID_NOT_ALLOWED is target-specific — everything else is terminal.
    """
    resp = requests.post(
        f"{HELIX_BASE}/raids",
        headers=_auth_headers(token),
        params={
            "from_broadcaster_id": my_id,
            "to_broadcaster_id": target_broadcaster_id,
        },
        timeout=30,
    )

    # Start a raid returns 200 with the raid details on success.
    if resp.status_code == 200:
        data = (resp.json().get("data") or [{}])[0]
        mature_note = ""
        if data.get("is_mature") is True:
            mature_note = " (target is flagged mature — viewers must acknowledge)"
        return (
            _RAID_SUCCESS,
            f"Raid started from '{login}' to broadcaster {target_broadcaster_id}. "
            f"Your viewers are now on the raid countdown{mature_note}.",
        )

    body = resp.text.strip()
    low = body.lower()

    # Rate limited — Twitch allows only 10 raid requests per 10 minutes. Trying
    # more candidates now just burns budget and keeps 429-ing.
    if resp.status_code == 429:
        return (
            _RAID_RATE_LIMITED,
            "Hit Twitch's raid rate limit (10 per 10 minutes). Wait ~10 minutes "
            "WITHOUT making any more raid attempts, then try once more.",
        )

    # Our problem — not streaming. Retrying another target won't help.
    if resp.status_code == 400 and "not currently live" in low:
        return (
            _RAID_NOT_LIVE,
            "Error: you need to be LIVE on Twitch to start a raid. "
            "Start your stream, then try again.",
        )

    # Target-specific — their settings don't allow raids right now. Try next.
    if resp.status_code == 400 and "do not allow you to raid" in low:
        return (
            _RAID_NOT_ALLOWED,
            f"Target {target_broadcaster_id} doesn't allow raids right now.",
        )

    return (
        _RAID_ERROR,
        f"Error: Twitch couldn't start the raid (HTTP {resp.status_code}): {body}. "
        "Note: you must be live to raid, and you can't raid yourself or a channel "
        "that's already being raided.",
    )


def start_raid(target_broadcaster_id: str, user_id: "str | None" = None) -> str:
    """Start a raid to target_broadcaster_id. Requires being live. Never raises."""
    try:
        token = get_token_for_user(user_id)
        my_id, login = get_broadcaster_id(token)
        _status, message = _attempt_raid(token, my_id, login, target_broadcaster_id)
        return message
    except NotConnectedError:
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error starting raid: {exc}"


def find_and_raid(
    game_name: str,
    max_viewers: int = 50,
    max_attempts: int = 3,
    user_id: "str | None" = None,
) -> str:
    """Raid the first candidate that accepts it, advancing past targets that
    block raids. Stops on any other error. max_attempts caps raid POSTs
    (Twitch allows only 10 per 10 minutes) regardless of candidates found.
    """
    candidates = find_raid_candidates(
        game_name, max_viewers=max_viewers, user_id=user_id
    )
    if isinstance(candidates, str):
        return candidates

    try:
        token = get_token_for_user(user_id)
        my_id, login = get_broadcaster_id(token)
    except NotConnectedError:
        return NEEDS_CONNECT
    except Exception as exc:  # noqa: BLE001
        return f"Error preparing raid: {exc}"

    attempts = 0
    for target in candidates:
        if attempts >= max_attempts:
            break
        attempts += 1
        try:
            status, message = _attempt_raid(
                token, my_id, login, target["broadcaster_id"]
            )
        except requests.HTTPError as exc:
            resp = exc.response  # type: ignore[assignment]
            detail = resp.text.strip() if resp is not None else str(exc)
            return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
        except Exception as exc:  # noqa: BLE001
            return f"Error starting raid: {exc}"

        if status == _RAID_SUCCESS:
            picked = (
                f"Picked raid target: {target['user_name']} (@{target['user_login']}) "
                f"with {target['viewer_count']} viewers in '{game_name}'."
            )
            return f"{picked}\n{message}"

        if status == _RAID_NOT_ALLOWED:
            continue

        return message  # rate-limited / not-live / error: all terminal

    return (
        f"Tried {attempts} channel(s) but none accepted the raid right now. "
        "Try a different category or run it again."
    )


def create_clip(user_id: "str | None" = None) -> str:
    """Capture a clip of the live stream. Requires being live; processes
    asynchronously (HTTP 202). Returns the public + edit URLs. Never raises.
    """
    try:
        token = get_token_for_user(user_id)
        my_id, login = get_broadcaster_id(token)

        resp = requests.post(
            f"{HELIX_BASE}/clips",
            headers=_auth_headers(token),
            params={"broadcaster_id": my_id},
            timeout=30,
        )

        if resp.status_code == 202:
            data = (resp.json().get("data") or [{}])[0]
            clip_id = data.get("id", "")
            edit_url = data.get("edit_url", "")
            public_url = (
                f"https://clips.twitch.tv/{clip_id}" if clip_id else "(unknown)"
            )
            return (
                f"Clip created from '{login}'!\n"
                f"  Public URL: {public_url}\n"
                f"  Edit URL:   {edit_url}\n"
                "Note: the clip may take a few seconds to finish processing before "
                "it's viewable."
            )

        body = resp.text.strip()
        low = body.lower()
        if resp.status_code in (404, 400) and (
            "offline" in low or "not currently live" in low or "no clip" in low
        ):
            return (
                "Error: you need to be LIVE on Twitch to create a clip. "
                "Start your stream, then try again."
            )
        if resp.status_code in (400, 401, 403, 404):
            return (
                f"Error: Twitch couldn't create the clip (HTTP {resp.status_code}): {body}. "
                "Note: you must be live to clip your stream."
            )
        return f"Error: Twitch rejected the clip (HTTP {resp.status_code}): {body}"
    except NotConnectedError:
        return NEEDS_CONNECT
    except requests.HTTPError as exc:
        resp = exc.response  # type: ignore[assignment]
        detail = resp.text.strip() if resp is not None else str(exc)
        return f"Error talking to Twitch (HTTP {getattr(resp, 'status_code', '?')}): {detail}"
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly string
        return f"Error creating clip: {exc}"


def get_clip_thumbnail(clip_id: str, user_id: "str | None" = None) -> "str | None":
    """Fetch the real thumbnail_url for clip_id via Get Clips. Best-effort —
    returns None on any problem so the caller just falls back to the text link.
    """
    try:
        if not clip_id:
            return None
        token = get_token_for_user(user_id)
        resp = requests.get(
            f"{HELIX_BASE}/clips",
            headers=_auth_headers(token),
            params={"id": clip_id},
            timeout=30,
        )
        data = resp.json().get("data") or [] if resp.status_code == 200 else []
        thumb = (data[0].get("thumbnail_url") or "") if data else ""
        logger.info(
            "get_clip_thumbnail clip_id=%s http=%s clip_found=%s thumbnail_url=%s",
            clip_id,
            resp.status_code,
            bool(data),
            thumb or "<none>",
        )
        if data:
            logger.info(
                "get_clip_thumbnail clip_id=%s full clip data=%r", clip_id, data[0]
            )
        if resp.status_code != 200 or not data:
            return None
        return thumb or None
    except NotConnectedError:
        logger.info("get_clip_thumbnail clip_id=%s -> not connected", clip_id)
        return None
    except Exception as exc:  # noqa: BLE001 - best-effort; any failure means "no image"
        logger.info("get_clip_thumbnail clip_id=%s -> error: %s", clip_id, exc)
        return None


if __name__ == "__main__":
    # Smoke-checks OAuth config + DB wiring; actions themselves run through the agent.
    print("=" * 70)
    print("twitchy OAuth config check")
    print("=" * 70)
    oauth_store.init_db()
    print(f"  redirect URI : {REDIRECT_URI}")
    print(f"  scopes       : {' '.join(SCOPES)}")
    print(f"  client id set: {bool(CLIENT_ID)}")
    print(f"  token DB     : {oauth_store.DB_PATH}")
    try:
        url, state = build_authorize_url("cli-test-sender")
        print(f"  sample state : {state}")
        print(f"  authorize URL: {url}")
    except Exception as exc:  # noqa: BLE001
        print(f"  build_authorize_url error: {exc}")
