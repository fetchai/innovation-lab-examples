#!/usr/bin/env bash
# Creates labeled intermediate contributor issues. Safe to re-run (skips duplicates by title).
set -euo pipefail
REPO="${1:-fetchai/innovation-lab-examples}"
cd "$(git rev-parse --show-toplevel)"

create_label() {
  gh label create "$1" --description "$2" --color "$3" -R "$REPO" 2>/dev/null || true
}

create_label "ai-agent-idea" "New agent example for contributors/" "1D76DB"
create_label "intermediate" "Intermediate difficulty" "FBCA04"
create_label "documentation" "Docs improvements" "0075CA"
create_label "challenge" "Multi-step or real-time agent challenge" "B60205"
create_label "good-first-issue-alias" "Starter task" "0E8A16"

issue() {
  local title="$1"
  local labels="$2"
  local body="$3"
  if gh issue list -R "$REPO" --search "in:title \"$title\"" --json title --jq '.[].title' | grep -Fxq "$title"; then
    echo "SKIP: $title"
    return
  fi
  gh issue create -R "$REPO" --title "$title" --label "$labels" --body "$body"
  echo "OK: $title"
}

# --- Bugs ---
issue "[Bug] Replace blocking requests with aiohttp in av-script-example agent" "bug,intermediate,help wanted" "$(cat <<'EOF'
**Path:** `av-script-example/agent.py`

`requests.post` inside async handlers can block the uAgent event loop.

## Task
- Replace with `aiohttp` or `httpx.AsyncClient`
- Keep timeout and error handling
- Update README if install deps change

## Acceptance
- [ ] No blocking `requests` in async paths
- [ ] Example still runs locally
- [ ] PR under `contributors/` only if adding new code; otherwise fix in place
EOF
)"

issue "[Bug] Async-safe HTTP in youtube_summarizer A2A agent" "bug,intermediate,help wanted" "$(cat <<'EOF'
**Path:** `a2a-uAgents-Integration/a2a-Outbound-Communication/youtube_summarizer/agent.py`

Uses `requests.get` in async context.

## Acceptance
- [ ] Use async HTTP client
- [ ] Document any new dependency in README
EOF
)"

issue "[Bug] Validate required env vars at startup for duffel-agent" "bug,intermediate,help wanted" "$(cat <<'EOF'
**Path:** `duffel-agent/`

Fail fast with a clear message when `DUFFEL_API_KEY` or other required vars are missing.

## Acceptance
- [ ] Startup check lists all missing vars
- [ ] README documents each variable
- [ ] `.env.example` complete
EOF
)"

issue "[Bug] Add startup env validation to deploy-agent-on-av example" "bug,good first issue,help wanted" "$(cat <<'EOF'
**Path:** `deploy-agent-on-av/`

Contributors report confusing runtime failures when `.env` is incomplete.

## Acceptance
- [ ] Friendly error if required keys missing
- [ ] `.env.example` aligned with code
EOF
)"

issue "[Bug] Fix Nike products agent blocking requests.get in async handler" "bug,intermediate" "$(cat <<'EOF'
**Path:** `Browser-based-agents/Notte-labs-agent/Nike-products-agent/agent.py`

## Acceptance
- [ ] Non-blocking HTTP for health/check calls
- [ ] README note on async pattern
EOF
)"

# --- Documentation ---
issue "[Docs] Add video-to-map-agent to root README examples index" "documentation,good first issue,help wanted" "$(cat <<'EOF'
**Path:** `video-to-map-agent/`

Example exists but is missing from the categorized table in root `README.md`.

## Acceptance
- [ ] Row added with description, stack, difficulty
- [ ] Link tested
EOF
)"

issue "[Docs] Add security-scanner-agent to README index table" "documentation,intermediate" "$(cat <<'EOF'
**Path:** `security-scanner-agent/` (or actual folder name on main)

Add merged agent to appropriate README section with difficulty tag.
EOF
)"

issue "[Docs] Create EXAMPLES_STATUS.md with run status per example" "documentation,intermediate,enhancement" "$(cat <<'EOF'
Track which examples were smoke-tested on Python 3.11+ with last verified date.

## Acceptance
- [ ] Table: folder | last tested | owner | notes
- [ ] Link from root README
EOF
)"

issue "[Docs] Standardize innovationlab badge line across agent READMEs" "documentation,intermediate" "$(cat <<'EOF'
Many examples use slightly different shield URLs. Pick one canonical markdown snippet in `docs/` and apply to 5+ READMEs missing it.
EOF
)"

issue "[Docs] Document maintainer bypass for review-required CI" "documentation,good first issue" "$(cat <<'EOF'
Ensure `CONTRIBUTING.md` explains maintainers skip review — cross-link `.github/MAINTAINERS`.
EOF
)"

# --- AI agent ideas (contributors/) ---
issue "[AI Agent] Hotel booking agent with sandbox API under contributors/" "ai-agent-idea,intermediate,challenge,help wanted" "$(cat <<'EOF'
Build under `contributors/hotel-booking-agent/`.

## Features
- Search hotels by city/dates (sandbox API)
- Compare options in chat
- Mock confirmation step

## Stack
uAgents + ASI:One + `.env.example` + demo screenshot

## References
`duffel-agent/`, `mcp-agents/ticketlens-agent/`
EOF
)"

issue "[AI Agent] Stripe-gated restaurant reservation agent" "ai-agent-idea,intermediate,challenge" "$(cat <<'EOF'
**Folder:** `contributors/restaurant-reservation-agent/`

Free preview of availability; Stripe unlock for booking details (see `stripe-payment-agents/` patterns).
EOF
)"

issue "[AI Agent] Multi-city trip planner with payment gate" "ai-agent-idea,intermediate,challenge" "$(cat <<'EOF'
Combine flight search + hotel shortlist + itinerary markdown report. Optional Stripe for full export.

**Path:** `contributors/trip-planner-agent/`
EOF
)"

issue "[AI Agent] Real-time crypto price alert uAgent" "ai-agent-idea,intermediate" "$(cat <<'EOF'
**Path:** `contributors/crypto-alert-agent/`

Poll public API, alert on threshold, chat protocol responses. No paid API required.
EOF
)"

issue "[AI Agent] MCP-powered GitHub PR summarizer for contributors/" "ai-agent-idea,intermediate" "$(cat <<'EOF'
Use MCP or GitHub API to summarize open PRs/issues for a repo. Reference `mcp-agents/Github MCP Agent/`.
EOF
)"

issue "[AI Agent] Invoice OCR + expense categorization agent" "ai-agent-idea,intermediate" "$(cat <<'EOF'
Upload receipt image → extract fields → categorize (see `stripe-payment-agents/expense-calculator-group/` for payment ideas).

**Path:** `contributors/invoice-agent/`
EOF
)"

issue "[AI Agent] Language-learning flashcard agent with spaced repetition" "ai-agent-idea,intermediate" "$(cat <<'EOF'
Chat-driven flashcards, local JSON or uAgents storage. Good ASI:One demo without external paid APIs.
EOF
)"

issue "[AI Agent] Job application copilot (read-only) under contributors/" "ai-agent-idea,intermediate" "$(cat <<'EOF'
Paste job URL → structured checklist, cover letter draft, skills gap. No auto-apply; read-only web fetch.
EOF
)"

issue "[AI Agent] Smart meeting scheduler with Google Calendar MCP" "ai-agent-idea,intermediate,challenge" "$(cat <<'EOF'
Reference `mcp-agents/calendar_chat_uagent/`. Propose slots, confirm in chat, sandbox mode documented.
EOF
)"

issue "[AI Agent] RAG wiki agent for open-source docs" "ai-agent-idea,intermediate" "$(cat <<'EOF'
Index a small markdown corpus (e.g. CONTRIBUTING + contributors README), answer setup questions.

**Path:** `contributors/docs-rag-agent/`
EOF
)"

# --- Intermediate improvements ---
issue "[Intermediate] Add pytest smoke test for contributors/community_agent" "enhancement,intermediate" "$(cat <<'EOF'
**Path:** `contributors/community_agent/tests/`

Minimal test: import agent module, mock LLM, assert handler registration.
EOF
)"

issue "[Intermediate] Add Docker Compose for fetch-hackathon-quickstarter" "enhancement,intermediate" "$(cat <<'EOF'
One-command `docker compose up` for hackathon onboarding. Document in README.
EOF
)"

issue "[Intermediate] Add healthcheck endpoint pattern to 3 uAgent examples" "enhancement,intermediate" "$(cat <<'EOF'
Pick three examples without clear health/diagnostic messages; add consistent `/health` or documented ping via chat.
EOF
)"

issue "[Intermediate] Migrate brand-management-agent image fetch to aiohttp" "enhancement,intermediate,bug" "$(cat <<'EOF'
**Path:** `google-genai-parallel-processing/brand-management-agent/agent.py` uses `requests.get` for images.
EOF
)"

issue "[Intermediate] Add rate limiting helper for public API agents" "enhancement,intermediate" "$(cat <<'EOF'
Create small reusable module (or doc pattern) for backoff/rate limits used by 2+ examples.
EOF
)"

issue "[Intermediate] Add Agentverse mailbox section to 5 READMEs" "documentation,intermediate" "$(cat <<'EOF'
Several examples lack Agentverse deploy steps. Pick 5 and add consistent mailbox + profile sections per `docs/AGENT_README_TEMPLATE.md`.
EOF
)"

issue "[Intermediate] Wire optional Langfuse tracing in one contributor agent" "enhancement,intermediate" "$(cat <<'EOF'
Document optional observability; env-gated so default run needs no extra keys.
EOF
)"

issue "[Intermediate] Add structured JSON chat responses for one MCP agent" "enhancement,intermediate" "$(cat <<'EOF'
Return machine-readable booking/search results alongside markdown (ticketlens-style deep links).
EOF
)"

issue "[Intermediate] Create contributors/agent-starter template folder" "enhancement,intermediate,help wanted" "$(cat <<'EOF'
`contributors/_template/` with README, agent.py stub, `.env.example`, `requirements.txt` — clone for new PRs.
EOF
)"

issue "[Intermediate] Add pre-commit config for ruff at repo root" "enhancement,intermediate" "$(cat <<'EOF'
Optional `pre-commit` config mirroring CI ruff rules; document in CONTRIBUTING.
EOF
)"

issue "[Intermediate] Audit and fix broken internal markdown links in README" "documentation,intermediate,good first issue" "$(cat <<'EOF'
Run link checker on root + top 10 example READMEs; fix 404 paths.
EOF
)"

issue "[Intermediate] Add CI job to verify contributors/ README has Category tag" "enhancement,intermediate" "$(cat <<'EOF'
Extend `validate-architecture` or new job: every `contributors/*/README.md` must include Category + Difficulty lines.
EOF
)"

issue "[Intermediate] Implement retry with tenacity for ASI API calls in pdf-summariser" "enhancement,intermediate" "$(cat <<'EOF'
**Path:** `pdf-summariser-example/`

Handle transient 429/5xx gracefully.
EOF
)"

issue "[Intermediate] Add streaming chat response example under contributors/" "ai-agent-idea,intermediate,challenge" "$(cat <<'EOF'
Demonstrate token/streaming UX with uAgents chat protocol for long answers.
EOF
)"

issue "[Intermediate] Payment protocol smoke test script for stripe examples" "enhancement,intermediate" "$(cat <<'EOF'
Script using Stripe test keys that validates webhook handler wiring without manual UI.
EOF
)"

issue "[Intermediate] Add OpenAPI-style tool schema docs for one function-calling agent" "documentation,intermediate" "$(cat <<'EOF'
**Path:** `anthropic-quickstart/03-function-calling-agent/` or similar.

Document each tool with JSON schema in README.
EOF
)"

issue "[Intermediate] Localize error messages to English-only consistent tone" "good first issue,intermediate" "$(cat <<'EOF'
Pick 3 examples with mixed error strings; standardize user-facing errors.
EOF
)"

issue "[Intermediate] Add GitHub Action to validate BADGE_REGISTRY.json schema" "enhancement,intermediate" "$(cat <<'EOF'
JSON schema check on `contributors/BADGE_REGISTRY.json` in PR CI.
EOF
)"

issue "[Intermediate] Flight status agent with AviationStack sandbox" "ai-agent-idea,intermediate" "$(cat <<'EOF'
**Path:** `contributors/flight-status-agent/`

Real-time flight status by flight number; reference `flight-tracker-openai-workflow-agent/`.
EOF
)"

issue "[Intermediate] Add CONTRIBUTOR_HALL_OF_FAME.md auto-generated from registry" "documentation,intermediate" "$(cat <<'EOF'
Script or workflow to render `contributors/BADGE_REGISTRY.json` as markdown table in README.
EOF
)"

echo "Done."
