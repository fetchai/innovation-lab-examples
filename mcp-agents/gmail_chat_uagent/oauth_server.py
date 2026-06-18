#!/usr/bin/env python3
"""
OAuth Callback Server for Gmail Chat Agent

Runs on http://localhost:8080 and displays the `code` parameter returned by
Google after the user grants consent.  This helper is optional – the agent
still works if you manually copy the code from the browser URL – but it makes
the flow smoother when running inside desktop chat clients that open the OAuth
page in an external browser.
"""

import http.server
import socketserver
import urllib.parse
import os
import json
import glob
from uagents_core.storage import ExternalStorage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
STORAGE_URL = os.getenv("AGENTVERSE_URL", "https://agentverse.ai") + "/v1/storage"

print(
    f"🔑 API Key loaded: {AGENTVERSE_API_KEY[:20] if AGENTVERSE_API_KEY else 'None'}..."
)
print(f"🌐 Storage URL: {STORAGE_URL}")

_storage: ExternalStorage | None = None
if AGENTVERSE_API_KEY:
    try:
        _storage = ExternalStorage(
            api_token=AGENTVERSE_API_KEY, storage_url=STORAGE_URL
        )
        print(f"🔐 ExternalStorage initialised successfully")  # noqa: F541
    except Exception as err:
        print(f"⚠️  ExternalStorage init failed: {err}")
        _storage = None
else:
    print("❌ No AGENTVERSE_API_KEY found - external storage disabled")


def save_oauth_code_to_agent_storage(session_id: str, auth_code: str):
    """Save OAuth code to agent storage JSON file."""
    try:
        # Find the agent storage file (pattern: agent*_data.json)
        storage_files = glob.glob("agent*_data.json")
        if not storage_files:
            print("⚠️  No agent storage file found")
            return False

        storage_file = storage_files[0]  # Use the first one found

        # Read current storage
        with open(storage_file, "r") as f:
            storage_data = json.load(f)

        # Parse gmail_chat_sessions
        sessions_str = storage_data.get("gmail_chat_sessions", "{}")
        sessions = (
            json.loads(sessions_str) if isinstance(sessions_str, str) else sessions_str
        )

        # Update the session with the OAuth code
        if session_id in sessions:
            sessions[session_id]["oauth_code"] = auth_code
            sessions[session_id]["code_received"] = True

            # Update storage
            storage_data["gmail_chat_sessions"] = json.dumps(sessions)

            # Write back to file
            with open(storage_file, "w") as f:
                json.dump(storage_data, f, indent=4)

            print(f"💾 OAuth code saved to agent storage for session {session_id}")
            return True
        else:
            print(f"⚠️  Session {session_id} not found in agent storage")
            return False

    except Exception as e:
        print(f"⚠️  Failed to save to agent storage: {e}")
        return False


SUCCESS_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Gmail Authorised</title>
    <script>
      // Extract OAuth code and session state from URL params
      const params = new URLSearchParams(window.location.search);
      const code = params.get('code');
      const state = params.get('state');

      if (code && state) {
        // Silently notify the chat agent so it can finish the flow automatically
        fetch('http://localhost:8088/oauth/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: state, auth_code: code })
        }).finally(() => {
          setTimeout(() => window.close(), 1200);
        });
      } else {
        // Nothing to send – just close shortly
        setTimeout(() => window.close(), 1200);
      }
    </script>
  </head>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; margin-top: 60px; color: #333;">
    <h2>✅ Authorisation successful</h2>
    <p>The window will close shortly.</p>
  </body>
</html>"""

ERROR_PAGE = """
<!DOCTYPE html>
<html><body><h2 style="color:#dc3545;font-family:sans-serif;text-align:center;">❌ OAuth Error – No code received</h2></body></html>
"""


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
            page = SUCCESS_PAGE_TEMPLATE.replace("{AUTH_CODE}", code)
            self.wfile.write(page.encode("utf-8"))
            print(
                f"\n🎉 Authorization code received for session {state}: {code[:10]}…\n"
            )

            # Persist to Agentverse so chat agent can pick it up
            stored_externally = False
            if _storage and state:
                try:
                    _storage.create_asset(
                        name=state, content=code.encode(), mime_type="text/plain"
                    )
                    print("💾 Code uploaded to Agentverse asset", state)
                    stored_externally = True
                except Exception as up_err:
                    print("⚠️  Failed to upload code to Agentverse:", up_err)

            # Fallback to agent storage
            if not stored_externally and state:
                if not save_oauth_code_to_agent_storage(state, code):
                    # Final fallback to local file
                    try:
                        with open(f"oauth_code_{state}.txt", "w") as f:
                            f.write(code)
                        print(
                            f"💾 Code saved locally to oauth_code_{state}.txt as final fallback"
                        )
                    except Exception as local_err:
                        print("⚠️  Failed to save code locally:", local_err)

            # --- Notify chat agent via REST so it can complete OAuth automatically
            try:
                import requests, json as _json  # noqa: E401, F401

                payload = {"session_id": state, "auth_code": code}
                resp = requests.post(
                    "http://localhost:8088/oauth/callback", json=payload, timeout=3
                )
                print("➡️  Posted code to chat agent – status", resp.status_code)
            except Exception as notify_err:
                print("⚠️  Could not notify chat agent:", notify_err)
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(ERROR_PAGE.encode("utf-8"))

    def log_message(self, fmt, *args):  # noqa: D401, N802
        # Suppress default logging noise
        pass


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
