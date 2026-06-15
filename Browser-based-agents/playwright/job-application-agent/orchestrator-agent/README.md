# Job Application Agent

![tag:user-facing](https://img.shields.io/badge/user--facing-3D8BD3)
![tag:playwright](https://img.shields.io/badge/playwright-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

Conversational job-application assistant built on ASI:One. Manages your profile and resume, then fills Greenhouse applications end-to-end via Playwright — with a per-application Stripe payment gate.

**Agentverse profile:** [agent1qwyqpyj3h3ktnlagx0nzjw58py8d8s7vkf0ud09f3aewdzk0le6nsku07sl](https://agentverse.ai/agents/details/agent1qwyqpyj3h3ktnlagx0nzjw58py8d8s7vkf0ud09f3aewdzk0le6nsku07sl/profile)

## What it does

**Profile management**
- Upload a resume (PDF, DOCX, TXT) directly in chat — parsed to markdown via ASI:One and stored with versioning.
- Edit any field in plain English: name, contact, work authorisation, EEO, education, experience.
- `show my profile` / `whoami` to review stored data at any time.

**Applying for jobs**
- Paste any Greenhouse URL — the agent scrapes the form, maps fields from your profile, drafts free-text answers with a compose→critique→revise loop, and streams live screenshots into chat.
- A **one-time Stripe payment is required per application** (configurable; disabled by default). The payment card appears before the form fill begins.
- Answers collected during each application are saved back to the profile for future use.

## Setup

```bash
cd Browser-based-agents/playwright/job-application-agent
cp .env.example .env          # fill in ASI_ONE_API_KEY, AGENTVERSE_API_KEY
cd orchestrator-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python agent.py
```

## Environment variables

All vars live in `job-application-agent/.env` (one level above `orchestrator-agent/`). See `.env.example` for the full list. Key ones:

| Variable | Required | Notes |
|---|---|---|
| `ASI_ONE_API_KEY` | Yes | ASI:One LLM key |
| `AGENTVERSE_API_KEY` | Yes | For Agentverse registration |
| `DEFAULT_RESUME_PATH` | Recommended | Path to a default resume file |
| `LIVE_FILL_MODE` | No | `headed` (default) opens a visible Chrome window; `off` runs headless |
| `PAYMENT_ENABLED` | No | `false` by default; set to `true` + add Stripe keys to charge per application |
| `STRIPE_SECRET_KEY` | If paying | Stripe secret key |
| `STRIPE_AMOUNT_CENTS` | If paying | Amount to charge (default `100` = $1.00) |

## Chat commands

| Say | What happens |
|---|---|
| `hi` / `hello` | Onboarding walkthrough |
| `help` | Full capability list |
| `show my profile` / `whoami` | Display stored profile |
| `my phone is +1-555-1234` | Update a profile field in plain English |
| `set my work auth to US Citizen` | Update work authorisation |
| `<greenhouse URL>` | Start an application (payment card shown first if gate is active) |
| `cancel` | Discard in-progress application |

## Internals

| File | Purpose |
|---|---|
| `agent.py` | Chat handler, intent router, Agentverse registration |
| `intents.py` | ASI:One classifier + regex short-circuits |
| `browser_filler.py` | Playwright form-fill engine |
| `extractor.py` | Greenhouse form scraper |
| `field_mapper.py` | Profile → form field mapping via ASI:One |
| `answer_composer.py` | LangGraph compose→critique→revise loop for free-text answers |
| `profile_store.py` | Persistent profile storage via `ctx.storage` |
| `resume_store.py` | Resume versioning and retrieval |
| `resume_ingest.py` | PDF/DOCX/TXT → markdown via ASI:One |
| `rendering.py` | Chat card and carousel formatters |
| `payment_proto.py` | Stripe payment gate integration |
| `session.py` | `OrchestratorSession` + storage helpers |
