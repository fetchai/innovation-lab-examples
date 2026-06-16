from __future__ import annotations

"""Gmail Chat uAgent – minimal version without separate MCP adapter.

This mirrors the pattern used by `booking_chat_agent.py`: one Agent that
exposes ONLY the conversational Gmail chat protocol.  The FastMCP Gmail server
(`gmail_chat_uagent.server`) still needs to be running separately (on port
8001 or `$GMAIL_MCP_PORT`) so OpenAI can reach the `/sse/` endpoint.
"""

import os  # noqa: E402
import sys  # noqa: E402
import pathlib  # noqa: E402
import json  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from uagents import Agent, Context, Model  # noqa: E402
from gmail_chat_proto import (  # noqa: E402
    _run_gmail_tool,
    SESSIONS_KEY,
    CURRENT_SESSION_DATA,
    _create_chat_message,
)
import server as gmail_server  # noqa: E402

gmail_auth = gmail_server.gmail_auth


class OAuthRequest(Model):
    session_id: str
    auth_code: str


class OAuthResponse(Model):
    success: bool
    message: str


load_dotenv()

# Ensure the project root (parent of this file) is on sys.path so that
# `import gmail_chat_uagent.*` works when running the script from inside the
# gmail_chat_uagent directory.
PARENT = pathlib.Path(__file__).resolve().parent.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

# Try import package path then fallback
try:
    from gmail_chat_uagent.gmail_chat_proto import chat_proto
except ModuleNotFoundError:
    from gmail_chat_proto import chat_proto  # type: ignore

# ---------------------------------------------------------------------------
# Agent configuration (env-override friendly)
# ---------------------------------------------------------------------------

AGENT_PORT = int(os.getenv("GMAIL_CHAT_AGENT_PORT", "8088"))
AGENT_NAME = os.getenv("GMAIL_CHAT_AGENT_NAME", "gmail_chat_agent")
AGENT_SEED = os.getenv("GMAIL_CHAT_AGENT_SEED", "deterministic_calendar_chat_seed")

agent = Agent(name=AGENT_NAME, port=AGENT_PORT, seed=AGENT_SEED, mailbox=True)

# Lifecycle logging helpers


@agent.on_event("startup")
async def _on_start(ctx: Context):
    ctx.logger.info("🚀 Gmail chat agent online – address: %s", agent.address)


@agent.on_event("shutdown")
async def _on_shutdown(ctx: Context):
    ctx.logger.info("🛑 Gmail chat agent shutting down.")


# Include chat protocol

agent.include(chat_proto, publish_manifest=True)

# ---------------------------------------------------------------------------
# REST endpoint to accept OAuth codes posted by oauth_server.py
# ---------------------------------------------------------------------------


@agent.on_rest_post("/oauth/callback", OAuthRequest, OAuthResponse)
async def _handle_oauth(ctx: Context, req: OAuthRequest) -> OAuthResponse:  # noqa: D401
    sid = req.session_id
    code = req.auth_code.strip()
    ctx.logger.info("🌐 [REST] Received OAuth code for session %s", sid)

    # Load existing sessions
    try:
        sessions_raw = ctx.storage.get(SESSIONS_KEY) or "{}"
        sessions = (
            json.loads(sessions_raw) if isinstance(sessions_raw, str) else sessions_raw
        )
    except Exception:
        sessions = {}

    session_data = sessions.get(sid, {"messages": []})
    ctx.logger.info(
        "🌐 [REST] Session found=%s keys=%s",
        bool(sid in sessions),
        list(session_data.keys()),
    )

    # If already authenticated, ignore duplicate callback
    if session_data.get("gmail_authenticated"):
        ctx.logger.info(
            "🌐 [REST] Session already authenticated – ignoring duplicate callback"
        )
        return OAuthResponse(success=True, message="Already authenticated")

    # Prepare token path
    tdir = pathlib.Path(os.getenv("GMAIL_TOKENS_DIR", ".tokens"))
    tdir.mkdir(exist_ok=True)
    tpath = tdir / f"oauth_tokens_{sid}.json"

    session_data["tokens_path"] = str(tpath)
    session_data["auth_code"] = code
    ctx.logger.info("🌐 [REST] Saved tokens_path and auth_code to session_data")

    # Complete OAuth via FastMCP
    session_ctx = {"tokens_path": str(tpath)}
    CURRENT_SESSION_DATA.set(session_ctx)
    try:
        ctx.logger.info("🌐 [REST] Calling complete_oauth via FastMCP …")
        out = await _run_gmail_tool("complete_oauth", {"auth_code": code})
        ctx.logger.info("🌐 [REST] complete_oauth raw response: %s", out[:200])
        res = json.loads(out)
        # If flow not initialised, run setup_oauth then retry
        if (
            not res.get("success")
            and "flow not initialised" in res.get("error", "").lower()
        ):
            ctx.logger.info(
                "🌐 [REST] Flow missing – calling setup_oauth then retrying complete_oauth"
            )
            await _run_gmail_tool("setup_oauth", {"session_id": sid})
            out = await _run_gmail_tool("complete_oauth", {"auth_code": code})
            res = json.loads(out)
    finally:
        CURRENT_SESSION_DATA.set({})

    if not res.get("success"):
        msg = res.get("error", "OAuth failed")
        return OAuthResponse(success=False, message=msg)

    # Load token JSON, then delete file
    try:
        with open(tpath, "r", encoding="utf-8") as tf:
            session_data["token_json"] = json.load(tf)
        os.remove(tpath)
    except Exception as f_err:
        ctx.logger.warning(
            "🌐 [REST] Could not read / delete temp token file: %s", f_err
        )

    session_data["gmail_authenticated"] = True
    session_data.pop("awaiting_auth_code", None)
    session_data.pop("oauth_link_sent", None)

    sessions[sid] = session_data
    ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
    ctx.logger.info("🌐 [REST] Session updated & stored; gmail_authenticated=True")

    # Notify user if we know their address
    if addr := session_data.get("sender_address"):
        ctx.logger.info("🌐 [REST] Notifying sender %s", addr)
        await ctx.send(
            addr,
            _create_chat_message(
                text="✅ Authentication successful! You can now ask me to read, send or manage your Gmail messages."
            ),
        )

    return OAuthResponse(success=True, message="OAuth completed and tokens stored")


# Entrypoint

if __name__ == "__main__":
    agent.run()
