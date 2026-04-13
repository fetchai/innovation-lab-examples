"""
Optional Agentverse mailbox registration without the Inspector browser flow.

ASI:One delivers chat to the mailbox on Agentverse. Until the mailbox exists, the local
agent logs `Agent mailbox not found` and never receives messages.

Setting `AGENTVERSE_API_TOKEN` triggers background POSTs to the local agent's `/connect`
endpoint (same as Inspector → Connect → Mailbox), which registers the mailbox.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Wait for the uAgents ASGI server to bind before POST /connect.
_DEFAULT_DELAY = float(os.getenv("MAILBOX_CONNECT_DELAY_SECONDS", "15"))
_RETRIES = int(os.getenv("MAILBOX_CONNECT_RETRIES", "6"))
_RETRY_INTERVAL = float(os.getenv("MAILBOX_CONNECT_RETRY_INTERVAL", "5"))


def schedule_mailbox_registration(
    port: int, user_token: str, delay_seconds: float | None = None
) -> None:
    """
    POST `AgentverseConnectRequest` to `http://127.0.0.1:{port}/connect` after a delay,
    with retries (connection refused is common if the server is not ready yet).
    """
    token = (user_token or "").strip()
    if not token:
        return

    def _run() -> None:
        wait = delay_seconds if delay_seconds is not None else _DEFAULT_DELAY
        time.sleep(wait)
        url = f"http://127.0.0.1:{port}/connect"
        body = json.dumps({"user_token": token, "agent_type": "mailbox"}).encode(
            "utf-8"
        )

        last_err: str | None = None
        for attempt in range(1, _RETRIES + 1):
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    status = resp.status
                    raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    parsed = {}
                success = (
                    parsed.get("success", True) if isinstance(parsed, dict) else True
                )
                detail = parsed.get("detail") if isinstance(parsed, dict) else None
                if success:
                    logger.info(
                        "Mailbox registration via /connect OK (HTTP %s, attempt %s/%s). "
                        "Look for: 'Successfully registered as mailbox agent in Agentverse'.",
                        status,
                        attempt,
                        _RETRIES,
                    )
                    return
                logger.error(
                    "Mailbox registration /connect returned success=false (attempt %s/%s). detail=%s body=%s",
                    attempt,
                    _RETRIES,
                    detail,
                    raw[:800],
                )
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                last_err = f"HTTP {e.code}: {err_body[:800]}"
                logger.warning(
                    "Mailbox registration via /connect failed HTTP %s (attempt %s/%s): %s",
                    e.code,
                    attempt,
                    _RETRIES,
                    err_body[:400],
                )
            except urllib.error.URLError as e:
                last_err = str(e)
                logger.warning(
                    "Mailbox registration via /connect failed (attempt %s/%s): %s",
                    attempt,
                    _RETRIES,
                    e,
                )
            except Exception:
                logger.exception(
                    "Mailbox registration attempt %s/%s failed", attempt, _RETRIES
                )

            if attempt < _RETRIES:
                time.sleep(_RETRY_INTERVAL)

        logger.error(
            "Mailbox registration gave up after %s attempts. Last error: %s. "
            "Is the agent listening on port %s? Try: curl -s http://127.0.0.1:%s/agent_info",
            _RETRIES,
            last_err,
            port,
            port,
        )

    threading.Thread(
        target=_run, name="agentverse-mailbox-connect", daemon=True
    ).start()
