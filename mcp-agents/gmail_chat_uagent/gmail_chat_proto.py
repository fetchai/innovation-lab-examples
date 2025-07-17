from __future__ import annotations

"""Gmail Chat Protocol

A uAgents chat protocol that lets end-users interact with Gmail via FastMCP
tools (defined in `snrauto/python-gmail-mcp-uagents/server.py`).  Each agent
conversation (``ctx.session``) gets its **own** OAuth token file which is
referenced in ``ctx.storage`` so that multiple parallel users can authorise
independently.

Flow:
1. First message – if the session is **not** authenticated we respond with an
   OAuth URL returned by the `setup_oauth` tool and set
   ``awaiting_auth_code = True``.
2. Once the user posts the Google **auth code** we call `complete_oauth`, mark
   the session as authenticated and store the unique ``tokens_path`` so every
   subsequent tool call re-uses the correct credentials.
3. For normal chat we forward the full transcript to the OpenAI *Responses* API
   enabling automatic tool-calling.  When the model emits tool calls we execute
   them locally through FastMCP and feed the outputs back until we obtain the
   final assistant reply.

Only a handful of helpers are carried over from the much larger MOT booking
agent to keep the logic lightweight and easy to reason about.
"""

import asyncio
import contextvars
import importlib
import json
import logging
import os
import pathlib
import sys
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
# ExternalStorage removed – we no longer back up tokens externally

load_dotenv()

# ---------------------------------------------------------------------------
# Logger (must exist before any code references it)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# External storage disabled – everything stays local
# ---------------------------------------------------------------------------

external_storage = None

# IO logger for raw chat traffic (optional)
chat_io_logger = logging.getLogger("gmail_chat_io")
if not any(isinstance(h, logging.FileHandler) for h in chat_io_logger.handlers):
    _fh2 = logging.FileHandler(os.getenv("GMAIL_CHAT_IO_LOG", "gmail_chat_io.log"), mode="a", encoding="utf-8")
    _fh2.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _fh2.setLevel(logging.DEBUG)
    chat_io_logger.addHandler(_fh2)
chat_io_logger.setLevel(logging.DEBUG)

# Add console output so logs are visible when running the chat agent
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _ch.setLevel(logging.INFO)
    logger.addHandler(_ch)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError("OPENAI_API_KEY must be set for Gmail chat proto")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o3-mini")
GMAIL_MCP_URL = os.getenv("GMAIL_MCP_URL", "https://a6aca4fcb00e.ngrok-free.app/sse/")
MAX_HISTORY = int(os.getenv("MAX_GMAIL_CHAT_HISTORY", "10"))

# File-level logs for later diagnostics
LOG_FILE = os.getenv("GMAIL_CHAT_LOG", "gmail_chat_debug.log")
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    _fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    _fh.setLevel(logging.DEBUG)
    logger.addHandler(_fh)

# ---------------------------------------------------------------------------
# Import Gmail FastMCP server (tools) so we can call them directly
# ---------------------------------------------------------------------------

# Import the local FastMCP Gmail server. Works both when the module is part of
# the package (normal import) and when executed directly (no parent package).
try:
    from . import server as gmail_server  # type: ignore
except ImportError:  # running as plain script – fallback to absolute import
    import importlib, pathlib, sys
    CURRENT_DIR = pathlib.Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    gmail_server = importlib.import_module("server")  # type: ignore

gmail_mcp = gmail_server.mcp  # FastMCP instance
gmail_auth = gmail_server.gmail_auth  # shared GmailAuth helper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_chat_message(text: str, end_session: bool = False) -> ChatMessage:
    """Wrap *text* into a ChatMessage with correct timestamp."""
    content: List[Any] = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


def _unwrap(result: Any) -> str:
    """Normalise various FastMCP return types to a plain JSON string."""
    if isinstance(result, tuple) and result:
        result = result[0]
    if hasattr(result, "text"):
        return result.text  # type: ignore[attr-defined]
    if isinstance(result, list) and result and hasattr(result[0], "text"):
        return result[0].text  # type: ignore[attr-defined]
    if isinstance(result, (dict, list)):
        return json.dumps(result)
    return str(result)

# ContextVar to pass the current *session_data* to helper fns like _run_gmail_tool
CURRENT_SESSION_DATA: contextvars.ContextVar[dict] = contextvars.ContextVar("CURRENT_SESSION_DATA")

# ---------------------------------------------------------------------------
# FastMCP tool execution helper (automatic retry + token-path injection)
# ---------------------------------------------------------------------------

async def _run_gmail_tool(fn_name: str, args: Dict[str, Any]) -> str:
    """Execute *fn_name* with *args* against the Gmail FastMCP server."""

    logger.debug("��️  CALLING TOOL: %s  args=%s", fn_name, args)

    # Ensure the shared gmail_auth instance points at the session-specific token file
    try:
        session_ctx = CURRENT_SESSION_DATA.get()
    except LookupError:
        session_ctx = {}

    tokens_path = session_ctx.get("tokens_path")
    token_json = session_ctx.get("token_json")

    temp_created = False  # track whether we create a temp token file this call

    # If we only have in-memory token JSON, recreate the file so gmail_auth can read it
    if token_json and (not tokens_path or not os.path.exists(tokens_path)):
        tokens_dir = pathlib.Path(os.getenv("GMAIL_TOKENS_DIR", ".tokens"))
        tokens_dir.mkdir(exist_ok=True)
        tokens_path = tokens_path or tokens_dir / f"oauth_tokens_{uuid4()}.json"
        with open(tokens_path, "w", encoding="utf-8") as tf:
            json.dump(token_json, tf, indent=2)
        session_ctx["tokens_path"] = str(tokens_path)
        temp_created = True

    if tokens_path and getattr(gmail_auth, "tokens_path", None) != str(tokens_path):
        gmail_auth.tokens_path = str(tokens_path)  # type: ignore[attr-defined]
        gmail_auth._service = None  # reset cached client

    async def _call_once():  # noqa: D401
        return await gmail_mcp._mcp_call_tool(fn_name, args)  # type: ignore[attr-defined]

    for attempt in range(2):  # initial try + one retry on transient failure
        try:
            result = await _call_once()
            out = _unwrap(result)
            # Clean up the temp token file if we created it for this call
            if temp_created and tokens_path and os.path.exists(tokens_path):
                try:
                    os.remove(tokens_path)
                except Exception:
                    pass
            return out
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("⚠️  TOOL ERROR (%s) attempt %s/2 – %s", fn_name, attempt + 1, e)
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
            # on final failure also attempt cleanup
            if temp_created and tokens_path and os.path.exists(tokens_path):
                try:
                    os.remove(tokens_path)
                except Exception:
                    pass
            return json.dumps({"success": False, "error": str(e)})

    if temp_created and tokens_path and os.path.exists(tokens_path):
        try:
            os.remove(tokens_path)
        except Exception:
            pass
    return json.dumps({"success": False, "error": "Unknown tool failure"})

# ---------------------------------------------------------------------------
# OpenAI *Responses* streaming helper (spec compliant)
# ---------------------------------------------------------------------------

async def _call_openai_responses(messages: List[Dict[str, str]]) -> str:
    """Stream /v1/responses events, execute tool calls, return final assistant text."""

    transcript = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)

    TOOLS_BLOCK = [
        {
            "type": "mcp",
            "server_label": "gmail_tools",
            "server_url": GMAIL_MCP_URL,
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

        for hop in range(10):  # generous limit for tool chaining
            async with client.stream("POST", "https://api.openai.com/v1/responses", json=follow_payload, headers=headers) as stream:
                async for raw in stream.aiter_lines():
                    if not raw.startswith("data:"):
                        continue
                    chunk = raw.removeprefix("data:").strip()
                    if not chunk:
                        continue

                    event = json.loads(chunk)
                    if not isinstance(event, dict):
                        # Skip unexpected string/array events such as "DONE"
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
                            out = await _run_gmail_tool(fn, args_dict)
                            tool_outputs.append({"tool_call_id": call["id"], "output": out})

                        # Prepare follow-up request (still streaming)
                        follow_payload = {
                            "model": OPENAI_MODEL,
                            "input": "",
                            "previous_response_id": event["response_id"],
                            "tool_outputs": tool_outputs,
                            "stream": True,
                        }
                        break  # ↺ go to next hop
                else:
                    # Stream finished without tool calls – final answer ready
                    return "".join(assistant_chunks).strip()
        else:
            raise RuntimeError("Streaming run exceeded hop limit – possible tool loop?")

# ---------------------------------------------------------------------------
# System prompt – keeps the model focused on Gmail tasks only
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an AI assistant for Gmail and may **only** operate via the MCP\n"
    "tools provided: setup_oauth, complete_oauth, send_email, list_emails,\n"
    "read_email, delete_email, delete_last_sent_email, get_profile.\n\n"
    "Guidelines:\n"
    "1. Never expose raw JSON or tool-call blocks to the user – translate them\n"
    "   into clear natural-language replies.\n"
    "2. If the user is not authenticated you **must** start the OAuth flow\n"
    "   with `setup_oauth` followed by `complete_oauth`.\n"
    "3. When the user asks to *read* or *delete* an email but hasn’t supplied\n"
    "   a message-ID, first call `list_emails` (optionally with a query such\n"
    "   as \"from:devpost.com\") and present the top results in a numbered\n"
    "   list that shows Subject, From, Date **and** the message-ID.\n"
    "   Then ask the user which ID they’d like to act on, or if they want the\n"
    "   first one you can proceed automatically.\n"
    "4. Keep responses short, friendly Markdown.\n"
    "5. For batch operations (e.g. delete many matching emails) execute all\n"
    "   required tool calls silently first, then reply once when the entire\n"
    "   task is finished; do not ask the user again unless clarification is\n"
    "   truly needed.\n"
    "6. Do not send progress fillers like 'One moment please' or 'Searching…'.\n"
    "   Instead, carry out the necessary tool calls and respond only with the\n"
    "   final result or a clarifying question."
)

# ---------------------------------------------------------------------------
# Protocol definition
# ---------------------------------------------------------------------------

chat_proto = Protocol(spec=chat_protocol_spec)

# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

SESSIONS_KEY = "gmail_chat_sessions"

@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):  # noqa: C901 – complex but readable

    # Acknowledge immediately (for client UX)
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))

    # 1) Load per-session persisted data
    try:
        sessions_raw = ctx.storage.get(SESSIONS_KEY) or "{}"
        sessions: Dict[str, Any] = json.loads(sessions_raw) if isinstance(sessions_raw, str) else sessions_raw
    except Exception:
        sessions = {}

    session_id = str(ctx.session)
    session_data: Dict[str, Any] = sessions.get(session_id, {"messages": []})
    # Always store the sender address for this session
    session_data["sender_address"] = sender

    # If external token asset exists but local tokens file is missing, download it
    if (
        external_storage
        and session_data.get("tokens_asset_id")
        and not session_data.get("tokens_path")
    ):
        asset_id = session_data["tokens_asset_id"]
        try:
            data = external_storage.download(asset_id)
            tokens_dir = pathlib.Path(os.getenv("GMAIL_TOKENS_DIR", ".tokens"))
            tokens_dir.mkdir(exist_ok=True)
            tokens_path = tokens_dir / f"oauth_tokens_{session_id}.json"
            with open(tokens_path, "wb") as lf:
                lf.write(data["contents"] if isinstance(data["contents"], bytes) else data["contents"].encode())
            session_data["tokens_path"] = str(tokens_path)
            ctx.logger.info("📥 Downloaded tokens from Agentverse asset %s", asset_id)
        except Exception as dl_err:  # pragma: no cover
            ctx.logger.warning("Failed to download tokens from Agentverse: %s", dl_err)

    # 2) Persist helper to ContextVar so _run_gmail_tool can access
    token = CURRENT_SESSION_DATA.set(session_data)

    try:
        # Extract plain text blocks from incoming message
        inbound_texts: List[str] = [b.text.strip() for b in msg.content if isinstance(b, TextContent)]
        ctx.logger.info("📨 inbound_texts=%s", inbound_texts)

        # Shortcut – start session reset
        if any(isinstance(b, StartSessionContent) for b in msg.content):
            session_data.clear()
            session_data.update({"messages": []})
            inbound_texts = []  # don't treat start session as user input

        # If we received no user text and we're not waiting for the auth code
        # yet, do nothing (prevents duplicate auth links on pure StartSession).
        if not inbound_texts and not session_data.get("awaiting_auth_code"):
            sessions[session_id] = session_data
            ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
            return

        # --------------------------------------------------------------
        # 0.  Validate existing auth status (tokens might be deleted or
        #     the agent may have restarted and lost the Flow instance).
        # --------------------------------------------------------------

        # If we previously asked for an auth code but the agent restarted
        # (so gmail_auth lost its _flow) we must reset the flag, otherwise
        # every user message will be incorrectly treated as a code.
        if session_data.get("awaiting_auth_code") and getattr(gmail_auth, "_flow", None) is None:
            ctx.logger.warning(
                "Stale awaiting_auth_code detected but OAuth flow is missing – resetting state"
            )
            session_data.pop("awaiting_auth_code", None)
            session_data.pop("oauth_link_sent", None)  # also clear link flag so new flow can start

        if session_data.get("gmail_authenticated"):
            # Point gmail_auth at the session token file before the check
            if session_data.get("tokens_path"):
                gmail_auth.tokens_path = session_data["tokens_path"]  # type: ignore[attr-defined]
                gmail_auth._service = None  # reset cache

            try:
                status_raw = await _run_gmail_tool("check_auth_status", {})
                status = json.loads(status_raw)
                if not status.get("authenticated"):
                    session_data["gmail_authenticated"] = False
            except Exception as auth_err:
                ctx.logger.warning("Auth status check failed: %s", auth_err)
                session_data["gmail_authenticated"] = False

        # ------------------------------------------------------------------
        # 1. Handle authentication workflow (setup_oauth / complete_oauth)
        # ------------------------------------------------------------------

        ctx.logger.info("🔍 Auth status: authenticated=%s, awaiting_code=%s, inbound_texts=%s", 
                        session_data.get("gmail_authenticated"), 
                        session_data.get("awaiting_auth_code"), 
                        bool(inbound_texts))

        if not session_data.get("gmail_authenticated"):
            if session_data.get("oauth_link_sent") and not session_data.get("awaiting_auth_code"):
                # Shouldn't normally happen, but guard against duplicate sends
                return

            if session_data.get("awaiting_auth_code") and inbound_texts:
                possible = inbound_texts[0]
                auth_code = possible if possible.startswith("4/") else None
            # Auto-retrieval disabled – user must paste the code manually
            elif False:
                pass
            else:
                auth_code = None

            if auth_code:
                # Ensure a dedicated token file for this session
                tokens_dir = pathlib.Path(os.getenv("GMAIL_TOKENS_DIR", ".tokens"))
                tokens_dir.mkdir(exist_ok=True)
                tokens_path = tokens_dir / f"oauth_tokens_{session_id}.json"
                session_data["tokens_path"] = str(tokens_path)

                # Persist the raw auth code so callers can inspect it later if needed
                session_data["auth_code"] = auth_code

                # Point gmail_auth at this file *before* completing OAuth
                gmail_auth.tokens_path = str(tokens_path)  # type: ignore[attr-defined]
                gmail_auth._service = None  # reset cache

                try:
                    result = await _run_gmail_tool("complete_oauth", {"auth_code": auth_code})
                    parsed = json.loads(result)
                except RuntimeError as flow_err:
                    # _flow not initialised (e.g. after restart). Reset and fall back.
                    ctx.logger.warning("OAuth flow missing – restarting auth: %s", flow_err)
                    session_data.pop("awaiting_auth_code", None)
                    parsed = {"success": False, "error": "OAuth flow reset. Please authorise again."}

                if parsed.get("success"):
                    session_data["gmail_authenticated"] = True
                    session_data.pop("awaiting_auth_code", None)
                    session_data.pop("oauth_link_sent", None)

                    # Read the fresh token JSON and embed into session data, then delete the file
                    try:
                        with open(tokens_path, "r", encoding="utf-8") as tf:
                            token_obj = json.load(tf)
                        session_data["token_json"] = token_obj
                        # remove on-disk copy to keep everything in storage only
                        try:
                            os.remove(tokens_path)
                        except FileNotFoundError:
                            pass
                    except Exception as token_read_err:  # pragma: no cover
                        logger.warning("Failed to load token JSON for storage: %s", token_read_err)

                    # External token backup disabled – tokens remain local
                    reply = "✅ Authentication successful! You can now ask me to read, send or manage your Gmail messages."
                else:
                    session_data.pop("awaiting_auth_code", None)  # reset so a new auth flow can start
                    reply = f"❌ Authentication failed: {parsed.get('error', 'unknown error')}. Please try again."

                await ctx.send(sender, _create_chat_message(reply))
                # Save session state and exit early
                sessions[session_id] = session_data
                ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
                return

            # If we're still waiting for the code but didn't get a valid one, remind user instead of starting a new flow
            if session_data.get("awaiting_auth_code"):
                reminder = (
                    "⚠️ I\'m still waiting for the Google authorisation to complete. "
                    "Please click the Authorise Gmail link I sent above and grant access."
                )
                await ctx.send(sender, _create_chat_message(reminder))
                sessions[session_id] = session_data
                ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
                return

            # Not authenticated & not waiting – start OAuth
            ctx.logger.info("🚀 Starting OAuth setup...")
            try:
                oauth_json = await _run_gmail_tool("setup_oauth", {"session_id": session_id})
                ctx.logger.info("📋 OAuth response: %s", oauth_json)
                oauth_data = json.loads(oauth_json)
                if not oauth_data.get("success"):
                    err_msg = oauth_data.get("error", "Unknown error during OAuth setup")
                    await ctx.send(sender, _create_chat_message(f"❌ Authentication setup failed: {err_msg}"))
                    ctx.logger.error("❌ OAuth setup returned error: %s", err_msg)
                    return

                auth_url = oauth_data.get("auth_url", "")
                # Attach session_id as OAuth state so callback can map back
                state_val = session_id
                if "state=" not in auth_url:
                    sep = "&" if "?" in auth_url else "?"
                    auth_url = f"{auth_url}{sep}state={state_val}"
                session_data["state"] = state_val
                session_data["awaiting_auth_code"] = True
                session_data["oauth_link_sent"] = True
            except Exception as oauth_err:
                ctx.logger.error("❌ OAuth setup failed: %s", oauth_err)
                await ctx.send(sender, _create_chat_message(f"❌ Authentication setup failed: {oauth_err}"))
                return
            reply = (
                "Click the **Authorize Gmail** link below.\n"
                "A browser tab will open – sign in & grant access.\n"
                "Once authorised, please send me your query.\n\n"
                f"[Authorize Gmail]({auth_url})"
            )
            ctx.logger.info("Auth link sent: %s", auth_url)
            # Spawn background watcher so user doesn't need to paste code
            # Background watcher disabled – user must paste the code manually
            await ctx.send(sender, _create_chat_message(reply))
            sessions[session_id] = session_data
            ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))
            ctx.logger.info(">> session=%s to=%s content=%s", ctx.session, sender, reply)
            return

        # 3) Build conversation context for OpenAI call
        def _to_openai(m: Dict[str, str]) -> Dict[str, str]:
            role = "user" if m.get("source") == "human" else "assistant"
            return {"role": role, "content": m.get("content", "")}

        messages: List[Dict[str, str]] = [_to_openai(m) for m in session_data.get("messages", [])]
        messages.insert(0, {"role": "system", "content": _SYSTEM_PROMPT})

        # Append current user input
        if inbound_texts:
            user_content = "\n".join(inbound_texts)
            messages.append({"role": "user", "content": user_content})
            session_data.setdefault("messages", []).append({"source": "human", "content": user_content})

        # Trim history
        if len(session_data["messages"]) > MAX_HISTORY * 2:
            session_data["messages"] = session_data["messages"][-MAX_HISTORY * 2 :]

        # 4) Call OpenAI Responses API → possibly triggers tool calls
        assistant_reply = await _call_openai_responses(messages)

        # ---------------- Fallback: model leaked raw tool_calls JSON -------
        try:
            import re as _re, ast as _ast

            # If assistant dumped a tool_calls block, parse & execute it, then re-call OpenAI
            _match = _re.search(r"tool_calls\s*:?\s*(\{.*\})", assistant_reply, flags=_re.S)
            if _match:
                blob = _match.group(1)
                try:
                    container = json.loads(blob)
                except Exception:
                    try:
                        container = _ast.literal_eval(blob)
                    except Exception:
                        container = None

                if isinstance(container, dict):
                    calls = []
                    if "calls" in container and isinstance(container["calls"], list):
                        calls = container["calls"]
                    elif container.get("tool") == "parallel_tool_calls":
                        calls = container.get("params", [])
                    elif "tool" in container:
                        calls = [container]

                    if calls:
                        outs = []
                        for c in calls:
                            name = c.get("tool") or c.get("method") or c.get("function", {}).get("name", "")
                            name = name.split(".")[-1]
                            params = c.get("params") or c.get("parameters") or c.get("input") or {}
                            out = await _run_gmail_tool(name, params)
                            outs.append({"tool_call_id": f"manual_{name}", "output": out})

                        # get proper assistant reply with outputs
                        assistant_reply = await _call_openai_responses([
                            {"role": "assistant", "content": "", "tool_outputs": outs},
                        ])

            # Raw list variant starting with parallel_tool_calls [ ... ]
            if assistant_reply.strip().startswith("parallel_tool_calls"):
                _m = _re.search(r"parallel_tool_calls\s*:?\s*(\[.*\])", assistant_reply, flags=_re.S)
                if _m:
                    list_blob = _m.group(1)
                    try:
                        call_list = json.loads(list_blob)
                    except Exception:
                        try:
                            call_list = _ast.literal_eval(list_blob)
                        except Exception:
                            call_list = None

                    if isinstance(call_list, list):
                        outs = []
                        for c in call_list:
                            name = c.get("name") or c.get("tool")
                            name = name.split(".")[-1]
                            params = c.get("params") or {}
                            out = await _run_gmail_tool(name, params)
                            outs.append({"tool_call_id": f"manual_{name}", "output": out})

                        assistant_reply = await _call_openai_responses([
                            {"role": "assistant", "content": "", "tool_outputs": outs},
                        ])

        except Exception as _fallback_err:
            logger.debug("Fallback parsing skipped: %s", _fallback_err)

        session_data.setdefault("messages", []).append({"source": "assistant", "content": assistant_reply})

        await ctx.send(sender, _create_chat_message(assistant_reply))

        # 5) Persist session back to storage
        sessions[session_id] = session_data
        ctx.storage.set(SESSIONS_KEY, json.dumps(sessions))

    finally:
        CURRENT_SESSION_DATA.reset(token)

# ---------------------------------------------------------------------------
# ACK handler – currently noop
# ---------------------------------------------------------------------------

@chat_proto.on_message(ChatAcknowledgement)
async def _handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):  # noqa: D401
    logger.debug("ACK from %s for message %s", sender, msg.acknowledged_msg_id) 