#!/usr/bin/env python3
"""
OAuth Callback Server for Calendar Chat Agent

Runs on http://localhost:8080 and displays the `code` parameter returned by
Google after the user grants consent. This helper is optional – the chat agent
still works if you manually copy the code from the browser URL – but it makes
OAuth smoother when running in desktop chat clients that open the page in an
external browser.
"""

import http.server
import socketserver
import urllib.parse
import os
import json
import glob
from dotenv import load_dotenv

# Optional Agentverse asset storage for handing off the OAuth code to remote agents
from uagents_core.storage import ExternalStorage  # type: ignore

# ---------------------------------------------------------------------------
# Environment & External storage setup
# ---------------------------------------------------------------------------

load_dotenv()

AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
STORAGE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"

print(f"🔑 API Key loaded: {AGENTVERSE_API_KEY[:20] + '…' if AGENTVERSE_API_KEY else 'None'}")
print(f"🌐 Storage URL: {STORAGE_URL}")

_storage: ExternalStorage | None = None
if AGENTVERSE_API_KEY:
    try:
        _storage = ExternalStorage(api_token=AGENTVERSE_API_KEY, storage_url=STORAGE_URL)
        print("🔐 ExternalStorage initialised successfully")
    except Exception as err:
        print(f"⚠️  ExternalStorage init failed: {err}")
        _storage = None
else:
    print("❌ No AGENTVERSE_API_KEY found – external storage disabled")

# ---------------------------------------------------------------------------
# Helper for persisting the OAuth code in the agent's local storage JSON file
# ---------------------------------------------------------------------------

def save_oauth_code_to_agent_storage(session_id: str, auth_code: str) -> bool:
    """Save OAuth code into the agent*_data.json under `calendar_chat_sessions`."""
    try:
        # Locate the first agent storage file (pattern produced by uAgents framework)
        storage_files = glob.glob("agent*_data.json")
        if not storage_files:
            print("⚠️  No agent storage file found")
            return False

        storage_file = storage_files[0]
        with open(storage_file, "r") as f:
            storage_data = json.load(f)

        # calendar_chat_sessions is a JSON-serialised string in the storage JSON
        sessions_str = storage_data.get("calendar_chat_sessions", "{}")
        sessions = json.loads(sessions_str) if isinstance(sessions_str, str) else sessions_str

        if session_id in sessions:
            sessions[session_id]["oauth_code"] = auth_code
            sessions[session_id]["code_received"] = True
            storage_data["calendar_chat_sessions"] = json.dumps(sessions)

            with open(storage_file, "w") as f:
                json.dump(storage_data, f, indent=4)

            print(f"💾 OAuth code saved to agent storage for session {session_id}")
            return True
        else:
            print(f"⚠️  Session {session_id} not found in agent storage")
            return False
    except Exception as e:
        print(f"⚠️  Failed to save OAuth code to agent storage: {e}")
        return False

# ---------------------------------------------------------------------------
# HTML pages returned to the browser
# ---------------------------------------------------------------------------

SUCCESS_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <title>Calendar Authorised</title>
    <script>
      const p = new URLSearchParams(location.search);
      const code = p.get('code');
      const sid  = p.get('state');
      if (code && sid) {
        fetch('http://localhost:8089/oauth/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid, auth_code: code })
        }).finally(() => setTimeout(() => window.close(), 1200));
      } else {
        setTimeout(() => window.close(), 1200);
      }
    </script>
  </head>
  <body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;text-align:center;margin-top:60px;color:#333\">
    <h2>✅ Authorisation successful</h2>
    <p>You can now close this tab.</p>
  </body>
</html>"""

ERROR_PAGE = """<!DOCTYPE html><body><h2 style='color:#dc3545;font-family:sans-serif;text-align:center;'>❌ OAuth Error – No code received</h2></body></html>"""

# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            code = params["code"][0]
            state = params.get("state", [""])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(SUCCESS_PAGE_TEMPLATE.encode("utf-8"))
            print(f"\n🎉 Authorization code received for session {state}: {code[:10]}…\n")

            # 1️⃣ Upload to Agentverse asset storage
            stored_externally = False
            if _storage and state:
                try:
                    _storage.create_asset(name=state, content=code.encode(), mime_type="text/plain")
                    print("💾 Code uploaded to Agentverse asset", state)
                    stored_externally = True
                except Exception as up_err:
                    print("⚠️  Failed to upload code to Agentverse:", up_err)

            # 2️⃣ Fallback: store inside the agent's local storage file
            if not stored_externally and state:
                if not save_oauth_code_to_agent_storage(state, code):
                    # 3️⃣ Final fallback: dump to a local txt file
                    try:
                        with open(f"calendar_oauth_code_{state}.txt", "w") as f:
                            f.write(code)
                        print(f"💾 Code saved locally to calendar_oauth_code_{state}.txt as final fallback")
                    except Exception as local_err:
                        print("⚠️  Failed to save code locally:", local_err)

            # Notify the calendar_chat_agent REST endpoint so it can finish the flow automatically
            try:
                import requests as _req
                payload = {"session_id": state, "auth_code": code}
                resp = _req.post("http://localhost:8089/oauth/callback", json=payload, timeout=3)
                print("➡️  Posted code to chat agent – status", resp.status_code)
            except Exception as notify_err:
                print("⚠️  Could not notify chat agent:", notify_err)
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(ERROR_PAGE.encode("utf-8"))

    def log_message(self, fmt, *args):  # noqa: N802
        # Suppress the default noisy HTTP request logs from http.server
        pass

# ---------------------------------------------------------------------------
# Server entrypoint
# ---------------------------------------------------------------------------

def start_oauth_server():
    port = 8080
    with socketserver.TCPServer(("", port), OAuthCallbackHandler) as httpd:
        print(f"🌐 OAuth callback server listening on http://localhost:{port}")
        print("🛑 Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 OAuth server stopped")

if __name__ == "__main__":
    start_oauth_server() 