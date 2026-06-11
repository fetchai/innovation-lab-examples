# Orchestrator Agent

![tag:user-facing](https://img.shields.io/badge/user--facing-3D8BD3)
![tag:orchestrator](https://img.shields.io/badge/orchestrator-3D8BD3)
![tag:profile](https://img.shields.io/badge/profile-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

The single user-facing chat entry for the entire job-application workflow.
Sits in front of the helper agents and gives the user one conversational
surface for two distinct jobs:

1. **Managing their job-search profile** — upload / update a resume
   (kept in memory with versioning), edit structured profile fields
   conversationally, view what's currently stored.
2. **Applying for jobs** — paste a Greenhouse URL and the orchestrator
   hands off into `form-filler-agent` to do the actual form-fill.

Everything the user answers during an application is saved back into
their profile (delegated to `form-filler-agent` which already does this),
so the next application starts with more pre-filled fields.

```
                user (ASI:One)
                      │
                      ▼
            ┌─────────────────────┐
            │ orchestrator-agent  │
            └──────────┬──────────┘
                       │ ctx.send_and_receive
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌──────────────┐              ┌────────────────────┐
│ profile-     │              │ form-filler-agent  │
│ agent        │              │ (+ extractor +     │
│              │              │   submitter)       │
└──────────────┘              └────────────────────┘
```

## Setup

```bash
cd job-application-agent/orchestrator-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Boot the other agents (profile, extractor, submitter, form-filler) and
paste their addresses into `.env`. Only `PROFILE_AGENT_ADDRESS` and
`FORM_FILLER_AGENT_ADDRESS` are needed here — the orchestrator never
talks to extractor or submitter directly; those are reached through
form-filler.

Run:

```bash
python agent.py
```

The agent registers itself with Agentverse on startup (if
`AGENTVERSE_API_KEY` is set) and is then discoverable in ASI:One.

## Chat capabilities (early)

| Say | What happens |
|---|---|
| `hi` / `hello` | A warm onboarding reply listing what you can do. |
| `help` | The full capability list. |
| `show my profile` / `whoami` | Print a summary of what's stored. |

More to land in subsequent commits: `edit profile`, resume upload via
attachment, resume version switching, `apply <greenhouse_url>`.

## Internals

- `agent.py`         — chat handler + intent router + Agentverse reg
- `intents.py`       — ASI:One classifier + regex short-circuits
- `clients.py`       — wire-model duplicates + `ctx.send_and_receive` wrappers
- `profile_proxy.py` — high-level helpers around the profile-agent
- `rendering.py`     — chat-side formatters
- `session.py`       — `OrchestratorSession` + `ctx.storage` helpers

This agent intentionally holds **no business logic**: it parses intent,
calls the right helper, and renders the result.
