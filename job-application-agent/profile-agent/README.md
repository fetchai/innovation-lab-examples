# User Profile Agent

Helper agent for the job-application workflow. Stores a user's resume +
structured profile fields once and serves them to other agents so the user
never has to type the same info twice. Built for Track 1 of the Fetch Summer
Cohort (multi-agent orchestration + RAG).

## What it does

Three layers, all wired together:

| Layer | Responsibility | Tech |
|---|---|---|
| 1 - Structured fields | name, email, phone, links, work-auth, EEO, canned answers | `ctx.storage` (uAgents built-in persistence) |
| 2 - Resume file | PDF/DOCX/TXT saved to `data/resumes/`, plain text extracted | `pypdf` / `python-docx` |
| 3 - RAG over resume | embeddings for semantic question answering | Qdrant (local persistent mode) + FastEmbed (`BAAI/bge-small-en-v1.5`) |

The **field mapper** (`field_mapper.py`) combines all three with **ASI:One**
to convert a Greenhouse questions array (the output of the
`greenhouse-extractor` agent) into pre-filled application values:

```
question
  ├── structured-field name match  -> profile column        (source: profile)
  ├── canned-answer label match    -> stored verbatim       (source: canned)
  ├── select-type fuzzy match      -> chosen option         (source: profile)
  ├── free-text RAG + ASI:One      -> grounded composition  (source: rag/llm)
  └── nothing matches              -> added to `missing`
```

## File layout

```
profile-agent/
  agent.py            # uAgent: typed protocol + REST + chat + Agentverse reg
  models.py           # UserProfile, FilledField, MapFieldsResult
  profile_store.py    # Layer 1: ContextStore (ctx.storage) + FileStore (CLI/tests)
  resume_ingest.py    # Layer 2: file copy + text extraction + chunking
  rag.py              # Layer 3: Qdrant + FastEmbed
  field_mapper.py     # The "agentic" piece: combines all three + ASI:One
  data/               # (gitignored) resumes/, qdrant/, agent storage
```

## Setup

```bash
cd job-application-agent/profile-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> First boot downloads the FastEmbed ONNX model (~130 MB) into your
> HuggingFace cache - one-time cost.

Ensure the repo-root `.env` has:
```
AGENTVERSE_API_KEY=...
ASI_ONE_API_KEY=...
```

## Running

```bash
python agent.py
```

On startup it prints the address and registers with Agentverse.

### One-time profile setup (via REST)

```bash
# 1. Save structured profile
curl -X POST http://localhost:8011/profile \
  -H 'content-type: application/json' \
  -d '{
    "user_key": "me",
    "profile_json": "{\"first_name\":\"Aditya\",\"last_name\":\"...\",\"email\":\"you@example.com\",\"phone\":\"+1...\",\"linkedin\":\"https://linkedin.com/in/...\",\"github\":\"https://github.com/...\",\"work_authorization\":\"Student Visa - F1\",\"needs_sponsorship\":true,\"canned_answers\":{\"Why are you interested in this role?\":\"...\"}}"
  }'

# 2. Ingest resume (file already on disk anywhere)
curl -X POST http://localhost:8011/resume \
  -H 'content-type: application/json' \
  -d '{"user_key": "me", "resume_path": "/abs/path/to/resume.pdf"}'

# 3. Inspect
curl http://localhost:8011/profile
curl http://localhost:8011/health
```

The resume is copied into `data/resumes/me.pdf`, parsed, chunked, and indexed
into `data/qdrant/`. From then on, every restart picks the data right back up.

## Agent-to-agent usage

```python
from typing import Optional
from uagents import Model

PROFILE_AGENT_ADDRESS = "agent1q..."  # printed at startup

class MapFieldsRequest(Model):
    user_key: str = "me"
    questions_json: str

class MapFieldsResponse(Model):
    success: bool
    error: Optional[str] = None
    result_json: Optional[str] = None

# inside an orchestrator agent:
import json
questions = job["questions"]  # from greenhouse-extractor's JobInfo
await ctx.send(
    PROFILE_AGENT_ADDRESS,
    MapFieldsRequest(questions_json=json.dumps(questions)),
)

# When the reply comes in, rehydrate:
from models import MapFieldsResult
result = MapFieldsResult.model_validate_json(msg.result_json)
for f in result.filled:
    print(f.name, "->", f.value, f"[{f.source}, {f.confidence:.2f}]")
print("missing:", result.missing)
```

## Track 1 alignment

* **Real task**: avoids re-typing application fields, drafts free-text
  answers from your own resume.
* **Agentic behavior**: multi-layer pipeline (structured lookup -> fuzzy
  select match -> Qdrant RAG -> ASI:One composition) + multi-agent
  coordination (consumed by the extractor and the eventual submitter).
  Clears the "no single prompt -> single response" bar.
* **RAG + vector DB**: Qdrant local + FastEmbed, satisfies the explicit
  Track 1 callout for RAG-based agents.
* **Agentverse registration**: yes, with `innovationlab` tag in the README.
* **ASI:One discoverability**: chat protocol included with `show profile`
  / `whoami` / `help`.
* **Payment**: not on this agent. The orchestrator will gate the final
  submission step with the Fetch payment protocol.

## What's deliberately *not* here yet

* Multi-user auth (single `"me"` key by default - trivially extends with a
  per-user user_key).
* Resume re-parsing on file change (call `/resume` again).
* Field-mapping confidence calibration (currently uses static priors).
