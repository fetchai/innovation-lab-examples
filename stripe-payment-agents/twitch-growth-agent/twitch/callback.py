"""Hosted OAuth redirect endpoint. Raw ASGI app served by uvicorn at the path
of TWITCH_REDIRECT_URI; on GET ?code=&state= it hands off to
twitch_oauth.handle_oauth_callback to exchange the code and store the token.

For local dev, point ngrok at OAUTH_CALLBACK_PORT and register that HTTPS URL
as TWITCH_REDIRECT_URI in the Twitch console.
"""

import asyncio
import logging
import os
import queue
import threading
from urllib.parse import parse_qs, urlparse

import uvicorn

from .oauth import REDIRECT_URI, handle_oauth_callback

logger = logging.getLogger(__name__)

# This server runs in its own thread with no agent Context, so it can't send a
# chat message itself. Instead it queues a "resume signal" that the agent's
# on_interval handler drains and uses to pick up where the user left off.
_resume_queue: "queue.Queue[dict]" = queue.Queue()


def drain_resume_signals() -> "list[dict]":
    """Pop all pending connect-resume signals (non-blocking). Called by the agent.

    Each signal is ``{"sender": <asi1 sender id>, "pending": <stashed job|None>}``.
    """
    signals: "list[dict]" = []
    while True:
        try:
            signals.append(_resume_queue.get_nowait())
        except queue.Empty:
            break
    return signals


_parsed = urlparse(REDIRECT_URI)
CALLBACK_PATH = _parsed.path or "/callback"
# Explicit override, else the redirect URI's port, else 3000.
CALLBACK_PORT = int(os.getenv("OAUTH_CALLBACK_PORT", str(_parsed.port or 3000)))
CALLBACK_HOST = os.getenv("OAUTH_CALLBACK_HOST", "0.0.0.0")


def _page(title: str, body: str) -> bytes:
    return (
        f"<html><body style='font-family:sans-serif;max-width:520px;margin:60px auto'>"
        f"<h2>{title}</h2><p>{body}</p></body></html>"
    ).encode()


async def _respond(send, status: int, html: bytes):
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"text/html; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": html})


async def app(scope, receive, send):
    """Raw ASGI handler for the Twitch OAuth redirect."""
    if scope["type"] != "http":
        return
    if scope.get("path") != CALLBACK_PATH or scope.get("method") != "GET":
        await _respond(send, 404, _page("Not found", "Nothing here."))
        return

    params = parse_qs(scope.get("query_string", b"").decode())
    code = (params.get("code") or [None])[0]
    state = (params.get("state") or [None])[0]
    err = (params.get("error_description") or params.get("error") or [None])[0]

    if err:
        await _respond(send, 400, _page("Authorization failed", err))
        return
    if not code or not state:
        await _respond(
            send, 400, _page("Missing parameters", "No code/state in the redirect.")
        )
        return

    try:
        result = await asyncio.to_thread(handle_oauth_callback, code, state)
    except Exception as exc:  # noqa: BLE001 - show a friendly page, log for debugging
        logger.error("oauth callback failed: %s", exc)
        await _respond(send, 400, _page("Could not connect", f"{exc}"))
        return

    # Hand the agent a resume signal so it can pick up where the user left off.
    sender = result.get("sender")
    if sender:
        _resume_queue.put({"sender": sender, "pending": result.get("pending")})

    await _respond(
        send,
        200,
        _page(
            f"Twitch connected for {result.get('login', 'your channel')}!",
            "You're all set — head back to the chat and I'll automatically pick up "
            "right where you left off. (You can close this tab.)",
        ),
    )


def start_callback_server() -> threading.Thread:
    """Start the callback server in a daemon thread (non-blocking)."""
    config = uvicorn.Config(
        app, host=CALLBACK_HOST, port=CALLBACK_PORT, log_level="warning"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="oauth-callback")
    thread.start()
    logger.info(
        "oauth callback listening on %s:%d%s",
        CALLBACK_HOST,
        CALLBACK_PORT,
        CALLBACK_PATH,
    )
    return thread


if __name__ == "__main__":
    # Standalone run for local testing (Ctrl-C to stop).
    from twitch import store as oauth_store

    oauth_store.init_db()
    uvicorn.run(app, host=CALLBACK_HOST, port=CALLBACK_PORT, log_level="info")
