# Fetch.ai x OpenClaw: Secure Local Execution via Autonomous Agents

*A complete technical walkthrough of how we connected Fetch.ai's autonomous agent network with OpenClaw's local execution runtime to build AI workflows that actually run real tools on your machine, safely.*

**GitHub:** [cmaliwal/fetchai-openclaw-orchestrator](https://github.com/cmaliwal/fetchai-openclaw-orchestrator)
**Live Demo:** [View a Sample Chat on ASI:One](https://asi1.ai/chat/f7ccb160-88bc-46a0-bd44-041483eca338)

---

## Table of Contents

1. [The Problem](#the-problem)
2. [What We Built](#what-we-built)
3. [Why Both Technologies](#why-both-technologies)
4. [Architecture Overview](#architecture-overview)
5. [Step-by-Step: How It Works](#step-by-step-how-it-works)
6. [Code Walkthrough: Orchestrator Agent](#code-walkthrough-orchestrator-agent)
7. [Code Walkthrough: OpenClaw Connector](#code-walkthrough-openclaw-connector)
8. [Cryptographic Trust Layer](#cryptographic-trust-layer)
9. [Dual Policy Enforcement](#dual-policy-enforcement)
10. [Intelligent Planning with ASI:One LLM](#intelligent-planning-with-asione-llm)
11. [Workflow 1: GitHub Repo Health Analyzer](#workflow-1-github-repo-health-analyzer)
12. [Workflow 2: Weekly Dev Report](#workflow-2-weekly-dev-report)
13. [Feedback Loop Protection](#feedback-loop-protection)
14. [Complete End-to-End Data Flow](#complete-end-to-end-data-flow)
15. [Security Model](#security-model)
16. [What Each Technology Contributes](#what-each-technology-contributes)
17. [Try It Yourself](#try-it-yourself)
18. [What's Next](#whats-next)

---

## The Problem

Large Language Models can reason about objectives. Platforms like [ASI:One](https://asi1.ai) and [Agentverse](https://agentverse.ai) let users discover and talk to specialized AI agents. But when the task is **"analyze this GitHub repo and give me a health report"** or **"generate my weekly dev report from local git repos"**, those agents hit a wall.

They can *plan* the work. They can't *do* the work.

Real analysis requires running tools like `cloc`, `git log`, `pip-audit`, and reading actual files on a real filesystem. No matter how smart the LLM is, it cannot clone a repository, count lines of code, or inspect commit history. It would have to guess, and guessing is hallucinating.

The obvious fix: give the remote agent shell access to your machine. But that is a security nightmare. Cross-user misuse, uncontrolled command execution, leaked credentials. None of that is acceptable.

**The real question is:** how do you let an AI agent do real work on your machine without giving it the keys to the castle?

That is the problem we solved.

---

## What We Built

We built an integration between two technologies:

- **[Fetch.ai](https://fetch.ai)** provides the autonomous agent network: discovery, identity, messaging, planning, and a public chat interface ([ASI:One](https://asi1.ai)).
- **[OpenClaw](https://openclaw.ai)** provides the local execution runtime: verification, policy checking, sandboxed tool execution on your own machine.

The result: anyone on ASI:One can type a natural-language request and get back real results from real tools running on a real machine, with zero trust assumptions and full cryptographic verification.

To demonstrate this integration, we built two working workflows:

**1. GitHub Repo Health Analyzer (public, anyone can use):**
> *"Analyze https://github.com/fastapi/fastapi"*

Returns a scored health report with real line counts, git statistics, test detection, dependency audit, and best-practice checks.

**2. Weekly Dev Report (paired users):**
> *"Generate my weekly dev report"*

Scans local git repositories, gathers recent commit messages, and compiles a Markdown report.

These are not the product. They are **proof that the integration pattern works** for any workflow that requires real tool execution combined with public accessibility.

---

## Why Both Technologies

A common first question: why not just use one or the other?

### What Fetch.ai Brings

Fetch.ai provides the **agent infrastructure layer**:

| Capability | How It Works |
|---|---|
| **Agent Identity** | Deterministic Ed25519 keypairs via `uAgents`. Same seed = same address every time. |
| **Discovery** | Agents register on the Almanac (testnet/mainnet). Any agent on the network can find them. |
| **Messaging** | Standard agent-to-agent messaging with protocol-based routing. |
| **ASI:One** | A public chat interface where any user can talk to any registered agent in natural language. |
| **Agentverse** | Hosting, mailbox relay, manifest publishing. Your local agent becomes globally reachable. |
| **LLM Planning** | ASI:One's LLM API converts natural-language objectives into structured plans. |

Fetch agents can run arbitrary Python code. You can write any logic you want inside an agent. But Fetch's core strength is **communication, coordination, and discovery** across a decentralized network.

### What OpenClaw Brings

OpenClaw provides the **safe local execution layer**:

| Capability | How It Works |
|---|---|
| **Sandboxed Execution** | Tools run in temporary directories with controlled access. |
| **Policy Enforcement** | Action allowlists, path sandboxing, no background execution. |
| **Signature Verification** | Ed25519 verification on every inbound task plan. |
| **Declarative Task Plans** | No raw shell commands. Only named actions with validated parameters. |
| **Pipeline Chaining** | Step outputs feed into next step inputs automatically. |
| **Cleanup** | Temporary data is deleted after execution completes. |

### Why Together

| Scenario | Fetch Alone | OpenClaw Alone | Together |
|---|---|---|---|
| User asks "analyze this repo" on ASI:One | Agent receives the request but has no sandboxed execution runtime with policy checks | Nobody can reach it; it is a local tool | Request flows through Fetch to OpenClaw, executes safely, results return to ASI:One |
| You want your tool to be discoverable | Agent is on the network, anyone can find it | Invisible to external users | OpenClaw runs the tool; Fetch makes it discoverable |
| You need cryptographic request verification | Agent identity exists, but no execution-layer verification | Full Ed25519 verification, but no network reach | Both layers enforce independently |

**The key insight:** the agent that plans the work never touches the files. The service that executes the work never accepts raw commands. Neither can bypass the other's policies.

---

## Architecture Overview

Three components connect in a linear pipeline:

```
User --> ASI:One --> Orchestrator Agent (Agentverse) --> [signed task plan] --> OpenClaw Connector (local) --> Execution --> Results
```

| Component | Where It Runs | Technology | What It Does |
|---|---|---|---|
| **ASI:One** | Cloud (Fetch) | Chat interface + LLM | User sends a natural-language objective |
| **Orchestrator Agent** | Agentverse (mailbox relay) | `uagents` 0.23.6 | Plans the task, enforces Fetch-side policy, signs and dispatches |
| **OpenClaw Connector** | Your machine | `uagents` 0.23.6 + OpenClaw runtime | Verifies signature, enforces local policy, executes, returns results |

### Project Structure

```
openclaw-fetch/
|-- orchestrator/                 # Fetch Orchestrator Agent
|   |-- agent.py                  #   Agent construction + startup
|   |-- planner.py                #   Objective -> TaskPlan (LLM + keyword fallback)
|   |-- policy.py                 #   Fetch-side policy engine
|   |-- storage.py                #   In-memory device pairing store
|   +-- protocols/
|       |-- chat.py               #   AgentChatProtocol (ASI:One integration)
|       |-- objective.py          #   Objective intake + result routing
|       |-- pairing.py            #   Device pairing protocol
|       +-- models.py             #   uAgents message models
|
|-- connector/                    # OpenClaw Connector (local)
|   |-- server.py                 #   Agent construction + auto-pairing
|   |-- executor.py               #   Task plan execution engine
|   |-- auth.py                   #   Ed25519 signature verification
|   |-- policy.py                 #   Local policy engine
|   +-- workflows/
|       |-- repo_analyzer.py      #   clone_repo, analyze_repo, generate_health_report
|       +-- weekly_report.py      #   scan_directory, generate_report, post_summary
|
|-- shared/                       # Shared schemas and crypto
|   |-- schemas.py                #   Pydantic models (TaskPlan, TaskStep, etc.)
|   +-- crypto.py                 #   Ed25519 key management, signing, verification
|
|-- tests/                        #   68 unit tests (pytest)
|-- scripts/
|   |-- local_test.py             #   End-to-end local integration test
|   +-- setup_demo.py             #   Generate safe demo repos with fake git history
+-- pyproject.toml                #   Dependencies and project metadata
```

---

## Step-by-Step: How It Works

Here is the full journey from "user types a message" to "user gets results," explained for non-technical readers. Technical deep dives follow in later sections.

### 1. User Sends a Message
A user opens [ASI:One](https://asi1.ai) and types: *"Analyze https://github.com/fastapi/fastapi"*

### 2. ASI:One Finds the Agent
ASI:One looks up the agent on the Fetch network via the Almanac. It finds our orchestrator because we published its protocol manifest to Agentverse.

### 3. Message Arrives via Mailbox
The orchestrator runs on a local machine (no public IP). ASI:One delivers the message to the Agentverse mailbox. The local agent polls Agentverse and picks it up.

### 4. Orchestrator Plans the Task
The orchestrator's planner calls the ASI:One LLM to convert the natural-language message into a structured task plan: `clone_repo -> analyze_repo -> generate_health_report`.

### 5. Policy Check (Fetch-side)
Before dispatching, the orchestrator checks: Are these actions allowed? Has the user exceeded rate limits? Is the plan within the maximum step count?

### 6. Sign and Dispatch
The orchestrator serializes the task plan as JSON, signs it with Ed25519, and sends it to the paired OpenClaw Connector.

### 7. Connector Verifies and Executes
The connector verifies the Ed25519 signature (is this really from my orchestrator?), checks local policies (are these actions allowed on my machine?), then executes the plan step by step.

### 8. Results Return
Results flow back: Connector -> Orchestrator -> ASI:One -> User. The user sees a health report with real numbers.

**The entire round trip happens in under 60 seconds for most repos.**

---

## Code Walkthrough: Orchestrator Agent

### Creating the Agent

The orchestrator is a standard [uAgent](https://github.com/fetchai/uAgents) built with `uagents==0.23.6`:

```python
# orchestrator/agent.py
from uagents import Agent

agent = Agent(
    name="openclaw-orchestrator",
    seed="openclaw-orchestrator-dev-seed",   # deterministic Ed25519 identity
    port=8200,
    mailbox=True,                            # enable Agentverse mailbox relay
    network="testnet",                       # register on Fetch testnet Almanac
)
```

Key points:
- **`seed`**: Generates a deterministic Ed25519 keypair. Same seed produces the same agent address (`agent1q...`) every time. In production, use a secure random seed stored in secrets.
- **`mailbox=True`**: The agent registers with Agentverse's mailbox relay instead of exposing a public endpoint. No ngrok, no port forwarding, no public IP.
- **`network="testnet"`**: Registers the agent on the Fetch testnet Almanac, making it discoverable by other agents and ASI:One.

### Registering Protocols

The agent includes three protocols, each published to Agentverse:

```python
# orchestrator/agent.py
from orchestrator.protocols.chat import chat_proto
from orchestrator.protocols.objective import objective_protocol
from orchestrator.protocols.pairing import pairing_protocol

agent.include(chat_proto, publish_manifest=True)       # ASI:One integration
agent.include(pairing_protocol, publish_manifest=True)  # device registration
agent.include(objective_protocol, publish_manifest=True) # task dispatch + results
```

Setting `publish_manifest=True` publishes each protocol's manifest to Agentverse. This is what makes ASI:One recognize and list the agent. Without it, ASI:One cannot discover or communicate with the agent.

### The Chat Protocol (ASI:One Integration)

This is the most important protocol. It implements the standard [AgentChatProtocol](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents) so ASI:One can send messages to the agent:

```python
# orchestrator/protocols/chat.py
from uagents import Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement,
    TextContent, StartSessionContent,
    chat_protocol_spec,
)

# Create the protocol from the official spec
chat_proto = Protocol(spec=chat_protocol_spec)

@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx, sender, msg):
    # 1. Acknowledge receipt immediately (required by the protocol)
    await ctx.send(sender, ChatAcknowledgement(
        acknowledged_msg_id=msg.msg_id,
        timestamp=datetime.now(timezone.utc),
    ))

    # 2. Extract the user's text
    for content in msg.content:
        if isinstance(content, StartSessionContent):
            return  # session start, nothing to process
        elif isinstance(content, TextContent):
            objective_text = content.text

    # 3. Clean the message (strip @agent... prefix from ASI:One)
    objective_text = _clean_objective(objective_text)

    # 4. Feedback loop detection (see dedicated section below)
    if _looks_like_echo(objective_text):
        return  # silently ignore echoes

    # 5. Plan, policy-check, sign, dispatch
    plan = plan_objective(objective_text)
    # ... (dispatch to connector, await results)
```

The `ChatMessage` model supports multiple content types (`TextContent`, `StartSessionContent`, etc.). We handle text objectives and gracefully ignore others.

### Custom Protocol: Device Pairing

Before the connector can receive tasks, it must register with the orchestrator. This is handled by a custom protocol:

```python
# orchestrator/protocols/models.py
from uagents import Model

class PairDeviceRequest(Model):
    user_id: str
    device_id: str
    public_key_hex: str       # Ed25519 public key (64-char hex string)
    capabilities: list[str]   # e.g. ["weekly_report", "repo_analyzer"]

class PairDeviceResponse(Model):
    user_id: str
    device_id: str
    status: str               # "paired" or "rejected"
    message: str = ""
```

```python
# orchestrator/protocols/pairing.py
from uagents import Protocol

pairing_protocol = Protocol(name="device-pairing", version="0.1.0")

@pairing_protocol.on_message(PairDeviceRequest, replies={PairDeviceResponse})
async def handle_pairing(ctx, sender, msg):
    # Validate the Ed25519 public key (must be 64-char hex)
    if not msg.public_key_hex or len(msg.public_key_hex) != 64:
        await ctx.send(sender, PairDeviceResponse(
            user_id=msg.user_id, device_id=msg.device_id,
            status="rejected",
            message="Invalid public key (expected 64-char hex Ed25519 key).",
        ))
        return

    # Store the pairing record
    pairing_store.pair(msg.user_id, msg.device_id, msg.public_key_hex,
                       capabilities=msg.capabilities)

    # Remember the connector's agent address for future dispatching
    ctx.storage.set(f"connector:{msg.user_id}:{msg.device_id}", sender)

    await ctx.send(sender, PairDeviceResponse(
        user_id=msg.user_id, device_id=msg.device_id,
        status="paired", message="Device paired successfully.",
    ))
```

The `ctx.storage.set(...)` call persists the connector's agent address. When a task needs dispatching later, the orchestrator looks up this address to know where to send it.

### Custom Protocol: Task Dispatch

After planning, the orchestrator dispatches signed task plans:

```python
# orchestrator/protocols/models.py
class TaskDispatchRequest(Model):
    user_id: str
    device_id: str
    task_plan_json: str   # JSON-encoded TaskPlan (Pydantic model)
    signature: str        # hex-encoded Ed25519 signature over the plan

class TaskExecutionResult(Model):
    task_id: str
    status: str           # "completed" | "failed" | "rejected" | "partial"
    step_results_json: str = "[]"
    outputs: dict[str, Any] = {}
    reason: str = ""
```

### Async Result Correlation

Because tasks execute asynchronously, the orchestrator tracks which ASI:One sender initiated each task:

```python
# When dispatching (in chat handler):
pending_dict[plan.task_id] = {"sender": sender, "objective": objective_text}
ctx.storage.set("chat_pending", json.dumps(pending_dict))

# When results arrive (in objective protocol):
chat_meta = chat_dict.pop(msg.task_id, None)
if chat_meta:
    # Route results back to the correct ASI:One session
    await send_chat_reply(ctx, chat_meta["sender"], formatted_result)
```

This lets the orchestrator handle multiple concurrent requests from different users and route each result back to the correct conversation.

---

## Code Walkthrough: OpenClaw Connector

### Creating the Connector Agent

The connector also uses `uagents`, but runs locally without a mailbox:

```python
# connector/server.py
from uagents import Agent

connector_agent = Agent(
    name="openclaw-connector",
    seed="openclaw-connector-dev-seed",
    port=8199,
    endpoint=["http://127.0.0.1:8199/submit"],  # local only
    network="testnet",
)
```

### Auto-Pairing on Startup

When the connector starts, it automatically registers with the orchestrator:

```python
# connector/server.py
@connector_agent.on_event("startup")
async def on_startup(ctx):
    if _ORCHESTRATOR_ADDRESS:
        await ctx.send(_ORCHESTRATOR_ADDRESS, PairDeviceRequest(
            user_id=_USER_ID,
            device_id=_DEVICE_ID,
            public_key_hex=DEVICE_PUBLIC_KEY_HEX,  # Ed25519 public key
            capabilities=["weekly_report", "repo_analyzer"],
        ))
```

The `DEVICE_PUBLIC_KEY_HEX` is generated on first run using the `cryptography` library:

```python
# connector/server.py (keypair generation)
from shared.crypto import generate_keypair, save_keypair, load_keypair

KEY_DIR = Path("./keys")

if (KEY_DIR / "private.hex").exists():
    _private_key, _public_key = load_keypair(KEY_DIR)
else:
    _private_key, _public_key = generate_keypair()
    save_keypair(KEY_DIR, _private_key)
```

### The Core Handler: Verify, Check Policy, Execute

Every inbound task follows a strict pipeline:

```python
# connector/server.py
@connector_agent.on_message(TaskDispatchRequest, replies={TaskExecutionResult})
async def handle_task_dispatch(ctx, sender, msg):
    # 1. Verify ownership (user_id + device_id match this connector)
    if msg.user_id != _USER_ID or msg.device_id != _DEVICE_ID:
        return reject("device_not_paired")

    # 2. Verify Ed25519 signature
    ok, reason = authenticator.verify_dispatch(msg.task_plan_json, msg.signature)
    if not ok:
        return reject("invalid_signature")

    # 3. Deserialize the task plan (Pydantic validation)
    plan = TaskPlan.model_validate_json(msg.task_plan_json)

    # 4. Local policy check (action allowlist + path sandbox)
    rejection = local_policy.validate_plan(plan)
    if rejection is not None:
        return reject(rejection)

    # 5. Execute the plan
    result = execute_plan(plan)

    # 6. Return results to the orchestrator
    await ctx.send(sender, TaskExecutionResult(
        task_id=result.task_id,
        status=result.status.value,
        step_results_json=json.dumps([sr.model_dump(mode="json") for sr in result.step_results]),
        outputs=result.outputs,
    ))
```

### The Executor: Pipeline-Based Step Execution

The executor runs each step sequentially and chains outputs:

```python
# connector/executor.py
_ACTIONS = {
    "scan_directory":         scan_directory,
    "generate_report":        generate_report,
    "post_summary":           post_summary,
    "clone_repo":             clone_repo,
    "analyze_repo":           analyze_repo,
    "generate_health_report": generate_health_report,
    "summarise_text":         _summarise_text,
}

def execute_plan(plan: TaskPlan) -> ExecutionResult:
    previous_output = None
    for step in plan.steps:
        handler = _ACTIONS[step.action]

        # Pipeline chaining: if the handler accepts 2 args,
        # pass the previous step's output
        sig = inspect.signature(handler)
        if len(sig.parameters) >= 2:
            output = handler(step.params, previous_output)
        else:
            output = handler(step.params)

        previous_output = output
    return ExecutionResult(task_id=plan.task_id, ...)
```

This pipeline chaining is critical. For the repo analyzer:
- `clone_repo` returns `{"clone_path": "/tmp/repo_analysis_xxx/repo", ...}`
- `analyze_repo` receives that as `clone_output` and reads files from that path
- `generate_health_report` receives the analysis data and compiles the report

---

## Cryptographic Trust Layer

Every task dispatch is cryptographically signed. This is not optional decoration; it is the foundation of the trust model.

### How Signing Works

```python
# shared/crypto.py
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import json

def sign_payload(private_key: Ed25519PrivateKey, payload: dict) -> str:
    """Sign a JSON-serializable dict; return hex-encoded signature."""
    canonical = json.dumps(payload, sort_keys=True, default=str).encode()
    sig = private_key.sign(canonical)
    return sig.hex()
```

The `sort_keys=True` ensures deterministic JSON serialization. The same payload always produces the same byte string, which means the same signature can be reproduced and verified independently.

### How Verification Works

```python
# shared/crypto.py
def verify_signature(public_key_hex: str, payload: dict, signature_hex: str) -> bool:
    """Verify an Ed25519 signature over a canonical JSON payload."""
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        canonical = json.dumps(payload, sort_keys=True, default=str).encode()
        pub.verify(bytes.fromhex(signature_hex), canonical)
        return True
    except Exception:
        return False
```

### What This Prevents

If someone intercepts the task plan and modifies it (e.g., changing `clone_repo` params to point to a malicious URL, or injecting an extra step), the signature verification fails and the connector rejects the entire request. The plan is **immutable** once signed.

### Key Management

```python
# shared/crypto.py
def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()

def save_keypair(directory: Path, private_key: Ed25519PrivateKey) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "private.hex").write_text(private_key_to_hex(private_key))
    (directory / "public.hex").write_text(public_key_to_hex(private_key.public_key()))
    return directory
```

Keys are stored as raw hex strings in the `./keys/` directory. In production, these would go into a hardware security module or secrets manager.

---

## Dual Policy Enforcement

Policies are checked at two independent layers. This is intentional: neither layer trusts the other.

### Fetch-side Policy (Orchestrator)

Checked **before** the task plan is dispatched:

```python
# orchestrator/policy.py
@dataclass
class FetchPolicy:
    allowed_actions: set[str] = {
        "scan_directory", "generate_report", "summarise_text",
        "post_summary", "clone_repo", "analyze_repo",
        "generate_health_report",
    }
    rate_limit_per_minute: int = 10
    max_steps_per_plan: int = 20

    def validate(self, user_id: str, plan: TaskPlan) -> RejectionReason | None:
        # 1. Rate limit (sliding window, 60 seconds)
        if requests_in_last_minute(user_id) >= self.rate_limit_per_minute:
            return RejectionReason.QUOTA_EXCEEDED

        # 2. Step count
        if len(plan.steps) > self.max_steps_per_plan:
            return RejectionReason.POLICY_VIOLATION

        # 3. Action allowlist
        for step in plan.steps:
            if step.action not in self.allowed_actions:
                return RejectionReason.ACTION_NOT_ALLOWED

        return None  # all checks passed
```

### Local Policy (Connector)

Checked **before** execution, independently of the orchestrator:

```python
# connector/policy.py
@dataclass
class LocalPolicy:
    allowed_actions: set[str] = {
        "scan_directory", "generate_report", "summarise_text",
        "post_summary", "clone_repo", "analyze_repo",
        "generate_health_report",
    }
    allowed_paths: list[str] = [
        "~/projects", "~/Documents", "/tmp",
        "./demo_projects",  # safe testing directory
    ]
    require_user_confirmation: bool = True
    allow_background_execution: bool = False

    def validate_plan(self, plan: TaskPlan) -> RejectionReason | None:
        for step in plan.steps:
            # Check action is in local allowlist
            if step.action not in self.allowed_actions:
                return RejectionReason.ACTION_NOT_ALLOWED

            # Check path is within sandbox
            raw_path = step.params.get("path")
            if raw_path and not is_within_allowed_paths(raw_path):
                return RejectionReason.PATH_NOT_ALLOWED

        return None  # all checks passed
```

### Why Two Layers?

The orchestrator cannot bypass the connector's policies. Even if the orchestrator is compromised and sends a malicious plan, the connector independently validates every action and every path. **Your machine always has the final say.**

---

## Intelligent Planning with ASI:One LLM

The planner converts natural-language objectives into structured `TaskPlan` objects. It uses a two-tier strategy:

### Tier 1: LLM Planning (ASI:One API)

When `ASI_ONE_API_KEY` is configured, the planner calls the ASI:One LLM through an OpenAI-compatible API:

```python
# orchestrator/planner.py
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("ASI_ONE_API_KEY"),
    base_url="https://api.asi1.ai/v1",  # ASI:One endpoint
)

response = client.chat.completions.create(
    model="asi1",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Analyze https://github.com/fastapi/fastapi"},
    ],
    temperature=0.1,   # low temperature for deterministic planning
    max_tokens=512,
)
```

The system prompt tells the LLM exactly which actions are available and what parameters they accept:

```python
SYSTEM_PROMPT = """
You are a task planner for the OpenClaw execution system.
Given a user objective, produce a JSON task plan.

Available LOCAL actions:
  WEEKLY REPORT WORKFLOW:
  - scan_directory: params {"path": "./demo_projects"}
  - generate_report: params {"format": "markdown"}
  - summarise_text: params {"text": "<text>"}

  GITHUB REPO HEALTH ANALYZER:
  - clone_repo: params {"url": "<github_https_url>"}
  - analyze_repo: params {}
  - generate_health_report: params {}

Available EXTERNAL actions:
  - post_summary: params {"target": "slack"|"email"}

Rules:
  - ONLY output valid JSON, no explanation or markdown.
  - For GitHub repo analysis: use clone_repo -> analyze_repo -> generate_health_report.
  - The URL must be a public GitHub HTTPS URL.
  - Always set no_delete: true and require_user_confirmation: true.
"""
```

The LLM returns structured JSON:

```json
{
  "steps": [
    {"type": "local", "action": "clone_repo", "params": {"url": "https://github.com/fastapi/fastapi"}},
    {"type": "local", "action": "analyze_repo", "params": {}},
    {"type": "local", "action": "generate_health_report", "params": {}}
  ],
  "constraints": {"no_delete": true, "require_user_confirmation": true}
}
```

### Tier 2: Keyword Fallback (No LLM Required)

If the LLM is unavailable (API key missing, network error, timeout), the planner falls back to regex-based keyword matching:

```python
# orchestrator/planner.py
_GITHUB_URL_RE = re.compile(r"https://github\.com/[\w.\-]+/[\w.\-]+")
_REPORT_KEYWORDS = re.compile(r"\b(report|summary|weekly|daily)\b", re.I)

def _plan_with_keywords(objective: str) -> TaskPlan:
    github_url = _GITHUB_URL_RE.search(objective)
    if github_url:
        return TaskPlan(steps=[
            TaskStep(action="clone_repo", params={"url": github_url.group(0)}),
            TaskStep(action="analyze_repo", params={}),
            TaskStep(action="generate_health_report", params={}),
        ])

    if _REPORT_KEYWORDS.search(objective):
        return TaskPlan(steps=[
            TaskStep(action="scan_directory", params={"path": "./demo_projects"}),
            TaskStep(action="generate_report", params={"format": "pdf"}),
        ])

    # ... more patterns
```

**The system always works.** It just plans more intelligently when the LLM is available.

---

## Workflow 1: GitHub Repo Health Analyzer

This is the public-facing workflow. Anyone on ASI:One can use it. No pairing required.

### What It Does

Three sequential steps:

**Step 1: `clone_repo`**
- Accepts only public GitHub HTTPS URLs (SSH and non-GitHub URLs are rejected)
- Shallow clone (`git clone --depth 1`) into a temporary directory
- Enforces a 500 MB size limit
- Fetches full git history (`git fetch --unshallow`) for accurate statistics

```python
# connector/workflows/repo_analyzer.py
def clone_repo(params):
    url = params.get("url", "").strip()

    # Security: only HTTPS GitHub URLs
    if not re.match(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$", url):
        return {"error": "Only public GitHub HTTPS URLs accepted."}

    tmpdir = tempfile.mkdtemp(prefix="repo_analysis_")
    subprocess.run(["git", "clone", "--depth", "1", url, f"{tmpdir}/repo"], timeout=120)

    # Size check
    if dir_size_mb(f"{tmpdir}/repo") > 500:
        shutil.rmtree(tmpdir)
        return {"error": "Repository too large."}

    # Fetch full history for stats
    subprocess.run(["git", "-C", f"{tmpdir}/repo", "fetch", "--unshallow"], timeout=120)

    return {"clone_path": f"{tmpdir}/repo", "tmpdir": tmpdir, "url": url}
```

**Step 2: `analyze_repo`**

Runs six categories of static analysis (NO code from the repo is ever executed):

```python
def analyze_repo(params, clone_output):
    repo_path = clone_output["clone_path"]

    # 1. Language breakdown (cloc if available, else extension-based counting)
    languages = _count_lines_by_language(repo_path)

    # 2. Git statistics
    git_stats = _git_stats(repo_path)   # commits, contributors, recent activity

    # 3. Test detection
    tests = _detect_tests(repo_path)    # frameworks, test file count

    # 4. Dependency audit
    deps = _check_dependencies(repo_path)  # requirements.txt, package.json, etc.

    # 5. Security and best practices
    security = _check_security_files(repo_path)  # LICENSE, README, CI/CD, .gitignore

    # 6. Health score (0-10)
    health_score = _compute_health_score(languages, git_stats, tests, deps, security)

    return {"languages": languages, "git": git_stats, "tests": tests,
            "dependencies": deps, "security": security, "health_score": health_score}
```

The health score is computed from multiple weighted factors:

```python
def _compute_health_score(languages, git_stats, tests, deps, security):
    score = 5.0  # Start at middle

    if tests["test_files"] > 0:    score += 1.0    # Has tests
    if tests["test_files"] > 10:   score += 0.5    # Many tests
    if security["has_ci"]:         score += 1.0    # CI/CD pipeline
    if security["has_license"]:    score += 0.5    # License
    if security["has_readme"]:     score += 0.5    # README
    if security["has_gitignore"]:  score += 0.25   # .gitignore
    if git_stats["commits_last_30_days"] > 5:  score += 0.5  # Active
    if git_stats["commits_last_30_days"] > 20: score += 0.5  # Very active
    if git_stats["total_contributors"] > 2:    score += 0.5  # Community

    if len(security["findings"]) > 0:  score -= 0.5  # Security findings
    if tests["test_files"] == 0:       score -= 1.5  # No tests

    return max(0.0, min(10.0, round(score, 1)))
```

**Step 3: `generate_health_report`**
- Compiles all data into a formatted Markdown report
- Assigns a letter grade (A: 8+, B: 6+, C: 4+, D: below 4)
- Cleans up the temporary clone directory

### Sample Output

```
# Repo Health Report: fastapi/fastapi
**URL**: https://github.com/fastapi/fastapi
**Health Score**: 8.7/10 (Grade: A)

## Languages
- **Python**: 82.3% (48,200 lines)
- **Markdown**: 12.1% (7,100 lines)

## Git Activity
- **Total Commits**: 3,456
- **Commits (last 30 days)**: 124
- **Contributors**: 485

## Testing
- **Test Files Found**: 340
- **Frameworks Detected**: pytest

## Best Practices
- **README**: pass
- **LICENSE**: pass
- **CI/CD Pipeline**: pass
- **SECURITY.md**: pass
```

### Why an LLM Cannot Do This

ChatGPT cannot `git clone` a repository. It cannot run `cloc` to count lines of code. It cannot execute `git log --since="30 days ago"` to check recent commit history. It would have to **guess the numbers**, and guessing is hallucinating. Our agent runs the actual tools and returns real data.

### Why It Is Safe

The repo is cloned into `/tmp/repo_analysis_xxx/`. No code from the repo is ever executed, imported, or installed. Files are read as text. If someone points to a repo full of malware, the agent just reports its health score and moves on. The temp directory is deleted after.

---

## Workflow 2: Weekly Dev Report

This workflow scans local git repositories and compiles a development report.

### Three Steps

**`scan_directory`**: Walks a directory tree, finds git repos, gathers commit messages from the last 7 days.

```python
def scan_directory(params):
    root = Path(params.get("path", "./demo_projects")).resolve()
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    repos = []
    for candidate in root.iterdir():
        if (candidate / ".git").is_dir():
            result = subprocess.run(
                ["git", "-C", str(candidate), "log", f"--since={since}", "--oneline"],
                capture_output=True, text=True, timeout=10,
            )
            commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            repos.append({"repo": candidate.name, "commits": commits})

    return {"root": str(root), "repos": repos, "since": since}
```

**`generate_report`**: Compiles scan results into a Markdown report. Writes the file to disk.

**`post_summary`**: (Stub) Prepares the summary for Slack or email delivery. Returns a message indicating the integration is not yet configured.

### Sample Output

```
# Weekly Dev Report
**Period**: 2026-02-16 -> 2026-02-23

## weather-agent
  - abc1234 Add temperature caching
  - def5678 Fix API timeout handling

## marketplace-ui
  - 111aaa2 Update product grid layout
  - 333bbb4 Add pagination component

## data-pipeline
  _No commits this week._
```

---

## Feedback Loop Protection

When integrating with ASI:One, a real-world challenge emerges: **ASI:One's LLM sometimes rewrites agent responses and sends them back as new objectives**, creating an infinite feedback loop.

For example:
1. Agent sends: "Task dispatched, standing by for results"
2. ASI:One rewrites it as: "Report mode activated! Gen + Post: mission running!"
3. Agent receives this as a new objective
4. Repeat forever

We solved this with five layers of protection:

```python
# orchestrator/protocols/chat.py

# Layer 1: Command-verb fast-path
# If the message starts with a command verb, it is ALWAYS genuine
_COMMAND_VERBS_RE = re.compile(
    r"^(generate|analyze|review|audit|check|scan|clone|build|run|"
    r"test|summarize|compare|find|list|tell|explain|help|what|how|can)\b", re.I)

# Layer 2: GitHub URL fast-path
# If the message contains a GitHub URL, it is ALWAYS genuine
_GITHUB_URL_RE = re.compile(r"https?://github\.com/", re.I)

# Layer 3: Echo pattern detection (100+ known patterns)
_ECHO_PATTERNS = [
    "task dispatched", "mission running", "report mode activated",
    "standing by!", "pipeline running", "gen + post", "mission complete!",
    "weekly dev intel", "repos scanned", "intel compiling", ...
]

# Layer 4: Emoji density check (ASI:One adds emoji to rewrites)
if len(emoji_re.findall(text)) >= 3:
    return True  # likely an echo

# Layer 5: Genuine objective keyword check
# If the message has NO genuine keywords (generate, analyze, repo, etc.)
# it is probably an echo
_GENUINE_OBJECTIVE_KEYWORDS = re.compile(
    r"\b(generate|weekly|report|analyze|review|audit|health|"
    r"check|github\.com|repo|clone|scan|hello|help)\b", re.I)
```

**On top of pattern detection, we also enforce:**

- **Per-sender cooldown**: 30 seconds minimum between objectives from the same sender
- **Exact dedup**: MD5 hash of the text, ignore duplicates within a 120-second window
- **Pending task cap**: Maximum 5 concurrent tasks; stale entries are pruned

**The most important design decision**: do not send intermediate status messages. Instead of saying "Your task has been dispatched, please wait...", the agent stays silent until the final result arrives. This eliminates the primary trigger for ASI:One's echo behavior. The user receives exactly one message: the completed result.

---

## Complete End-to-End Data Flow

Here is every step that happens when you type "Analyze https://github.com/fastapi/fastapi" in ASI:One:

```
 1. User types the message in ASI:One (asi1.ai)
 2. ASI:One sends a ChatMessage to the agent's Almanac-registered address
 3. Agentverse mailbox holds the message
 4. Local orchestrator polls Agentverse, receives the ChatMessage
 5. Chat handler acknowledges receipt (ChatAcknowledgement)
 6. Chat handler strips @agent... prefix, runs feedback loop detection:
      - Command-verb check (starts with "Analyze") -> genuine request
      - Echo pattern check -> not an echo
      - Sender cooldown check -> OK
      - Dedup check -> first time seeing this text
 7. Planner calls ASI:One LLM API (POST https://api.asi1.ai/v1/chat/completions)
      - System prompt lists available actions
      - LLM returns JSON: [clone_repo, analyze_repo, generate_health_report]
 8. TaskPlan created with Pydantic validation:
      - task_id: "task_a1b2c3d4e5f6"
      - 3 steps, constraints (no_delete=true, require_user_confirmation=true)
 9. Fetch-side policy validates:
      - Rate limit: under 10/minute -> OK
      - Step count: 3 < 20 -> OK
      - Actions: all in allowlist -> OK
10. Plan serialized as canonical JSON (sort_keys=True)
11. Orchestrator signs the JSON with Ed25519 private key
12. TaskDispatchRequest sent to paired connector's agent address
13. Connector receives TaskDispatchRequest
14. Connector verifies Ed25519 signature against orchestrator's public key
15. Connector checks local policy:
      - Actions: clone_repo, analyze_repo, generate_health_report -> all in allowlist
16. Executor runs step 1: clone_repo
      - Validates URL is GitHub HTTPS
      - Creates /tmp/repo_analysis_xxx/
      - git clone --depth 1 https://github.com/fastapi/fastapi.git
      - Checks size < 500 MB
      - git fetch --unshallow (for full history)
17. Executor runs step 2: analyze_repo (receives clone_output)
      - Counts lines by language (cloc or extension-based)
      - Gathers git stats (git rev-list --count, git shortlog, git log)
      - Detects test frameworks (pytest, jest, etc.)
      - Parses dependency files (requirements.txt, package.json)
      - Checks best practices (README, LICENSE, CI/CD, .gitignore, SECURITY.md)
      - Computes health score (0-10, weighted formula)
18. Executor runs step 3: generate_health_report (receives analysis_output)
      - Compiles Markdown report with score, grade, all sections
      - Deletes temporary directory
19. TaskExecutionResult sent back to orchestrator with full outputs
20. Orchestrator correlates result with pending task (by task_id)
21. Orchestrator extracts report_text from outputs
22. Orchestrator sends ChatMessage with the report back to ASI:One
23. User sees the health report in their chat (no intermediate messages)
```

**See a real conversation:** [View Sample Chat on ASI:One](https://asi1.ai/chat/f7ccb160-88bc-46a0-bd44-041483eca338)

---

## Security Model

| Layer | What It Checks | Where | Code |
|---|---|---|---|
| **URL Validation** | Only public GitHub HTTPS URLs accepted | Connector | `repo_analyzer.py` |
| **Sandbox Execution** | Temp directory, no code execution, auto-cleanup | Connector | `repo_analyzer.py` |
| **Size Limits** | Repos over 500 MB rejected | Connector | `repo_analyzer.py` |
| **Device Pairing** | Ed25519 public key registration | Orchestrator | `pairing.py` |
| **Request Signing** | Ed25519 signature on every task dispatch | Both | `crypto.py` |
| **Signature Verification** | Connector verifies before executing | Connector | `auth.py` |
| **Fetch-side Policy** | Rate limits (10/min), max steps (20), action allowlist | Orchestrator | `orchestrator/policy.py` |
| **Local Policy** | Path sandbox, action allowlist, no background execution | Connector | `connector/policy.py` |
| **Declarative Plans** | No shell commands; only named actions with parameters | Both | `schemas.py` |
| **Feedback Loop Protection** | Echo detection, cooldown (30s), dedup (120s), pending cap (5) | Orchestrator | `chat.py` |
| **No Intermediate Messages** | Silent until final result (prevents ASI:One echo trigger) | Orchestrator | `chat.py` |

**Key principle:** The agent that plans never touches the files. The service that executes never accepts raw commands. Neither can bypass the other's policies.

---

## What Each Technology Contributes

### Full Technology Stack

| Technology | Version | Role |
|---|---|---|
| [uAgents](https://github.com/fetchai/uAgents) | `0.23.6` | Agent framework: identity (Ed25519), messaging, protocols, lifecycle |
| [uAgents-core](https://pypi.org/project/uagents-core/) | `0.4.1` | Core protocol specs including `AgentChatProtocol` |
| [Agentverse](https://agentverse.ai) | cloud | Agent hosting, discovery, mailbox relay, manifest publishing |
| [ASI:One Chat](https://asi1.ai) | cloud | User-facing chat interface for talking to agents |
| [ASI:One LLM](https://docs.asi1.ai) | model: `asi1` | OpenAI-compatible API for intelligent planning |
| [AgentChatProtocol](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents) | `0.3.0` | Standard protocol for ASI:One discoverability |
| [Almanac](https://docs.agentverse.ai) | testnet | Agent registration and discovery on the Fetch network |
| [Pydantic](https://docs.pydantic.dev) | `>=2.0` | Schema validation for task plans, messages, device records |
| [cryptography](https://cryptography.io) | `>=42.0` | Ed25519 key generation, signing, verification |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | `>=1.0` | Client for ASI:One LLM API (OpenAI-compatible interface) |

### The Pydantic Data Models

All data flowing through the system is validated with Pydantic:

```python
# shared/schemas.py
class TaskStep(BaseModel):
    type: StepType          # "local" or "external"
    action: str             # e.g. "clone_repo", "analyze_repo"
    params: dict[str, Any]  # action-specific parameters

class TaskPlan(BaseModel):
    task_id: str            # auto-generated: "task_a1b2c3d4e5f6"
    steps: list[TaskStep]
    constraints: TaskConstraints  # no_delete, require_user_confirmation, max_duration
    created_at: datetime

class ExecutionResult(BaseModel):
    task_id: str
    status: TaskStatus      # completed | failed | rejected | partial
    step_results: list[StepResult]
    outputs: dict[str, Any]
    reason: RejectionReason | None
    completed_at: datetime
```

### What Would Be Missing Without Each Piece

| Without... | You Lose... |
|---|---|
| **Fetch/Agentverse** | Nobody can discover or reach your tool. It runs locally and stays invisible. |
| **ASI:One** | Users need to learn your API or CLI. No natural-language interface. |
| **ASI:One LLM** | Planning falls back to keyword matching. Less intelligent, but still works. |
| **OpenClaw** | The agent can plan tasks but cannot execute them. No real tool output. |
| **Ed25519 signing** | No proof that a task plan came from the orchestrator. Tampered plans could execute. |
| **Dual policies** | Either side could force the other into unwanted actions. |
| **Pydantic** | No schema validation. Malformed data could crash the system. |

---

## Try It Yourself

**GitHub Repo:** [cmaliwal/fetchai-openclaw-orchestrator](https://github.com/cmaliwal/fetchai-openclaw-orchestrator)

### Prerequisites

- Python 3.10+
- A [Fetch Agentverse](https://agentverse.ai) account and API key
- An [ASI:One](https://asi1.ai) API key (optional, for LLM planning)
- Git installed (for the repo analyzer workflow)

### Install and Run

```bash
# Clone and install
git clone https://github.com/cmaliwal/fetchai-openclaw-orchestrator.git
cd fetchai-openclaw-orchestrator
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env and add: AGENTVERSE_API_KEY, ASI_ONE_API_KEY

# Set up demo data (safe fake repos for weekly report testing)
python scripts/setup_demo.py

# Terminal 1: Start the Orchestrator
python -m orchestrator.agent

# Terminal 2: Start the Connector (auto-pairs with orchestrator)
ORCHESTRATOR_AGENT_ADDRESS=<address-from-terminal-1> python -m connector.server
```

### Register the Agentverse Mailbox

With the orchestrator running, register its mailbox so ASI:One can reach it:

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

Expected output: `{'success': True, 'detail': None}`

### Test from ASI:One

Go to [ASI:One](https://asi1.ai) and try:

```
Analyze https://github.com/fastapi/fastapi
```
```
Check the health of https://github.com/pallets/flask
```
```
Generate my weekly dev report
```
```
Scan my projects and create a summary, then post to Slack
```

### Run the Test Suite

```bash
pytest          # all 68 tests
pytest -v       # verbose output
pytest --cov    # with coverage report
```

### End-to-End Local Test (No Agents Required)

```bash
python scripts/local_test.py
```

This simulates the full flow (pair, plan, dispatch, execute, result) in a single process without running the actual agents.

---

## What's Next

- **Security scanning**: Integrate `pip-audit`, `bandit`, `npm audit` for vulnerability detection
- **Comparative analysis**: "Compare repo A vs repo B" in a single request
- **Scheduled monitoring**: "Check this repo every week and alert me if the score drops"
- **Multi-agent composition**: One agent clones, another analyzes, another reports
- **Real Slack/email integration**: Replace the `post_summary` stub with actual API calls
- **Multi-device support**: Pair multiple machines to one account
- **PyPI package**: `pip install fetch-openclaw` for easy integration

---

## The Bigger Picture

This is not just a repo analyzer or a weekly report tool. It is a **reference architecture** for safe remote-to-local AI orchestration.

The pattern: a Fetch agent handles discovery, communication, and planning. OpenClaw handles verification, policy enforcement, and execution. The user never has to choose between AI capability and data safety.

Any Fetch agent can coordinate local work (code analysis, file processing, system administration, data pipelines, infrastructure health checks, document processing) through the same design: plan remotely, verify cryptographically, execute locally.

The user stays in control. The agent stays useful. And neither has to trust the other blindly.

---

*Built with [Fetch.ai uAgents](https://fetch.ai), [OpenClaw](https://openclaw.ai), and [ASI:One](https://asi1.ai).*
