from __future__ import annotations

import os, sys, pathlib, json
from dotenv import load_dotenv
from uagents import Agent, Context, Model

load_dotenv()

PARENT = pathlib.Path(__file__).resolve().parent.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))


from calendar_chat_proto import chat_proto
import json, pathlib
from calendar_chat_proto import (_run_cal_tool, CURRENT_SESSION_DATA, _create_msg, SESSIONS_KEY)


class OAuthRequest(Model):
    session_id: str
    auth_code: str


class OAuthResponse(Model):
    success: bool
    message: str


AGENT_PORT = int(os.getenv("CAL_CHAT_AGENT_PORT", "8089"))
AGENT_NAME = os.getenv("CAL_CHAT_AGENT_NAME", "calendar_chat_agent")
AGENT_SEED = os.getenv("CAL_CHAT_AGENT_SEED", "deterministic_calendar_seed")

agent = Agent(name=AGENT_NAME, port=AGENT_PORT, seed=AGENT_SEED, mailbox=True)

agent.include(chat_proto, publish_manifest=True)

# REST callback similar to Gmail agent


@agent.on_rest_post("/oauth/callback", OAuthRequest, OAuthResponse)
async def _cb(ctx: Context, req: OAuthRequest) -> OAuthResponse:
    sid = req.session_id
    code = req.auth_code.strip()

    ctx.logger.info("🌐 [REST] Received OAuth code for session %s", sid)

    # Load existing sessions from storage
    try:
        sessions_raw = ctx.storage.get(SESSIONS_KEY) or "{}"
        sessions = json.loads(sessions_raw) if isinstance(sessions_raw, str) else sessions_raw
    except Exception:
        sessions = {}

    data = sessions.get(sid, {})
    ctx.logger.info("🌐 [REST] Session found=%s keys=%s", bool(sid in sessions), list(data.keys()))

    # Ignore duplicate callbacks if already authenticated
    if data.get("cal_authenticated"):
        ctx.logger.info("🌐 [REST] Session already authenticated – ignoring duplicate callback")
        return OAuthResponse(success=True, message="Already authenticated")

    # Prepare a unique token file for this session
    tdir = pathlib.Path(os.getenv("CAL_TOKENS_DIR", ".tokens"))
    tdir.mkdir(exist_ok=True)
    tpath = tdir / f"oauth_tokens_{sid}.json"

    data["tokens_path"] = str(tpath)
    data["auth_code"] = code
    ctx.logger.info("🌐 [REST] Saved tokens_path and auth_code to session_data")

    # Finish OAuth via FastMCP
    CURRENT_SESSION_DATA.set({"tokens_path": str(tpath)})
    try:
        ctx.logger.info("🌐 [REST] Calling complete_oauth via FastMCP …")
        out = await _run_cal_tool("complete_oauth", {"auth_code": code})
        ctx.logger.info("🌐 [REST] complete_oauth raw response: %s", out[:200])
        res = json.loads(out)
        if not res.get("success") and "flow not initialised" in res.get("error", "").lower():
            ctx.logger.info("🌐 [REST] Flow missing – calling setup_oauth then retrying complete_oauth")
            await _run_cal_tool("setup_oauth", {"session_id": sid})
            out = await _run_cal_tool("complete_oauth", {"auth_code": code})
            res = json.loads(out)
    finally:
        CURRENT_SESSION_DATA.set({})

    if not res.get("success"):
        msg = res.get("error", "OAuth failed")
        ctx.logger.error("🌐 [REST] OAuth failed: %s", msg)
        return OAuthResponse(success=False, message=msg)

    # ------------------------------------------------------------------
    # Persist credentials for future tool calls
    # ------------------------------------------------------------------
    # The FastMCP server always writes credentials to its canonical path
    # (calendar_chat_uagent/oauth_tokens.json).  We load that file and keep
    # both the JSON and the *canonical* path in the session so that
    # _run_cal_tool can later rebuild temp files if needed.

    from server import TOKENS_PATH as CANONICAL_TOKENS_PATH  # local import to avoid cycles

    try:
        with open(CANONICAL_TOKENS_PATH, "r", encoding="utf-8") as cf:
            data["token_json"] = json.load(cf)
        # Replace the session tokens_path with the canonical one
        data["tokens_path"] = str(CANONICAL_TOKENS_PATH)
        # Clean up the earlier temp file if it still exists
        try:
            if tpath.exists():
                tpath.unlink()
        except Exception:
            pass
        ctx.logger.info("🌐 [REST] Token JSON loaded from canonical path %s", CANONICAL_TOKENS_PATH)
    except Exception as f_err:
        ctx.logger.warning("🌐 [REST] Failed to load canonical token file %s: %s", CANONICAL_TOKENS_PATH, f_err)

    data["cal_authenticated"] = True
    data.pop("awaiting_auth_code", None)
    data.pop("oauth_link_sent", None)

    sessions[sid] = data
    ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
    ctx.logger.info("🌐 [REST] Session updated & stored; cal_authenticated=True")

    # Notify the chat user if we know their address
    if addr := data.get("sender_address"):
        ctx.logger.info("🌐 [REST] Notifying sender %s", addr)
        await ctx.send(addr, _create_msg("✅ Calendar authorisation successful! You can now ask me about your calendar."))

    return OAuthResponse(success=True, message="OAuth completed and tokens stored")


@agent.on_event("startup")
async def _start(ctx: Context):
    ctx.logger.info("📅 Calendar chat agent online – address: %s", agent.address)


@agent.on_event("shutdown")
async def _stop(ctx: Context):
    ctx.logger.info("🛑 Calendar chat agent shutting down.")


if __name__ == "__main__":
    agent.run() 