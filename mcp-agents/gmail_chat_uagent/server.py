# Replacing previous lightweight wrapper with the full Gmail FastMCP server implementation
# (adapted from snrauto/python-gmail-mcp-uagents/server.py).  The only change
# is the `main()` which now calls `mcp.run("sse", ...)` so no external Uvicorn
# dependency is required.

#!/usr/bin/env python3
"""
FastMCP Gmail Server (self-contained copy)

Exposes OAuth tools plus send/list/read/delete email utilities. This file lives
inside `gmail_chat_uagent/` so the entire Gmail integration is now completely
independent from the `snrauto` project subtree.
"""

import os
import json
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any

from fastmcp import FastMCP

# Google auth imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

# Optional environment loading
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

VERBOSE_GMAIL_LOGS = os.getenv("VERBOSE_GMAIL_LOGS", "true").lower() in ("1", "true", "yes")
logger.setLevel(logging.DEBUG if VERBOSE_GMAIL_LOGS else logging.INFO)

LOG_FILE = os.getenv("GMAIL_LOG", "gmail_debug.log")
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    _fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    _fh.setLevel(logging.DEBUG)
    logger.addHandler(_fh)

if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _ch.setLevel(logging.INFO)
    logger.addHandler(_ch)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(
    CURRENT_DIR,
    "client_secret_347333255507-itkbqibl0j8jg733dcj9u5o1h7dprpm0.apps.googleusercontent.com.json",
)
TOKENS_PATH = os.path.join(CURRENT_DIR, "oauth_tokens.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

logger.info(f"🔧 Gmail server initializing with credentials path: {CREDENTIALS_PATH}")
logger.info(f"🔧 Tokens will be stored at: {TOKENS_PATH}")
logger.info(f"🔧 Requested scopes: {SCOPES}")

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("Gmail MCP")
logger.info("🚀 Gmail MCP server instance created")

# ---------------------------------------------------------------------------
# Gmail OAuth helper class
# ---------------------------------------------------------------------------


class GmailAuth:
    """Handles OAuth for Gmail and provides an authenticated service."""

    def __init__(self, credentials_path: str = CREDENTIALS_PATH, tokens_path: str = TOKENS_PATH):
        self.credentials_path = credentials_path
        self.tokens_path = tokens_path
        self._service = None  # Cached Gmail service
        self._flow = None  # OAuth flow instance
        logger.info(f"🔑 GmailAuth initialized with credentials: {credentials_path}")

    # --------------------------- OAuth Flow ---------------------------
    def get_oauth_url(self, session_id: str = None) -> str:
        logger.info("🔗 Starting OAuth flow - generating authorization URL")
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Google OAuth client secrets not found at {self.credentials_path}.")
        self._flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri="http://localhost:8080/callback",
        )
        
        # Use session_id as state if provided, otherwise let Google generate one
        if session_id:
            auth_url, _ = self._flow.authorization_url(prompt="consent", state=session_id)
        else:
            auth_url, _ = self._flow.authorization_url(prompt="consent")
        
        logger.info(f"✅ OAuth URL generated successfully: {auth_url[:100]}…")
        return auth_url

    def exchange_code_for_token(self, auth_code: str) -> bool:
        logger.info(f"🔄 Exchanging authorization code for tokens: {auth_code[:20]}…")
        if self._flow is None:
            raise RuntimeError("OAuth flow not initialised. Call get_oauth_url first.")
        self._flow.fetch_token(code=auth_code)
        creds = self._flow.credentials
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }
        with open(self.tokens_path, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"💾 Tokens saved to {self.tokens_path}")
        return True

    # --------------------------- Gmail Service ---------------------------
    def get_service(self):  # noqa: D401
        if self._service:
            return self._service
        if not os.path.exists(self.tokens_path):
            raise RuntimeError("Not authenticated – run setup_oauth/complete_oauth first.")
        with open(self.tokens_path, "r") as f:
            token_info = json.load(f)
        creds = Credentials(
            token_info["token"],
            refresh_token=token_info.get("refresh_token"),
            token_uri=token_info["token_uri"],
            client_id=token_info["client_id"],
            client_secret=token_info["client_secret"],
            scopes=token_info["scopes"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            token_info["token"] = creds.token
            with open(self.tokens_path, "w") as f:
                json.dump(token_info, f, indent=2)
        self._service = build("gmail", "v1", credentials=creds)
        return self._service


gmail_auth = GmailAuth()

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _create_message(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    is_html: bool = False,
):
    msg_root: MIMEMultipart | MIMEText
    if is_html:
        msg_root = MIMEMultipart("alternative")
        msg_root.attach(MIMEText(body, "html"))
    else:
        msg_root = MIMEText(body)
    msg_root["To"] = to
    msg_root["Subject"] = subject
    if cc:
        msg_root["Cc"] = cc
    if bcc:
        msg_root["Bcc"] = bcc
    raw = base64.urlsafe_b64encode(msg_root.as_bytes()).decode()
    return {"raw": raw}


# ---------------------------------------------------------------------------
# OAuth tools
# ---------------------------------------------------------------------------


@mcp.tool()
def setup_oauth(session_id: str = None) -> str:
    try:
        url = gmail_auth.get_oauth_url(session_id)
        return json.dumps({"success": True, "auth_url": url}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def complete_oauth(auth_code: str) -> str:
    try:
        gmail_auth.exchange_code_for_token(auth_code)
        return json.dumps({"success": True}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def check_auth_status() -> str:
    token_file = gmail_auth.tokens_path
    if token_file and os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                scopes = json.load(f).get("scopes", [])
            gmail_auth.get_service()  # refresh check
            return json.dumps({"success": True, "authenticated": True, "scopes": scopes}, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "authenticated": False, "error": str(e)})
    return json.dumps({"success": True, "authenticated": False}, indent=2)


@mcp.tool()
def reset_oauth_tokens() -> str:
    if os.path.exists(TOKENS_PATH):
        os.remove(TOKENS_PATH)
        gmail_auth._service = None  # type: ignore[attr-defined]
        return json.dumps({"success": True}, indent=2)
    return json.dumps({"success": False, "error": "No token file"}, indent=2)

# ---------------------------------------------------------------------------
# Gmail action tools
# ---------------------------------------------------------------------------


@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "", is_html: bool = False) -> str:
    try:
        service = gmail_auth.get_service()
        msg = _create_message(to, subject, body, cc or None, bcc or None, is_html)
        result = service.users().messages().send(userId="me", body=msg).execute()
        return json.dumps({"success": True, "message_id": result.get("id")}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def list_emails(query: str = "", label_ids: str = "INBOX", max_results: int = 10) -> str:
    try:
        service = gmail_auth.get_service()
        labels = [lbl.strip() for lbl in label_ids.split(",") if lbl.strip()]
        resp = service.users().messages().list(userId="me", q=query, labelIds=labels, maxResults=max_results).execute()
        msgs = resp.get("messages", [])
        output: List[Dict[str, Any]] = []
        for msg in msgs:
            detail = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"]).execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            output.append({
                "id": detail.get("id"),
                "snippet": detail.get("snippet"),
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
            })
        return json.dumps({"success": True, "emails": output}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def read_email(message_id: str) -> str:
    try:
        service = gmail_auth.get_service()
        detail = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        return json.dumps({
            "success": True,
            "id": detail.get("id"),
            "snippet": detail.get("snippet"),
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "payload": detail.get("payload"),
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def delete_email(message_id: str) -> str:
    try:
        service = gmail_auth.get_service()
        try:
            service.users().messages().trash(userId="me", id=message_id).execute()
        except Exception:
            pass  # already trashed
        return json.dumps({"success": True, "trashed_id": message_id}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def delete_last_sent_email(to: str, query: str = "", label_ids: str = "SENT") -> str:
    try:
        service = gmail_auth.get_service()
        full_query = f"to:{to} {query}".strip()
        resp = service.users().messages().list(userId="me", q=full_query, labelIds=[lbl.strip() for lbl in label_ids.split(",") if lbl.strip()], maxResults=1).execute()
        msgs = resp.get("messages", [])
        if not msgs:
            return json.dumps({"success": False, "error": "No matching email found"}, indent=2)
        msg_id = msgs[0]["id"]
        try:
            service.users().messages().trash(userId="me", id=msg_id).execute()
        except Exception:
            pass
        return json.dumps({"success": True, "trashed_id": msg_id}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def get_profile() -> str:
    try:
        service = gmail_auth.get_service()
        profile = service.users().getProfile(userId="me").execute()
        return json.dumps({"success": True, "profile": profile}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Entrypoint for standalone run
# ---------------------------------------------------------------------------


def main():  # pragma: no cover
    """Run as standalone FastMCP server (SSE transport)."""
    port = int(os.getenv("GMAIL_MCP_PORT", "8081"))
    mcp.run("sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main() 