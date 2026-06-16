#!/usr/bin/env bash
# Fetch.ai / uAgents / Agentverse / ASI:One focused issues — full briefs.
# Does NOT delete or modify existing issues, workflows, or contributor setup.
set -euo pipefail
REPO="${1:-fetchai/innovation-lab-examples}"

create_label() {
  gh label create "$1" --description "$2" --color "$3" -R "$REPO" 2>/dev/null || true
}

create_label "fetch-tech" "Fetch.ai stack: uAgents, Agentverse, ASI:One" "3D8BD3"
create_label "uagents" "uAgents framework" "1B4F8A"
create_label "agentverse" "Agentverse deployment & discovery" "6F42C1"
create_label "asi-one" "ASI:One LLM integration" "E36209"

issue() {
  local title="$1"
  local labels="$2"
  if gh issue list -R "$REPO" --search "in:title \"$title\"" --json title --jq '.[].title' 2>/dev/null | grep -Fxq "$title"; then
    echo "SKIP: $title"
    return
  fi
  local body
  body=$(cat)
  gh issue create -R "$REPO" --title "$title" --label "$labels" --body "$body"
  echo "OK: $title"
}

issue "[Fetch] uAgent: Weather + Almanac agent with mailbox (no paid API)" \
  "ai-agent-idea,fetch-tech,uagents,intermediate,help wanted" <<'EOF'
## Overview
Build a **beginner-friendly uAgent** under `contributors/weather-almanac-agent/` that answers natural-language weather questions using a **free public API** (e.g. Open-Meteo) and returns formatted replies via the **Agent Chat Protocol** so it is discoverable on **Agentverse** and testable from **ASI:One**.

## Why this matters (Fetch stack)
- Teaches the core loop: `uagents` → `Protocol` (chat) → `@agent.on_message` → LLM optional for phrasing
- No Stripe or Web3 required — ideal hackathon / GSSoC entry point
- Demonstrates **mailbox** deployment path documented in Innovation Lab

## Technical requirements

### uAgents
- Python 3.10+, `uagents` latest compatible with repo examples
- Unique `SEED_PHRASE` in `.env.example`
- Register **chat protocol** (see `fetch-hackathon-quickstarter/` and `contributors/community_agent/`)

### Agentverse
- README section: **Connect via Mailbox** with Agent Inspector URL pattern
- Screenshot of agent listed on Agentverse after mailbox connect
- Optional: Agent profile README tags (`![tag:innovationlab](...)`)

### ASI:One (optional enhancement)
- Use ASI:One to rewrite raw API JSON into a friendly paragraph when `ASI1_API_KEY` is set
- Graceful fallback: template-based reply if key missing

## User stories
1. *"What's the weather in London tomorrow?"* → temp, conditions, wind
2. *"Compare Paris vs Berlin this weekend"* → side-by-side summary
3. Invalid city → clear error, no stack trace to user

## Acceptance criteria
- [ ] Folder: `contributors/weather-almanac-agent/` with `agent.py`, `requirements.txt`, `README.md`, `.env.example`
- [ ] Runnable locally in under 5 minutes (documented steps)
- [ ] Chat protocol messages handled; no blocking `requests` in async handlers (use `aiohttp`/`httpx`)
- [ ] `contributors/CHANGELOG.md` updated
- [ ] Root README **Community Contributors** table row added
- [ ] Demo image in `assets/demo.png`

## References in this repo
- [fetch-hackathon-quickstarter](https://github.com/fetchai/innovation-lab-examples/tree/main/fetch-hackathon-quickstarter)
- [asi-cloud-agent](https://github.com/fetchai/innovation-lab-examples/tree/main/asi-cloud-agent)
- [Innovation Lab — uAgent creation](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation)

## Out of scope
- Paid weather APIs, flight booking, payments
EOF

issue "[Fetch] Multi-uAgent Bureau: orchestrator routes to specialist workers" \
  "ai-agent-idea,fetch-tech,uagents,intermediate,challenge" \
  <<'EOF'
## Overview
Create `contributors/bureau-routing-demo/` — a **minimal Bureau / orchestrator pattern** where one **coordinator uAgent** receives chat messages and delegates to 2–3 **worker uAgents** (e.g. `search_worker`, `summarize_worker`, `format_worker`) using uAgents messaging (REST fan-out or direct agent-to-agent as in Appliance Whisperer).

## Fetch technologies
| Layer | Use |
|-------|-----|
| **uAgents** | 1 orchestrator + N workers, each with own seed |
| **Chat Protocol** | Only orchestrator exposed to Agentverse |
| **ASI:One** | Workers may call ASI:One for reasoning steps |
| **Agentverse** | Single mailbox-connected orchestrator profile |

## Architecture (target)
```
User (ASI:One / Agentverse Chat)
        ↓ Chat Protocol
   Orchestrator uAgent
    ↙    ↓    ↘
Worker A  B  C  (internal ports / agent addresses)
```

## Detailed tasks
1. **Orchestrator** parses intent (keyword or ASI:One) and picks worker(s)
2. **Workers** implement one capability each (document in README)
3. **docker-compose.yml** (optional) to start all agents with one command
4. Document **local testing** via Agent Inspector before mailbox

## Acceptance criteria
- [ ] Clear README architecture diagram (mermaid acceptable)
- [ ] `.env.example` lists all seeds and API keys
- [ ] End-to-end demo: one user message → orchestrated reply
- [ ] No secrets in repo; workers fail gracefully if peer offline
- [ ] Pattern referenced from `openai-agent-sdk/Appliance Auto Whisperer` where relevant

## Learning outcomes for contributors
- Understand when to use **one public agent** vs **many internal agents**
- Practice **Agent Chat Protocol** compatibility for ASI:One discovery

## Docs
- [uAgents Bureau](https://github.com/fetchai/uAgents/tree/main/python/src/uagents/contrib/bureau) (if used)
- [Innovation Lab chat protocol examples](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents)
EOF

issue "[Fetch] ASI:One agent with structured JSON tool output for Agentverse UI" \
  "enhancement,fetch-tech,uagents,asi-one,intermediate" \
  <<'EOF'
## Problem
Many examples return plain markdown in chat. Agentverse and ASI:One can render richer UX when agents return **structured payloads** (cards, lists, deep links) alongside text.

## Goal
Add or extend **one existing example** (or new `contributors/structured-chat-agent/`) to return **JSON-structured chat content** (e.g. list of results with `title`, `url`, `summary`) while remaining **ASI:One compatible**.

## Full brief

### 1. Protocol layer
- Use uAgents **chat protocol** message types already in repo (`mcp-agents/ticketlens-agent`, `security-scanner-agent`)
- Document the schema in README (fields, types, example payload)

### 2. ASI:One
- System prompt instructs model to emit parseable structure when user asks for search/list/booking style queries
- Validate JSON before sending; fallback to markdown on parse failure

### 3. Agentverse
- README: how structured messages appear in **Chat with Agent**
- Screenshot showing structured vs plain reply

### 4. Implementation checklist
- [ ] `TypedDict` or Pydantic model for outbound message shape
- [ ] Unit test: sample handler returns valid schema
- [ ] `.env.example` with `ASI1_API_KEY`
- [ ] No breaking change to default text-only mode (env flag `STRUCTURED_CHAT=true`)

## References
- `mcp-agents/ticketlens-agent/chat_protocol.py`
- `security-scanner-agent` (Agent Chat Protocol refactor)

## Acceptance
PR with README, demo screenshot, and CHANGELOG entry under `contributors/` or targeted fix to one official example (justify choice in PR).
EOF

issue "[Fetch] Agentverse mailbox deployment guide for 3 undocumented examples" \
  "documentation,fetch-tech,agentverse,uagents,intermediate" \
  <<'EOF'
## Context
Several examples run locally but lack a consistent **Agentverse Mailbox** section (Connect → Mailbox → test on ASI:One). New contributors get stuck after `python agent.py`.

## Task
Pick **three** folders from this list (comment on issue which you chose):
- `pdf-summariser-example/`
- `asi1-llm-example/`
- `advance-agent-examples/basic_agent/`
- `fet-example/`
- `image-agent-payment-protocol/`

For each, add a README section:

### Required sections (copy structure)
1. **Prerequisites** — Agentverse + ASI:One accounts (with Innovation Lab links)
2. **Local run** — venv, `.env`, start command
3. **Mailbox connect** — step-by-step with placeholder inspector URL pattern
4. **Test on Agentverse** — "Chat with Agent" screenshot
5. **Test on ASI:One** — example query screenshot
6. **Troubleshooting** — mailbox not connected, wrong seed, firewall

## Fetch links to cite
- [Mailbox agents](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents)
- [Agentverse](https://agentverse.ai/)
- [ASI:One quickstart](https://innovationlab.fetch.ai/resources/docs/asione/asi-one-quickstart)

## Acceptance criteria
- [ ] 3 READMEs updated, same heading structure
- [ ] No duplicate work — claim examples in issue comments
- [ ] PR references this issue number
- [ ] Doc-only PR acceptable (no `contributors/CHANGELOG` unless code touched)

## Difficulty
Intermediate — requires actually running agents and capturing screenshots.
EOF

issue "[Fetch] FET payment-gated uAgent: micro-payment before premium reply" \
  "ai-agent-idea,fetch-tech,uagents,intermediate,challenge" \
  <<'EOF'
## Overview
Build `contributors/fet-gated-insights-agent/` — a uAgent that gives a **short free preview** then requires a **FET micro-payment** (testnet/sandbox) before returning the full analysis.

## Fetch stack alignment
| Component | Reference in repo |
|-----------|-------------------|
| FET payments | `fet-example/`, `image-agent-payment-protocol/` |
| uAgents chat | `fetch-hackathon-quickstarter/` |
| Payment protocol patterns | Innovation Lab payment docs |

## User flow
1. User asks for "full market brief" or similar
2. Agent returns 2–3 sentence preview + payment request (amount in FET, testnet)
3. After verified payment event → full markdown report (ASI:One generated or template)

## Environment variables (document all)
- `AGENT_SEED` / `SEED_PHRASE`
- `ASI1_API_KEY` (optional)
- FET wallet / network vars per `fet-example/.env.example`
- Explicit **TESTNET ONLY** banner in README

## Safety & compliance
- README must state: **do not use mainnet keys in examples**
- No private keys in repo; `.env.example` only placeholders

## Acceptance criteria
- [ ] Working local demo on testnet (document faucet steps)
- [ ] Chat protocol compatible
- [ ] Payment state machine diagram in README
- [ ] Demo GIF or PNG of free → pay → unlock flow
- [ ] Listed in Community Contributors table

## Stretch goals
- Agentverse mailbox + ASI:One discovery
- Refund / timeout handling documented
EOF

issue "[Fetch] A2A bridge: uAgent host calls external A2A shopping agent" \
  "ai-agent-idea,fetch-tech,uagents,intermediate" \
  <<'EOF'
## Overview
Create `contributors/a2a-bridge-host-agent/` — a **host uAgent** that exposes chat protocol to users and forwards suitable queries to an **A2A agent** from `a2a-uAgents-Integration/a2a-Outbound-Communication/shopping_agent/` (or book-agent).

## Why
Shows how **Fetch uAgents** coexist with **A2A** in one user-facing flow — core Innovation Lab narrative.

## Architecture
```
User → uAgent (chat protocol) → A2A client → shopping_agent (A2A server)
                ↓
         ASI:One (optional intent routing)
```

## Implementation brief
1. **Host agent** — seed, chat handlers, session context (last 3 turns)
2. **Router** — classify: local reply vs delegate to A2A (keywords or ASI:One)
3. **A2A client** — reuse patterns from `a2a-uAgents-Integration/` README
4. **Error handling** — A2A timeout → user-friendly message

## Run instructions (README)
- Terminal 1: start A2A shopping agent
- Terminal 2: start host uAgent
- Terminal 3: Agent Inspector or ASI:One test query

## Acceptance criteria
- [ ] Both agents documented with ports/addresses
- [ ] At least 3 example queries (1 local, 2 delegated)
- [ ] `.env.example` for both components
- [ ] Sequence diagram in README

## References
- [a2a-uAgents-Integration](https://github.com/fetchai/innovation-lab-examples/tree/main/a2a-uAgents-Integration)
- [A2A protocol docs](https://innovationlab.fetch.ai/resources/docs/agent-creation/agent-creation#agent-to-agent-a2a-protocol)
EOF

issue "[Fetch] Agentverse discovery: semantic search wrapper uAgent" \
  "ai-agent-idea,fetch-tech,agentverse,uagents,intermediate" \
  <<'EOF'
## Overview
Build `contributors/agentverse-search-agent/` that lets users ask in natural language **"find me an agent that can …"** and returns **curated Agentverse search results** (or documented mock if API limits apply).

## Fetch technologies
- **uAgents** + chat protocol for user interface
- **Agentverse API / search** (see `openclaw/agentverse-caller` and `deploy-agent-on-av/`)
- **ASI:One** to rewrite user intent into search keywords

## Detailed behavior
| Step | Action |
|------|--------|
| 1 | Parse user goal ("book flights", "summarize PDF") |
| 2 | Query Agentverse search (or static index from repo README table as fallback) |
| 3 | Return top 3 agents: name, description, profile link, capability tags |

## README must include
- Innovation Lab link to **agent discovery**
- How to register **your own** agent so others can find it
- Ethical note: don't spam search; accurate README tags

## Acceptance criteria
- [ ] End-to-end chat flow works locally
- [ ] Structured response (name + link per agent)
- [ ] `.env.example` documents `AGENTVERSE_API_KEY` or equivalent if used
- [ ] Mock mode documented when API key absent

## References
- `openclaw/fetchai-openclaw-orchestrator/` agentverse-caller skill
- Root [README.md](https://github.com/fetchai/innovation-lab-examples/blob/main/README.md) examples index
EOF

issue "[Fetch] ASI:One + uAgents: streaming token replies in chat protocol" \
  "ai-agent-idea,fetch-tech,uagents,asi-one,intermediate,challenge" \
  <<'EOF'
## Problem
Long ASI:One responses block until complete; poor UX on Agentverse chat for reports and summaries.

## Goal
`contributors/streaming-chat-agent/` demonstrating **incremental / streaming** delivery over uAgents chat protocol where supported, with documented fallback to single-shot messages.

## Technical brief

### ASI:One
- Use streaming API if available in ASI:One client (check `asi1-llm-example/`, `asi-cloud-agent/`)
- Buffer chunks; send partial updates per protocol rules

### uAgents
- Document which message types allow partial content updates
- Handler must not block event loop — async throughout

### Agentverse
- README notes on streaming support limitations in UI (honest expectations)
- Video or GIF of streaming vs non-streaming side-by-side if possible

## Acceptance criteria
- [ ] Working demo with 100+ token response
- [ ] Fallback path when streaming disabled
- [ ] Performance note: max chunk rate to avoid flooding
- [ ] Tests or script that simulates slow stream

## Not in scope
- WebSocket frontend (see `frontend-integration/` separately)
EOF

issue "[Fetch] Chat protocol compatibility test suite for contributor agents" \
  "enhancement,fetch-tech,uagents,intermediate" \
  <<'EOF'
## Overview
Add `tests/test_chat_protocol_compat.py` (or `contributors/_tests/`) that validates **minimum chat protocol compliance** for any agent under `contributors/*/agent.py`.

## Motivation
Innovation Lab requires ASI:One / Agentverse discoverability. Automated checks reduce review burden.

## Proposed checks
1. Module imports `uagents` and defines `agent = Agent(...)`
2. Registers a protocol named like `chat` or imports from shared proto module
3. Has `@agent.on_message` or equivalent handler
4. README contains "Agentverse" and "Mailbox" sections
5. `.env.example` exists

## Implementation options
- Static analysis (AST) — no network
- Optional integration test marked `@pytest.mark.integration` with mock messages

## Acceptance criteria
- [ ] CI job or extend `validate-architecture` to run on PRs touching `contributors/`
- [ ] Document how new contributors run tests locally
- [ ] Does not break existing examples outside `contributors/`

## Fetch references
- [ASI-compatible uAgents](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents)
EOF

issue "[Fetch] uAgent storage: persist user preferences with uAgents ctx.storage" \
  "ai-agent-idea,fetch-tech,uagents,intermediate" \
  <<'EOF'
## Overview
`contributors/preferences-memory-agent/` — remembers per-session (or per-user id) preferences: city, language, currency using **uAgents context storage** (see `mcp-agents/ticketlens-agent` persistent storage patterns).

## User stories
1. User: "I'm in Mumbai" → later "What's the weather?" uses Mumbai without re-asking
2. User: "Reset my preferences"
3. User: "What do you remember about me?" (privacy-safe summary)

## Fetch stack
- uAgents `Context` / storage API
- Chat protocol
- Optional ASI:One for NLU slot filling

## Privacy README section
- What is stored locally
- TTL or reset command
- No PII collection policy statement

## Acceptance criteria
- [ ] Preferences survive agent restart (document storage path)
- [ ] `.env.example` + full README
- [ ] 3 automated tests for set/get/reset storage
EOF

issue "[Fetch] Deploy contributor agent to Agentverse via Render (template)" \
  "documentation,fetch-tech,agentverse,uagents,intermediate" \
  <<'EOF'
## Task
Extend `deploy-agent-on-av/` OR add `contributors/DEPLOY_AGENTVERSE.md` guide that walks through deploying **any** `contributors/<agent>/` to **Agentverse via Render** (or Railway).

## Guide must cover
1. Fork → `contributors/your-agent/`
2. `requirements.txt` + `agent.py` entrypoint
3. Render env vars mapping from `.env.example`
4. Mailbox connect after deploy (public URL)
5. ASI:One test query
6. Cost / sleep / free tier caveats

## Deliverables
- [ ] Step-by-step doc with commands (no placeholders like `YOUR_*` without explanation)
- [ ] Link from `contributors/README.md`
- [ ] One screenshot per major step

## References
- [deploy-agent-on-av](https://github.com/fetchai/innovation-lab-examples/tree/main/deploy-agent-on-av)
- [Innovation Lab Render deploy](https://innovationlab.fetch.ai/resources/docs/agent-creation/agent-creation)
EOF

issue "[Fetch] Skyfire + uAgents: pay-per-query document analysis agent" \
  "ai-agent-idea,fetch-tech,uagents,intermediate,challenge" \
  <<'EOF'
## Overview
`contributors/skyfire-gated-analyzer-agent/` — analyze pasted text or URL summary behind **Skyfire payment protocol** (see `image-agent-payment-protocol/`).

## Flow
1. Free: word count + 1-sentence teaser
2. Paid (Skyfire): full structured analysis (bullets, sentiment, entities)

## Fetch alignment
- uAgents + chat protocol
- Skyfire integration patterns from repo
- Agentverse mailbox optional

## README requirements
- Skyfire test credentials setup (Innovation Lab link)
- Diagram: user → agent → Skyfire → unlock
- Compare with Stripe examples in README table

## Acceptance
- [ ] Sandbox/test mode only
- [ ] `contributors/CHANGELOG.md` entry
- [ ] Demo assets
EOF

issue "[Fetch] Almanac / agent communication: two uAgents negotiate meeting time" \
  "ai-agent-idea,fetch-tech,uagents,intermediate" \
  <<'EOF'
## Overview
`contributors/meeting-negotiator-agents/` — **two uAgents** negotiate a meeting slot via agent-to-agent messaging (not human-in-loop), then report result to user via third **coordinator** agent on chat protocol.

## Concepts demonstrated
- Multi-agent coordination on Fetch stack
- Message passing between agent addresses
- Chat protocol for human-facing summary

## Scenario
- Agent A: calendar constraints [Mon 2-4pm, Tue 10-12]
- Agent B: calendar constraints [Mon 3-5pm, Wed 9-11]
- Coordinator: asks both, finds overlap, tells user

## Acceptance
- [ ] docker-compose or Makefile starts 3 agents
- [ ] README sequence diagram
- [ ] No external calendar API required (in-memory schedules OK)

## Stretch
- Replace in-memory with Google Calendar MCP read-only
EOF

issue "[Fetch] Innovation Lab quickstart: single-script setup for any contributors/ agent" \
  "enhancement,fetch-tech,uagents,intermediate" \
  <<'EOF'
## Problem
Root `setup.sh` targets top-level examples; `contributors/<agent>/` lacks unified bootstrap.

## Task
Extend `./setup.sh` to accept `contributors/my-agent` path:
```bash
./setup.sh contributors/weather-almanac-agent
```
Actions: venv, pip install, copy `.env.example` → `.env`, print next steps (run agent, mailbox URL).

## Acceptance
- [ ] Works on macOS/Linux (document Windows WSL)
- [ ] README update in `contributors/README.md`
- [ ] Error if folder has no `requirements.txt`
- [ ] No breaking change for existing `./setup.sh fetch-hackathon-quickstarter` usage
EOF

issue "[Fetch] ASI:One model routing: fallback when primary model unavailable" \
  "enhancement,fetch-tech,asi-one,uagents,intermediate" \
  <<'EOF'
## Overview
Add reusable pattern (module or doc) for **ASI:One model fallback** — try primary model, on 429/5xx retry with secondary or template response.

## Target paths (pick one in PR)
- `asi-cloud-agent/`
- `contributors/community_agent/`
- New `contributors/asi-fallback-demo/`

## Brief
- Exponential backoff (max 3 retries)
- Log model id used (no secrets)
- README: env `ASI1_MODEL_PRIMARY`, `ASI1_MODEL_FALLBACK`

## Acceptance
- [ ] Documented behavior table in README
- [ ] Unit test with mocked HTTP errors
- [ ] Innovation Lab link to ASI:One models docs
EOF

issue "[Fetch] Agent profile generator CLI for Agentverse README tags" \
  "ai-agent-idea,fetch-tech,agentverse,uagents,good first issue" \
  <<'EOF'
## Idea
`contributors/av-profile-cli/` — small CLI that asks agent name, capabilities, tags and outputs:
1. Agentverse **profile markdown** with Innovation Lab shields
2. Suggested `![tag:...]` badges matching repo conventions

## Example output
```markdown
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:uagents](https://img.shields.io/badge/uagents-4A90E2)
...
```

## Stack
- Python `typer` or `argparse`
- No network required

## Acceptance
- [ ] `python -m av_profile_cli --name "My Agent" --tags payments,weather`
- [ ] README with Agentverse paste instructions
- [ ] 2 unit tests
EOF

issue "[Fetch] uAgent health probe for Agentverse Inspector connectivity" \
  "enhancement,fetch-tech,uagents,agentverse,intermediate" \
  <<'EOF'
## Task
Create shared pattern `contributors/_shared/health.py` (or doc-only PR) showing standard **health / readiness** logging when agent starts:

- Agent name, address, protocol registered
- Mailbox status hint
- Version from env `AGENT_VERSION`

Apply to **2 existing** contributor or official examples in same PR.

## Why
Speeds up Agentverse debugging ("is my agent actually running?").

## Acceptance
- [ ] Consistent log lines across 2 agents
- [ ] README troubleshooting section references logs
EOF

echo "Fetch tech issues done."
