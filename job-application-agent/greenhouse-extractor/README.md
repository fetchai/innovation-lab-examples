# Greenhouse Job Extractor Agent

A **helper agent** (not user-facing) that turns a Greenhouse job URL into a
structured job posting + application form schema. It's the first building
block of the larger job-application agent.

## What it does

Given a URL like `https://boards.greenhouse.io/<company>/jobs/<id>`, it
returns:

- Job metadata: title, company, location, departments, offices, employment type, canonical URL
- Description in both Markdown (LLM-friendly) and HTML
- Application form schema: every question + its fields (name, type, required,
  allowed values for selects)

Uses Greenhouse's public Job Board API
(`boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}?questions=true`) — no
scraping, no auth needed.

## How it's structured

- `extractor.py` — pure **LangGraph** pipeline. State machine:
  `parse_url → fetch_job → assemble → END` with an `on_error` branch. Easy to
  unit-test and reusable by other agents (just `from extractor import extract`).
- `agent.py` — uAgent wrapper exposing two interfaces:
  1. **Typed agent-to-agent**: send `ExtractJobRequest(url=...)`, receive
     `ExtractJobResponse(success, error, job)`. Other uAgents should use this.
  2. **Chat protocol**: send a chat message containing the URL, get the
     JSON back. For ASI:One and chat clients.

## Setup

```bash
cd job-application-agent/greenhouse-extractor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ensure the repo-root `.env` has `AGENTVERSE_API_KEY=...` so the agent
registers itself on Agentverse on startup.

## Quick CLI test (no agent runtime needed)

```bash
python extractor.py "https://boards.greenhouse.io/<company>/jobs/<id>"
```

## Run as an agent

```bash
python agent.py
```

On startup it logs its address and `Registered with Agentverse`. Other agents
can then talk to it via `ExtractJobRequest`/`ExtractJobResponse`.

## Calling from another uAgent

```python
from typing import Optional
from uagents import Agent, Context, Model

EXTRACTOR_ADDRESS = "agent1q..."  # printed at startup

# Mirror the message models from agent.py (or import them if co-located).
# `job` is a dict matching extractor.JobInfo; rehydrate with JobInfo.model_validate(msg.job).
class ExtractJobRequest(Model):
    url: str

class ExtractJobResponse(Model):
    success: bool
    error: Optional[str] = None
    job: Optional[dict] = None

@my_agent.on_event("startup")
async def go(ctx: Context):
    await ctx.send(EXTRACTOR_ADDRESS, ExtractJobRequest(
        url="https://boards.greenhouse.io/<company>/jobs/<id>"
    ))

@my_agent.on_message(ExtractJobResponse)
async def handle(ctx: Context, sender: str, msg: ExtractJobResponse):
    if msg.success:
        ctx.logger.info(f"{msg.job['title']} ({len(msg.job['questions'])} form questions)")
    else:
        ctx.logger.error(msg.error)
```

## Next building blocks

- **Profile agent**: stores the user's resume / answers and fills form fields.
- **Submission agent**: wraps Greenhouse's `/v1/applications` POST endpoint.
- **Orchestrator**: takes a URL + user profile, fans out to extractor + profile
  + submission agents to actually apply.
