from __future__ import annotations

"""Google Calendar Chat Protocol.

A uAgents chat protocol that lets end-users interact with Google Calendar via
FastMCP tools defined in `calendar_chat_uagent.server`.
"""

import asyncio, contextvars, json, logging, os, pathlib, sys
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

import httpx
from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
if not logger.handlers:
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(_ch)
logger.setLevel(logging.INFO)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o3-mini")
CAL_MCP_URL = os.getenv("CALENDAR_MCP_URL", "https://a6aca4fcb00e.ngrok-free.app/sse/")
MAX_HISTORY = int(os.getenv("MAX_CAL_CHAT_HISTORY", "10"))

# Import FastMCP server
import server as cal_server 
cal_mcp = cal_server.mcp
cal_auth = cal_server.calendar_auth

CURRENT_SESSION_DATA: contextvars.ContextVar[dict] = contextvars.ContextVar("CURRENT_SESSION_DATA")

# ---------------------------------------------------------------------------
# Helper to normalise FastMCP return values (copied from Gmail proto)
# ---------------------------------------------------------------------------


def _unwrap(result: Any) -> str:
    """Convert *result* from FastMCP into a plain JSON string for logging/parsing."""
    if isinstance(result, tuple) and result:
        result = result[0]
    if hasattr(result, "text"):
        return result.text  # type: ignore[attr-defined]
    if isinstance(result, list) and result and hasattr(result[0], "text"):
        return result[0].text  # type: ignore[attr-defined]
    if isinstance(result, (dict, list)):
        return json.dumps(result)
    return str(result)

# ---------------------------------------------------------------------------
# OpenAI *Responses* streaming helper – executes tool calls when present
# ---------------------------------------------------------------------------


async def _call_openai_responses(messages: List[Dict[str, str]]) -> str:
    """Stream /v1/responses events, execute MCP tool calls, and return final text."""

    transcript = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)

    TOOLS_BLOCK = [
        {
            "type": "mcp",
            "server_label": "cal_tools",
            "server_url": CAL_MCP_URL,
            "require_approval": "never",
        }
    ]

    payload: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "instructions": _SYSTEM_PROMPT,
        "input": transcript,
        "tool_choice": "auto",
        "tools": TOOLS_BLOCK,
        "truncation": "disabled",
        "max_tool_calls": 50,
        "reasoning": {"effort": "low"},
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    assistant_chunks: List[str] = []

    async with httpx.AsyncClient(timeout=90) as client:
        follow_payload = dict(payload)

        for _hop in range(10):  # limit hops to prevent loops
            async with client.stream("POST", "https://api.openai.com/v1/responses", json=follow_payload, headers=headers) as stream:
                async for raw in stream.aiter_lines():
                    if not raw.startswith("data:"):
                        continue
                    chunk = raw.removeprefix("data:").strip()
                    if not chunk:
                        continue

                    event = json.loads(chunk)
                    if not isinstance(event, dict):
                        continue

                    kind = event.get("type")

                    if kind in ("content_block_delta", "message_delta", "response.output_text.delta"):
                        delta = event.get("delta", {})
                        if isinstance(delta, dict):
                            assistant_chunks.append(delta.get("text", ""))
                        elif isinstance(delta, str):
                            assistant_chunks.append(delta)

                    elif kind == "tool_call":
                        pending = event["tool_calls"]
                        tool_outputs = []
                        for call in pending:
                            fn = call["function"]["name"]
                            args_json = call["function"].get("arguments") or "{}"
                            args_dict = json.loads(args_json)
                            out = await _run_cal_tool(fn, args_dict)
                            tool_outputs.append({"tool_call_id": call["id"], "output": out})

                        follow_payload = {
                            "model": OPENAI_MODEL,
                            "input": "",
                            "previous_response_id": event["response_id"],
                            "tool_outputs": tool_outputs,
                            "stream": True,
                        }
                        break  # ↺ continue outer loop with new payload
                else:
                    # No tool calls – final answer assembled
                    return "".join(assistant_chunks).strip()
    # Fallback – no response
    return "(no response)"

async def _run_cal_tool(fn: str, args: Dict[str, Any]) -> str:
    """Execute *fn* with *args* against Calendar MCP, with retry and temp-token file handling."""

    try:
        session_ctx = CURRENT_SESSION_DATA.get({})
    except LookupError:
        session_ctx = {}

    tokens_path = session_ctx.get("tokens_path")
    token_json = session_ctx.get("token_json")

    temp_created = False  # track whether we create a temp file this call

    # Case 1: we already have a valid tokens_path → ensure cal_auth points to it
    if tokens_path and os.path.exists(tokens_path):
        if getattr(cal_auth, "tokens_path", None) != str(tokens_path):
            cal_auth.tokens_path = str(tokens_path)
            cal_auth._service = None
    else:
        # Case 2: only in-memory token JSON available → write temp file
        if token_json:
            tdir = pathlib.Path(os.getenv("CAL_TOKENS_DIR", ".tokens"))
            tdir.mkdir(exist_ok=True)
            tokens_path = tokens_path or tdir / f"oauth_tokens_{uuid4()}.json"
            with open(tokens_path, "w", encoding="utf-8") as tf:
                json.dump(token_json, tf, indent=2)
            session_ctx["tokens_path"] = str(tokens_path)
            temp_created = True
            cal_auth.tokens_path = str(tokens_path)
            cal_auth._service = None

    async def _call_once():  # noqa: D401
        return await cal_mcp._mcp_call_tool(fn, args)  # type: ignore[attr-defined]

    for attempt in range(2):  # initial try + one retry on transient failure
        try:
            result = await _call_once()
            out = _unwrap(result)
            if temp_created and tokens_path and os.path.exists(tokens_path):
                try:
                    os.remove(tokens_path)
                except Exception:
                    pass
            return out
        except Exception as e:
            logger.warning("⚠️  TOOL ERROR (%s) attempt %s/2 – %s", fn, attempt + 1, e)
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
            if temp_created and tokens_path and os.path.exists(tokens_path):
                try:
                    os.remove(tokens_path)
                except Exception:
                    pass
            return json.dumps({"success": False, "error": str(e)})

    # Final fallback – should not reach here
    if temp_created and tokens_path and os.path.exists(tokens_path):
        try:
            os.remove(tokens_path)
        except Exception:
            pass
    return json.dumps({"success": False, "error": "Unknown tool failure"})

_SYSTEM_PROMPT = (
    "You are an AI assistant for Google Calendar and may only operate via the MCP\n"
    "tools provided: setup_oauth, complete_oauth, list_calendars, list_events,\n"
    "create_event, update_event, delete_event, search_events, get_free_busy,\n"
    "get_current_time.\n\n"
    "• list_events is the main tool for a user's agenda. Always call it with\n"
    "  { calendar_id: \"primary\", date: \"today\"|\"tomorrow\"|\"YYYY-MM-DD\" }.\n"
    "  If the user doesn't specify a date use \"today\" by default.\n"
    "  When replying, show each meeting's title, time range and its link field so\n"
    "  the user can open the Calendar event.\n"
    "• search_events is only for keyword searches across events.\n"
    "• get_free_busy accepts a calendar_id – use an email like bob@example.com\n"
    "  to check someone else’s availability. The API returns data only if that\n"
    "  calendar is shared with you (≥ free/busy) or you’re in the same Google\n"
    "  Workspace with free-busy visibility; otherwise it may be empty or 403.\n"
    "• If the user isn’t authenticated you must start with setup_oauth then\n"
    "  complete_oauth, but once cal_authenticated is True assume valid tokens.\n"
    "• Understand natural-language dates like ‘today’, ‘tomorrow’, ‘next Monday’\n"
    "  and convert them to ISO timestamps when calling tools.\n"
    "• Keep responses short, in Markdown, and avoid filler phrases."
)

chat_proto = Protocol(spec=chat_protocol_spec)
SESSIONS_KEY = "cal_chat_sessions"


def _create_msg(text: str, end: bool = False) -> ChatMessage:
    content: List[Any] = [TextContent(type="text", text=text)]
    if end:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


@chat_proto.on_message(ChatMessage)
async def _handle(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    sessions = json.loads(ctx.storage.get(SESSIONS_KEY) or "{}")
    sid = str(ctx.session)
    data = sessions.get(sid, {"messages": []})
    inbound = [b.text.strip() for b in msg.content if isinstance(b, TextContent)]
    # Always keep track of sender for later replies
    data["sender_address"] = sender

    ctx.logger.info("📨 inbound_texts=%s", inbound)

    # If the message is just a StartSessionContent block (no user text yet),
    # don’t respond – simply initialise / reset the session and wait.
    if any(isinstance(b, StartSessionContent) for b in msg.content):
        # Reset state for a fresh conversation
        data.clear()
        data.update({"messages": []})
        inbound = []  # Treat as no user input

    # Skip automatic replies when there is still no actual user text and we’re
    # not already waiting for an OAuth code – prevents sending the auth link
    # right after the session starts.
    if not inbound and not data.get("awaiting_auth_code"):
        ctx.logger.info("🔕 StartSessionContent only – waiting for user input before responding")
        sessions[sid] = data
        ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
        return

    token = CURRENT_SESSION_DATA.set(data)
    try:
        # --------------------------------------------------------------
        # Validate existing auth status on every message (tokens may have
        # been revoked or the agent restarted losing Flow instance)
        # --------------------------------------------------------------

        if data.get("cal_authenticated"):
            # Prepare token context so _run_cal_tool can rebuild temp file if necessary
            token_ctx: Dict[str, str] = {}
            if data.get("token_json"):
                token_ctx["token_json"] = data["token_json"]
            if data.get("tokens_path"):
                token_ctx["tokens_path"] = data["tokens_path"]
                cal_auth.tokens_path = data["tokens_path"]  # type: ignore[attr-defined]
                cal_auth._service = None

            if token_ctx:
                CURRENT_SESSION_DATA.set(token_ctx)

            try:
                status_raw = await _run_cal_tool("check_auth_status", {})
                status = json.loads(status_raw)
                if not status.get("authenticated"):
                    data["cal_authenticated"] = False
            except Exception as auth_err:
                ctx.logger.warning("Auth status check failed: %s", auth_err)
                data["cal_authenticated"] = False
            finally:
                if token_ctx:
                    CURRENT_SESSION_DATA.set({})

        # ------------------------------------------------------------------
        # 1. Handle authentication workflow (setup_oauth / complete_oauth)
        # ------------------------------------------------------------------

        ctx.logger.info("🔍 Auth status: authenticated=%s, awaiting_code=%s, inbound_text=%s", 
                        data.get("cal_authenticated"), 
                        data.get("awaiting_auth_code"), 
                        bool(inbound))

        if not data.get("cal_authenticated"):
            # Guard against duplicate sends
            if data.get("oauth_link_sent") and not data.get("awaiting_auth_code"):
                return

            # If awaiting OAuth completion, gently remind the user
            if data.get("awaiting_auth_code"):
                if inbound:
                    await ctx.send(sender, _create_msg("🔄 Still waiting for you to grant access in the browser popup. Once finished, just ask me your question again."))
                ctx.logger.debug("Waiting for OAuth completion; inbound=%s", inbound)
                sessions[sid] = data
                ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
                return

            # Start OAuth
            ctx.logger.info("🚀 Starting OAuth setup…")
            oauth_json = await _run_cal_tool("setup_oauth", {"session_id": sid})
            ctx.logger.info("📋 OAuth response: %s", oauth_json)
            oauth_data = json.loads(oauth_json)

            if not oauth_data.get("success"):
                err_msg = oauth_data.get("error", "Unknown error during OAuth setup")
                await ctx.send(sender, _create_msg(f"❌ Authentication setup failed: {err_msg}"))
                ctx.logger.error("❌ OAuth setup failed: %s", err_msg)
                return

            auth_url = oauth_data.get("auth_url", "")
            data["awaiting_auth_code"] = True
            data["oauth_link_sent"] = True

            await ctx.send(sender, _create_msg(
                f"Click the **Authorize Calendar** link below.\n\n[Authorize Calendar]({auth_url})\n\nOnce authorised, paste the code here or just ask your question again."
            ))
            ctx.logger.info("➡️  Auth link sent: %s", auth_url)

            sessions[sid] = data
            ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
            return

        # After authentication, remove old OAuth-instruction messages to prevent
        # the model from repeating them.
        if data.get("cal_authenticated") and data.get("messages"):
            def _looks_like_oauth_prompt(text: str) -> bool:
                t = text.lower()
                return "authorize" in t and "calendar" in t or "authentication" in t

            filtered = [
                m for m in data["messages"]
                if not (m.get("source") == "assistant" and _looks_like_oauth_prompt(m.get("content", "")))
            ]
            if len(filtered) != len(data["messages"]):
                data["messages"] = filtered
                sessions[sid] = data
                ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))

        # build conversation for OpenAI Responses
        messages: List[Dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        # Add authenticated note immediately so it has high priority
        if data.get("cal_authenticated"):
            messages.append({
                "role": "system",
                "content": "The user is already authenticated with valid Google Calendar tokens. Use the calendar tools directly; do NOT request OAuth again."})

        messages += [
            {"role": m.get("source", "assistant"), "content": m.get("content", "")} for m in data.get("messages", [])
        ]

        if inbound:
            messages.append({"role": "user", "content": "\n".join(inbound)})
            data["messages"].append({"source": "human", "content": "\n".join(inbound)})

        # truncate history
        if len(data["messages"]) > MAX_HISTORY * 2:
            data["messages"] = data["messages"][-MAX_HISTORY * 2 :]

        # call OpenAI Responses
        answer = await _call_openai_responses(messages)
        data["messages"].append({"source": "assistant", "content": answer})
        await ctx.send(sender, _create_msg(answer))
        ctx.logger.info(">> session=%s to=%s content=%s", sid, sender, answer[:120].replace("\n", " "))
        sessions[sid] = data
        ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
    finally:
        CURRENT_SESSION_DATA.reset(token)


@chat_proto.on_message(ChatAcknowledgement)
async def _ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass 