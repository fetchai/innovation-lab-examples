# Form-Filler Agent

![tag:user-facing](https://img.shields.io/badge/user--facing-3D8BD3)
![tag:greenhouse](https://img.shields.io/badge/greenhouse-3D8BD3)
![tag:form-filler](https://img.shields.io/badge/form--filler-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

User-facing entry point for the job-application workflow. The user pastes
a Greenhouse job link in chat and **watches the form fill in real time**,
with every value visible and editable. The user explicitly decides when
to submit (`submit` runs a safe dry-run; `submit live` actually posts).

## Why this agent

The other three agents in this folder are helpers — they expose typed
agent-to-agent protocols and REST endpoints, but they aren't great UX
for humans. This agent is the chat front-door that wires the three
helpers together while keeping the user in the loop.

```
   user (ASI:One chat)
        │
        ▼
┌─────────────────────┐
│  form-filler-agent  │ ──┐
└─────────────────────┘   │ send_and_receive
       ▲                  ▼
       │            ┌──────────────┐
       │            │  extractor   │
       │            └──────────────┘
       │            ┌──────────────┐
       │            │   profile    │  (Get / Map / Upsert)
       │            └──────────────┘
       │            ┌──────────────┐
       │            │  submitter   │  (dry-run OR live)
       │            └──────────────┘
       │
       └──── streamed ChatMessage progress updates back to user
```

## Setup

```bash
cd job-application-agent/form-filler-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Boot the three helper agents first and copy each one's startup address
(`Agent starting: ... at agent1q...`) into `form-filler-agent/.env`:

```
EXTRACTOR_AGENT_ADDRESS=agent1q...
PROFILE_AGENT_ADDRESS=agent1q...
SUBMITTER_AGENT_ADDRESS=agent1q...
```

You'll also want a profile saved already (the user-key default is `me`)
via the Profile Agent's REST or chat surface — otherwise this agent has
nothing to fill the form with.

Run it:

```bash
python agent.py
```

The agent registers itself with Agentverse on startup (if
`AGENTVERSE_API_KEY` is set in the repo-root `.env`) and is then
discoverable in ASI:One.

## Chat commands

Paste a Greenhouse URL anywhere in a message to start a session. After
the form preview appears, use:

| Command | What it does |
|---|---|
| `show <name>` | full value of one field |
| `show all` / `form` | re-print the form preview |
| `answer <name> <value>` | fill a missing field |
| `edit <name> <value>` | change a filled value |
| `unfill <name>` | clear a field |
| `next` | show the next missing field's prompt |
| `submit` | dry-run (validate, preview the payload, nothing sent) |
| `submit live` | actually post to Greenhouse |
| `show payload` | dump the last dry-run payload |
| `cancel` | discard the active session |
| `help` | print this list |

Each `answer` / `edit` is also saved back to your profile (structured
field if recognised, otherwise as a canned-answer) so the next
application starts more pre-filled.

## Internals

- `agent.py`     — chat protocol handler + state-machine driver + Agentverse reg
- `session.py`   — `Session` dataclass + state enum + `ctx.storage` helpers
- `clients.py`   — wire-model copies + `ctx.send_and_receive` wrappers for the 3 helpers
- `rendering.py` — chat formatters (job summary, form panel, field detail, submission result)
- `commands.py`  — free-text → `Command` parser

The agent never executes business logic itself — it only orchestrates
the three helpers and renders their results. That keeps each helper
independently testable and keeps the chat surface thin.
