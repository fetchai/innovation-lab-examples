# Google Calendar Chat Agent (uAgents + FastMCP)

Natural-language interface to Google Calendar.

* **Fast-MCP** – exposes Calendar tools (`server.py`)
* **uAgents** – chat protocol & OAuth callback (`calendar_chat_agent.py`, `calendar_chat_proto.py`)
* **OAuth helper** – minimal HTTP server to capture the Google auth code (`oauth_server.py`)

---

## Features

* Per-session OAuth (tokens stored only in `.tokens/`, never committed).
* List, create, update and delete events.
* Check free/busy blocks for yourself or other calendars.
* Fully streaming OpenAI tool-calling – replies include Markdown links to each event.

---

## Quick-start (local)

### 1. Clone & prepare env

```bash
$ git clone git@github.com:<you>/calendar-chat-agent.git
$ cd calendar-chat-agent

# copy env template & edit values
$ cp env.sample .env
$ nano .env   # fill in OPENAI_API_KEY + CAL_CREDENTIALS_FILE path
```

### 2. Install dependencies (Python ≥ 3.10)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the three components

```bash
# ➊ HTTPS tunnel for the FastMCP SSE endpoint (OpenAI needs https)
ngrok http 8081
# copy the https:// URL with /sse/ and set CAL_MCP_URL in .env

# ➊ FastMCP Calendar tools (port 8081)
python calendar_chat_uagent/server.py

# ➋ OAuth callback helper (port 8080)
python calendar_chat_uagent/oauth_server.py

# ➌ Chat agent (port 8089)
python calendar_chat_uagent/calendar_chat_agent.py
```

On first message the agent replies with **Authorize Calendar**.  Click, grant access, and ask things like “List my meetings tomorrow”.

---

## Google OAuth client secret

Create a **Desktop app** OAuth 2.0 client in Google Cloud and download the JSON.  Store it as the file pointed to by `CAL_CREDENTIALS_FILE` (default `calendar_client_secret.json`) inside `calendar_chat_uagent/`.  The file is ignored by Git (`client_secret*.json`).

> **Tip:** Google saves the file with a long name such as
> `client_secret_XXXXXXXXXXXX-abcdefg.apps.googleusercontent.com.json`.
> You can leave the name or rename it to `calendar_client_secret.json` and set
> the env var accordingly:
>
> ```bash
> export CAL_CREDENTIALS_FILE="calendar_chat_uagent/calendar_client_secret.json"
> ```
> The server reads this variable at startup.

---

## Environment variables

See `env.sample` for the full list.  Key ones:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key. |
| `CAL_CHAT_AGENT_PORT` | uAgents HTTP port (default 8089). |
| `CAL_MCP_URL` | Public **https** URL of the SSE server – include `/sse/`. |
| `CAL_CREDENTIALS_FILE` | Path to your Google OAuth client JSON. |
| `CAL_TOKENS_DIR` | Directory where temp token JSON files are stored. |

---

## FAQ

**Where are my tokens?**  In `.tokens/oauth_tokens_<session>.json`.  Delete to force re-auth.

**Why does `get_free_busy` return nothing?**  The target calendar must share at least *free/busy* with you or be in the same Workspace with visibility enabled.

**How do I deploy?**  Build a Docker image copying the directory, install `requirements.txt`, set env vars, expose ports 8081 (SSE) & 8089 (uAgents). 