# Gmail Chat Agent (uAgents + FastMCP)

Interact with Gmail in natural language.  The agent uses:

* **Fast-MCP** – provides OAuth and email tools (`server.py`)
* **uAgents** – handles chat protocol & REST callback (`gmail_chat_agent.py` & `gmail_chat_proto.py`)
* **OAuth helper** – lightweight HTTP server that captures the Google authorisation code (`oauth_server.py`)

## Features

* Per-session OAuth – tokens stored only in `.tokens/`, never committed.
* Read, send, list and delete emails through OpenAI tool-calling.
* Minimal dependencies – works with plain Python (or Docker).

---

## Quick-start (local)

### 1. Clone & prepare env

```bash
# clone your fork
$ git clone git@github.com:<you>/gmail-chat-agent.git
$ cd gmail-chat-agent

# copy env template & edit values
$ cp env.sample .env
$ nano .env   # fill in OPENAI_API_KEY at minimum
```

### 2. Install dependencies (Python ≥ 3.10)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the three components

```bash
# ➊ Start an HTTPS tunnel for the FastMCP SSE endpoint
# (OpenAI Responses requires an https URL)
# Example with ngrok:
ngrok http 8081

# Copy the https:// URL it prints (e.g. https://abcd-1234.ngrok-free.app)
# and set it as GMAIL_MCP_URL in your .env, including the /sse/ suffix.

# ➊ FastMCP Gmail tools (SSE server on port 8081)
python gmail_chat_uagent/server.py

# ➋ OAuth callback helper (HTTP on port 8080)
python gmail_chat_uagent/oauth_server.py

# ➌ Chat agent (uAgents on port 8088)
python gmail_chat_uagent/gmail_chat_agent.py
```

Send messages to the agent (e.g. via uAgents desktop client, webhook or test script).  On first use the agent will reply with an **Authorize Gmail** link.  Click, grant access, and you’re ready to ask e-mail questions like “List unread from Amazon”.

---

## Google OAuth client secret

The Gmail tools need a **desktop** OAuth 2.0 client secret JSON downloaded from your Google Cloud Console:

> **Filename tip** – when Google downloads the file it is often called
> `client_secret_XXXXXXXXXXXX-abcdefg.apps.googleusercontent.com.json`.  You
> can keep this name or rename it to something shorter (e.g.
> `gmail_client_secret.json`).  The important part is that the file lives
> **inside** `gmail_chat_uagent/` and is **not** committed because
> `.gitignore` excludes `client_secret*.json`.

1. Open **Google Cloud → APIs & Services → Credentials**.
2. Create (or download) an *OAuth Client ID* of type **Desktop app**.
3. Place the JSON file inside `gmail_chat_uagent/`.  If you renamed it you must
   also update the constant `CREDENTIALS_PATH` in `gmail_chat_uagent/server.py`
   **or** export an environment variable:

   ```bash
   export GMAIL_CREDENTIALS_FILE="gmail_chat_uagent/gmail_client_secret.json"
   ```
   (The server falls back to this variable if set.)

The file is git-ignored by the pattern `client_secret*.json`; never commit it to Git.

---

## Environment variables

See `env.sample` for the full list.  The essentials:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | API key for OpenAI Chat/Responses API. |
| `GMAIL_CHAT_AGENT_PORT` | uAgents HTTP port (default 8088). |
| `GMAIL_MCP_PORT` | FastMCP SSE port (default 8081). |
| `GMAIL_MCP_URL` | Public **https** URL of the SSE server – required because OpenAI tool-calls only connect over TLS. Use ngrok or CloudRun and include `/sse/` (e.g. `https://abcd.ngrok-free.app/sse/`). |
| `GMAIL_TOKENS_DIR` | Directory for temporary token JSON files (default `.tokens`). |

---

## FAQ

**Where do tokens live?**  Each chat session gets its own `oauth_tokens_<session>.json` inside `.tokens/`; once loaded they’re cached in-memory.

**How do I revoke / reset auth?**  Delete the `oauth_tokens_<session>.json` file or call the `reset_oauth_tokens` tool.

**Troubleshooting 401 errors**  Check that your Google Cloud OAuth creds in `client_secret*.json` contain Gmail scopes and that the redirect URI is `http://localhost:8080/callback`.

**Do I need to expose the OAuth callback (`oauth_server.py`)?**  No – it runs on `http://localhost:8080` only for the browser tab opened during consent.  The page itself posts the code back to the local chat agent, so an external HTTPS tunnel is **not** required for `oauth_server.py`. 