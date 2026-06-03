# Greenhouse Submitter Agent

![tag:helper](https://img.shields.io/badge/helper-3D8BD3)
![tag:submitter](https://img.shields.io/badge/submitter-3D8BD3)
![tag:greenhouse](https://img.shields.io/badge/greenhouse-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

Internal helper agent for the job-application workflow. It takes:

- a structured `JobInfo` (from the [`greenhouse-extractor`](../greenhouse-extractor/) agent),
- a `MapFieldsResult` (from the [`profile-agent`](../profile-agent/)),
- and a resume file path on disk,

and POSTs the application to Greenhouse's public board API:

```
POST https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}
Content-Type: multipart/form-data
```

There is no LLM in this agent — it is a pure executor. The multi-agent
coordination box for Track 1 is checked at the orchestrator level; the
submitter exists as a small, replaceable building block.

## Interfaces

### 1. Typed agent-to-agent protocol — `submitter_agent` v1.0

```python
class SubmitApplicationRequest(Model):
    job_json: str       # JSON-encoded extractor.JobInfo
    filled_json: str    # JSON-encoded profile_agent.MapFieldsResult
    resume_path: str    # absolute path on disk
    dry_run: bool = False

class SubmitApplicationResponse(Model):
    success: bool
    error: Optional[str] = None
    application_id: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    dry_run: bool = False
    missing_required: list[str] = []
    fields_submitted: list[str] = []
```

The rich payloads (`JobInfo`, `MapFieldsResult`) are sent as JSON strings to
sidestep the uagents pydantic-v1 wire-schema limitations. Receivers should
rehydrate with `model_validate_json`.

### 2. REST

- `POST /submit` — body matches `SubmitApplicationRequest`.
- `GET  /health` — returns agent address + default dry-run flag.

### 3. Chat (ASI:One discoverability)

The agent answers `help`, `address`, and `dry-run`. The expected client is
the orchestrator agent, not humans.

## Behaviour

1. Rehydrate `JobInfo` + `MapFieldsResult` from JSON.
2. Compute required-field gap. If any required field is missing, fail fast
   with `missing_required` populated — the orchestrator should have closed
   the gap via `gather_missing` before calling.
3. Build the multipart form body:
   - One field per `FilledField.name → value`.
   - Lists are sent as repeated form keys (for multi-select fields).
   - Booleans are coerced to `"0"` / `"1"`.
   - Empty / `None` values are skipped.
   - The `resume` (or any `input_file`-typed) field is attached from
     `resume_path` as the actual file bytes.
4. POST. If `dry_run` (or `SUBMITTER_DEFAULT_DRY_RUN=1`), skip the request
   and return the prepared payload in `response_body` instead.
5. Parse Greenhouse's JSON response and surface `application_id` when
   present.

## Run it locally

```bash
cd job-application-agent/submitter-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example ../.env   # then fill in AGENTVERSE_API_KEY
python agent.py
```

Smoke-test with `dry_run`:

```bash
curl -s -X POST http://127.0.0.1:8012/submit \
  -H 'Content-Type: application/json' \
  -d "$(cat <<'JSON'
{
  "job_json": "{\"board_token\":\"example\",\"job_id\":\"123\",\"title\":\"SWE\",\"description_markdown\":\"...\",\"description_html\":\"...\",\"questions\":[{\"label\":\"First name\",\"required\":true,\"fields\":[{\"name\":\"first_name\",\"type\":\"input_text\",\"required\":true}]}]}",
  "filled_json": "{\"success\":true,\"filled\":[{\"name\":\"first_name\",\"value\":\"Aditya\",\"source\":\"profile\",\"confidence\":1.0}]}",
  "resume_path": "/tmp/resume.pdf",
  "dry_run": true
}
JSON
)"
```

## Risks / known limits

- Some Greenhouse boards disable the public submission endpoint and force
  their hosted form. The submitter will surface the HTTP status; the
  orchestrator should fall back gracefully.
- Boards that put the ATS behind a vendor-specific iframe (Workday, Lever,
  etc.) are out of scope — the extractor wouldn't have produced a valid
  schema for them in the first place.
- No captcha handling. If a board enables one, expect an HTTP error.
