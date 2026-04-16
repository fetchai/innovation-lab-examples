# OpenClaw x Fetch.ai - Secure Local Execution via Autonomous Agents

> **Location in this repo:** [`openclaw/fetchai-openclaw-orchestrator/`](https://github.com/fetchai/innovation-lab-examples/tree/main/openclaw/fetchai-openclaw-orchestrator) — see [`openclaw/README.md`](../README.md). Run commands from **this** directory (`fetchai-openclaw-orchestrator`).

A reference architecture for **safe remote-to-local AI orchestration**.
A public Fetch agent on [Agentverse](https://agentverse.ai) plans work; a local
connector on your machine executes it - without granting remote shell access or
leaking sensitive data.

```
User --> ASI:One --> Orchestrator Agent --> [signed task plan] --> OpenClaw Connector --> Execution --> Results
```

| Component | Where it runs | What it does |
|---|---|---|
| **ASI:One** | Cloud ([asi1.ai](https://asi1.ai)) | Natural-language objective input |
| **Orchestrator Agent** | Agentverse / local | Plans tasks, enforces policy, dispatches work |
| **OpenClaw Connector** | Your machine | Verifies, policy-checks, executes, returns results |

> **New to the project?** Read the [Technical Blog Post](blog/fetch-openclaw-integration.md) for
> a step-by-step walkthrough of how each piece was built, from agent creation through
> mailbox configuration to ASI:One integration.

---

## Featured Use Case: GitHub Repo Health Analyzer

Anyone on ASI:One can type a message like **"Analyze https://github.com/fastapi/fastapi"**
and get back a real health report with:

- Lines of code by language
- Git activity (commits, contributors, recent activity)
- Test detection (frameworks, file count)
- Dependency audit (requirements.txt, package.json, etc.)
- Best practices check (README, LICENSE, CI/CD, SECURITY.md)
- Health score with letter grade (A/B/C/D)

**How it works:** The Fetch agent plans the analysis, OpenClaw clones the repo into a
temporary sandbox and runs static analysis tools (no code from the repo is ever
executed), then returns the results through ASI:One.

**Why all three technologies:** An LLM alone cannot clone repos or run `cloc`. OpenClaw alone
is invisible to other users. A Fetch agent alone has no execution engine. Together, they
provide real tool execution (OpenClaw) accessible to anyone (Fetch/Agentverse) through
natural language (ASI:One).

**See it in action:** [View a Sample Chat on ASI:One](https://asi1.ai/chat/f7ccb160-88bc-46a0-bd44-041483eca338)

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- A [Fetch Agentverse](https://agentverse.ai) account & API key
- An [ASI:One](https://asi1.ai) API key (for LLM-powered planning)
- Git (for the repo analyzer workflow)

### 2. Install

```bash
cd path/to/innovation-lab-examples/openclaw/fetchai-openclaw-orchestrator

python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Configure

Copy the example and fill in your keys:

```bash
cp .env.example .env
# Then edit .env and add your real API keys
```

See [Environment Variables](#environment-variables) below for the full list.
You will need at minimum:
- `AGENTVERSE_API_KEY` from [agentverse.ai/profile/api-keys](https://agentverse.ai/profile/api-keys)
- `ASI_ONE_API_KEY` from [asi1.ai](https://asi1.ai) (for LLM-powered planning)

### 4. Set Up Demo Data

Create safe sample repositories (fake git history) for the weekly report workflow:

```bash
python scripts/setup_demo.py
```

This generates a `demo_projects/` directory with 3 sample repos and ~12 fake
commits - **no real system data is ever touched during testing**.

### 5. Run

```bash
# Terminal 1 - Orchestrator Agent
python -m orchestrator.agent

# Terminal 2 - OpenClaw Connector (auto-pairs with orchestrator)
ORCHESTRATOR_AGENT_ADDRESS=<address-from-terminal-1> python -m connector.server
```

On startup the connector sends a pairing request to the orchestrator.
You should see `Paired successfully` in the connector logs.

### 6. Register Mailbox (for ASI:One access)

With the orchestrator running, register its mailbox on Agentverse so ASI:One
can deliver messages to it:

```bash
python -c "
import requests, os
from dotenv import load_dotenv
load_dotenv()
resp = requests.post('http://127.0.0.1:8200/connect', json={
    'user_token': os.getenv('AGENTVERSE_API_KEY'),
    'agent_type': 'mailbox',
}, timeout=30)
print(resp.json())
"
```

You should see `{'success': True, 'detail': None}` and the orchestrator logs
will show `Successfully registered as mailbox agent in Agentverse`.

---

## Testing from ASI:One

Once both agents are running and the mailbox is registered, go to
**[ASI:One](https://asi1.ai)** and send a message to the agent.

### Repo Health Analyzer Prompts

| Prompt | What it does |
|---|---|
| `Analyze https://github.com/fastapi/fastapi` | Full health report for FastAPI |
| `Check the health of https://github.com/pallets/flask` | Health report for Flask |
| `Review https://github.com/fetchai/innovation-lab-examples/tree/main/openclaw/fetchai-openclaw-orchestrator` | Analyze this example in the Innovation Lab repo |
| `Analyze https://github.com/expressjs/express` | Health report for Express.js |
| `https://github.com/django/django` | Even just a URL works |

### Weekly Dev Report Prompts

| Prompt | What it does |
|---|---|
| `Generate my weekly dev report` | Scans demo repos, generates Markdown report |
| `Scan my projects and create a summary, then post to Slack` | 3-step: scan, report, post (Slack) |
| `Look at my repos and email the report to my team` | 3-step: scan, report, post (email) |
| `Summarize: we shipped 3 features this week` | Runs text summarisation |

### Sample Chat

See a real conversation with the agent on ASI:One:
[**View Sample Chat on ASI:One**](https://asi1.ai/chat/f7ccb160-88bc-46a0-bd44-041483eca338)

### What You'll See (Repo Analyzer)

```
Repo Health Report: fastapi/fastapi
Health Score: 8.7/10 (Grade: A)

Languages:
  Python: 82.3% (48,200 lines)
  Markdown: 12.1% (7,100 lines)

Project Stats:
  Total Files: 1,245
  Repo Size: 12.3 MB

Git Activity:
  Total Commits: 3,456
  Commits (last 30 days): 124
  Contributors: 485

Testing:
  Test Files Found: 340
  Frameworks Detected: pytest

Best Practices:
  README: pass
  LICENSE: pass
  CI/CD Pipeline: pass
  SECURITY.md: pass
```

---

## Running Tests

```bash
pytest                # run all 68 tests
pytest -v             # verbose
pytest --cov          # with coverage
```

### End-to-End Local Test

```bash
python scripts/local_test.py
```

This simulates the full flow (pair, plan, dispatch, execute, result)
in a single process without needing the agents to be running.

---

## Project Structure

```
fetchai-openclaw-orchestrator/
|-- orchestrator/                 # Fetch Orchestrator Agent (Agentverse)
|   |-- agent.py                  #   Main entry point, agent construction
|   |-- planner.py                #   Objective -> TaskPlan (ASI:One LLM + fallback)
|   |-- policy.py                 #   Fetch-side policy engine
|   |-- storage.py                #   In-memory device pairing store
|   +-- protocols/
|       |-- chat.py               #   AgentChatProtocol for ASI:One
|       |-- objective.py          #   Objective intake + task dispatch
|       |-- pairing.py            #   Device pairing protocol
|       +-- models.py             #   uAgents message models
|
|-- connector/                    # OpenClaw Connector (local machine)
|   |-- server.py                 #   Main entry point, auto-pairing
|   |-- executor.py               #   Task plan execution engine
|   |-- auth.py                   #   Signature verification
|   |-- policy.py                 #   Local policy engine (path sandbox, etc.)
|   +-- workflows/
|       |-- weekly_report.py      #   scan_directory, generate_report, post_summary
|       +-- repo_analyzer.py      #   clone_repo, analyze_repo, generate_health_report
|
|-- shared/                       # Shared between orchestrator & connector
|   |-- schemas.py                #   Pydantic models (TaskPlan, TaskStep, etc.)
|   +-- crypto.py                 #   Ed25519 key management & signing
|
|-- scripts/
|   |-- local_test.py             #   End-to-end local integration test
|   +-- setup_demo.py             #   Generate demo_projects/ with fake repos
|
|-- tests/                        #   68 unit tests
|-- blog/
|   +-- fetch-openclaw-integration.md  #   Technical blog post (step-by-step walkthrough)
|-- pyproject.toml                #   Project metadata & dependencies
|-- requirements.txt              #   Pinned dependencies
+-- .env                          #   Environment variables (not committed)
```

---

## Architecture Deep Dive

For a full step-by-step walkthrough with code samples, see the
[Technical Blog Post](blog/fetch-openclaw-integration.md).

### How It Works

**1. Agent Creation (uAgents)**

The orchestrator is a [uAgent](https://github.com/fetchai/uAgents) built with `uagents==0.23.6`.
The `Agent` class handles identity (Ed25519 keypair from the seed), messaging, protocol
registration, and Almanac registration on `testnet`.

**2. ASI:One Compatibility (AgentChatProtocol)**

The agent implements the standard `AgentChatProtocol` from `uagents-core==0.4.1`.
When included with `publish_manifest=True`, the protocol manifest is published to
Agentverse, which makes ASI:One able to discover and communicate with the agent.

**3. Agentverse Mailbox (Local Agent, Global Reach)**

The agent runs on your machine but uses an Agentverse mailbox for inbound messages.
Messages from ASI:One are delivered to Agentverse, and the local agent polls for them.
No public IP, no port forwarding, no ngrok needed.

**4. Two Workflows**

The system supports two workflows out of the box:

| Workflow | Actions | Use |
|---|---|---|
| **Repo Health Analyzer** | `clone_repo` -> `analyze_repo` -> `generate_health_report` | Public: analyze any GitHub repo |
| **Weekly Dev Report** | `scan_directory` -> `generate_report` -> `post_summary` | Paired: scan local repos |

**5. Signed Task Plans**

Every task dispatch carries an Ed25519 signature over the full task plan. The
connector's `RequestAuthenticator` verifies the signature against the orchestrator's
public key before executing anything. Tampered payloads are rejected.

**6. Dual Policy Enforcement**

Policies are checked at two independent layers:

| Layer | When | What it checks |
|---|---|---|
| Fetch-side (`orchestrator/policy.py`) | Planning time | Max steps, action allowlists, rate limits |
| Local (`connector/policy.py`) | Execution time | Path sandboxing, action allowlists, no background execution |

The orchestrator **cannot** bypass local policies. Your machine always has the final say.

**7. Intelligent Planning (ASI:One LLM)**

When `ASI_ONE_API_KEY` is set, the orchestrator calls the [ASI:One LLM](https://docs.asi1.ai)
(OpenAI-compatible API at `https://api.asi1.ai/v1`, model `asi1`) to convert
natural-language objectives into structured task plans. If the LLM is unavailable,
the planner falls back to keyword matching.

**8. Safety Model (Repo Analyzer)**

For the repo analyzer workflow specifically:
- Only public GitHub HTTPS URLs are accepted
- Repos are cloned into a temporary sandbox directory
- No code from the repo is ever executed, imported, or installed
- Size limit enforced (500 MB default)
- Temp directory is deleted after analysis completes
- Only static analysis tools are used (line counts, file parsing, git history)

**9. Feedback Loop Protection**

When integrating with ASI:One, a practical challenge emerges: ASI:One's LLM sometimes
rewrites agent responses and sends them back as new objectives, creating infinite loops.
The chat handler includes multi-layered protection:
- **Echo pattern detection** - 100+ known ASI:One rewrite patterns are blocked
- **Emoji density check** - messages with 3+ emoji (typical of LLM rewrites) are filtered
- **Per-sender cooldown** - 30-second minimum between objectives from the same sender
- **Exact dedup** - identical objectives within a 120-second window are ignored
- **Pending task cap** - maximum 5 concurrent tasks; stale entries are pruned
- **No intermediate messages** - the agent stays silent until the final result, avoiding
  the primary trigger for ASI:One's echo behavior

### End-to-End Data Flow (Repo Analyzer)

```
 1. User types: "Analyze https://github.com/fastapi/fastapi" in ASI:One
 2. ASI:One sends ChatMessage to the agent address
 3. Agentverse mailbox holds the message
 4. Local orchestrator polls and receives it
 5. Chat handler runs feedback loop detection (echo patterns, cooldown, dedup)
 6. Chat handler extracts the text and GitHub URL
 7. Planner produces TaskPlan: [clone_repo, analyze_repo, generate_health_report]
 8. Fetch-side policy validates the plan
 9. Plan is serialised, signed with Ed25519, dispatched to connector
10. Connector verifies signature, checks local policy
11. clone_repo: shallow-clone into temp sandbox
12. analyze_repo: cloc, git stats, deps, tests, security checks
13. generate_health_report: compile scored Markdown report, delete temp dir
14. Results sent back to orchestrator -> formatted -> sent to ASI:One (no intermediate messages)
```

---

## Key Technologies

| Technology | Version | Role |
|---|---|---|
| [uAgents](https://github.com/fetchai/uAgents) | `0.23.6` | Agent framework: identity, messaging, protocols, lifecycle |
| [uAgents-core](https://pypi.org/project/uagents-core/) | `0.4.1` | Core protocol specs including AgentChatProtocol |
| [Agentverse](https://agentverse.ai) | | Agent hosting, discovery, mailbox relay, manifest publishing |
| [ASI:One Chat](https://asi1.ai) | | User-facing chat interface for interacting with agents |
| [ASI:One LLM](https://docs.asi1.ai) | model: `asi1` | OpenAI-compatible API for intelligent task planning |
| [AgentChatProtocol](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents) | `0.3.0` | Standard protocol for ASI:One discoverability |
| [Ed25519](https://en.wikipedia.org/wiki/EdDSA) | | Asymmetric signing for pairing and request authentication |
| [Pydantic](https://docs.pydantic.dev) | | Schema validation for task plans and messages |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ORCHESTRATOR_AGENT_SEED` | `openclaw-orchestrator-dev-seed` | Seed for orchestrator agent identity |
| `ORCHESTRATOR_PORT` | `8200` | Orchestrator local server port |
| `CONNECTOR_AGENT_SEED` | `openclaw-connector-dev-seed` | Seed for connector agent identity |
| `CONNECTOR_PORT` | `8199` | Connector local server port |
| `CONNECTOR_USER_ID` | `u_dev` | User ID for pairing |
| `CONNECTOR_DEVICE_ID` | `dev_local` | Device ID for pairing |
| `ORCHESTRATOR_AGENT_ADDRESS` | *(none)* | Set to auto-pair connector on startup |
| `AGENT_NETWORK` | `testnet` | `testnet` or `mainnet` |
| `AGENTVERSE_API_KEY` | *(none)* | Agentverse API key for mailbox registration |
| `ASI_ONE_API_KEY` | *(none)* | ASI:One API key for LLM planning |
| `ASI_ONE_BASE_URL` | `https://api.asi1.ai/v1` | ASI:One API base URL |
| `ASI_ONE_MODEL` | `asi1` | ASI:One model name |
| `DEMO_PROJECTS_DIR` | `./demo_projects` | Safe demo directory for testing |
| `USE_MAILBOX` | `true` | Enable Agentverse mailbox relay |
| `MAX_REPO_SIZE_MB` | `500` | Max repo size for analyzer (MB) |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Roadmap

- [x] Weekly dev report workflow
- [x] GitHub repo health analyzer (public use case)
- [x] ASI:One LLM integration for intelligent planning
- [x] Agentverse mailbox for local agent reachability
- [ ] Security scanning (`pip-audit`, `bandit`, `npm audit`)
- [ ] Comparative analysis ("compare repo A vs repo B")
- [ ] Real Slack / email integration (replace `post_summary` stub)
- [ ] Scheduled monitoring ("alert me if score drops")
- [ ] Multi-device support (pair multiple machines to one account)
- [ ] PyPI package (`pip install fetch-openclaw`)

---

## License

MIT

---

*Built with [Fetch.ai uAgents](https://fetch.ai), [OpenClaw](https://openclaw.ai),
and [ASI:One](https://asi1.ai).*
