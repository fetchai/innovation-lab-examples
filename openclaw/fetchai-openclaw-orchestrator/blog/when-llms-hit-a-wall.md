# OpenClaw x Fetch.ai: Where Autonomous Agents Meet Safe Local Execution

*Fetch.ai agents can reach anyone and plan anything. OpenClaw can execute real tools safely on local machines. Neither is complete alone. Here's what we built by connecting the two.*

---

## The problem: execution is still the hard part

AI agents are getting smarter every month. They can plan multi-step workflows, call APIs, generate code, and hold complex conversations. But there's one thing that's still surprisingly hard: getting an agent to safely run real tools on a real machine.

Think about it. You want an AI agent to clone a GitHub repo, run `cloc` to count lines of code, check `git log` for commit history, scan for security issues, and give you a health report. That requires actual execution: processes running, files being read, commands producing output.

Most agent platforms solve this by either running everything in a remote sandbox (limited, no access to your data) or giving the agent shell access to a server (powerful, but a security nightmare). Neither is great.

What if there was a way to let AI agents trigger real execution on local machines, without giving up control, without exposing your system, and without trusting the agent blindly?

That's what we built.

---

## Two technologies, one gap

**[Fetch.ai](https://fetch.ai)** built an agent ecosystem where any AI agent can be discovered, communicated with, and used by anyone through natural language. [Agentverse](https://agentverse.ai) handles hosting and discovery. [ASI:One](https://asi1.ai) gives users a chat interface to interact with agents. The network handles identity, routing, and trust. You can write any code inside a Fetch agent, but the framework's strength is in agent coordination, not in providing a sandboxed, policy-checked execution environment for running untrusted workloads.

**[OpenClaw](https://openclaw.ai)** built exactly that: a local execution runtime designed for safe, policy-controlled task execution. It can run tools, access files, and execute workflows on your machine with built-in sandboxing, action allowlists, and signature verification.

But OpenClaw, on its own, is invisible. It runs locally. Nobody outside your machine can discover it, interact with it, or send it work.

Each technology has exactly what the other one is missing:

| | Agent coordination & discovery? | Sandboxed local execution? | Accessible to any user? |
|---|---|---|---|
| **Fetch.ai** | Yes | Not its focus | Yes |
| **OpenClaw** | No | Yes | No |
| **Together** | Yes | Yes | Yes |

Fetch's strength is the network: discovery, communication, trust. OpenClaw's strength is safe local execution: sandboxing, policy enforcement, signature verification. Connect them and you get something neither provides alone: AI agents that are publicly accessible, intelligently plan work, and safely execute real tools on real machines.

---

## The architecture: Plan remotely. Execute locally.

Here's how the integration works:

```
User (natural language)
  → ASI:One (chat interface)
    → Fetch Agent (plans + signs the task)
      → OpenClaw Connector (verifies + executes)
        → Real results back to the user
```

**The Fetch Agent (Orchestrator)** lives on Agentverse. It:
- Receives natural-language objectives from ASI:One
- Uses the ASI:One LLM to break the objective into a structured task plan
- Signs the plan cryptographically (Ed25519)
- Dispatches it to the paired OpenClaw connector

**The OpenClaw Connector** lives on your machine. It:
- Verifies the signature: is this from a trusted agent?
- Checks local policy: are these actions allowed on this machine?
- Executes the plan, step by step
- Returns the results

The key design decision: **the agent that plans the work never touches your files. The service that executes the work never accepts raw commands.**

The Fetch agent sends *what* to do. OpenClaw decides *whether* and *how* to do it.

---

## What Fetch.ai brings to the table

Without Fetch, OpenClaw is a powerful tool that only you can use, on your own machine, from your own terminal. Useful, but limited.

Fetch adds four things that transform it:

**1. Discovery.** A Fetch agent registers on the Almanac, publishes its capabilities, and shows up in ASI:One. Any user on the network can find it and interact with it without knowing your server IP, your API, or your deployment.

**2. Natural language interface.** ASI:One speaks `AgentChatProtocol`. Any agent that implements it gets a chat-based UI for free. Users don't need docs, CLIs, or API keys. They just type what they want in plain English.

**3. Global reachability.** Your agent runs locally (localhost:8200), but Agentverse's mailbox relay makes it reachable from anywhere. Messages from ASI:One go to Agentverse; your local agent polls and picks them up. No public IP. No ngrok. No port forwarding.

**4. Cryptographic identity.** Every agent has an Ed25519 keypair. Every message is tied to a verifiable identity. The connector knows exactly who is making the request and can trust or reject accordingly.

In short: Fetch turns a local tool into a globally accessible AI service.

---

## What OpenClaw brings to the table

Without OpenClaw, a Fetch agent is a conversationalist. It can plan tasks beautifully ("Step 1: clone the repo. Step 2: run analysis. Step 3: generate report.") but nothing actually happens.

OpenClaw adds three things that make agents useful:

**1. Real execution.** Clone repos. Scan files. Run `cloc`. Parse `git log`. Read `requirements.txt`. Count test files. These aren't LLM guesses. They're actual commands running on an actual machine, producing actual data.

**2. Safety by design.** OpenClaw doesn't accept shell commands. It accepts *declarative plans*: named actions with typed parameters. The difference:

```
# Shell command (dangerous, anything goes):
"git clone https://... && cloc . && rm -rf /"

# Declarative plan (safe, every action is constrained):
{"action": "clone_repo", "params": {"url": "https://github.com/owner/repo"}}
```

Each action maps to a pre-built, audited function. There's no way to inject arbitrary commands because the system doesn't speak shell.

**3. Dual policy enforcement.** The orchestrator checks policies *before* dispatching (rate limits, max steps, action allowlists). The connector checks local policies *again* before executing (allowed paths, action allowlists, no destructive operations). If either side says no, nothing runs. Your machine always has the final say.

In short: OpenClaw turns AI plans into real-world results, safely.

---

## To show it works, we built two demo workflows

The architecture is general-purpose. To prove it, we shipped two concrete use cases that anyone can try:

### Demo 1: GitHub Repo Health Analyzer

Open [ASI:One](https://asi1.ai) and type:

> "Analyze https://github.com/fastapi/fastapi"

Behind the scenes:
1. The Fetch agent receives your message and plans three steps: `clone_repo → analyze_repo → generate_health_report`
2. The plan is signed and dispatched to the OpenClaw connector
3. OpenClaw clones the repo into a temp sandbox (no code is executed, it's read as data)
4. It runs static analysis: line counts, git history, test detection, dependency parsing, security checks
5. It compiles a scored health report and deletes the sandbox
6. The report comes back through ASI:One

You get back real numbers: actual lines of code, actual commit counts, actual contributor lists. Not LLM guesses.

### Demo 2: Weekly Dev Report

Type:

> "Generate my weekly dev report"

The agent scans local project directories, collects git commit history from the past 7 days, and compiles a Markdown report with every repo, every commit, and every contributor.

### Same pipeline, different workflows

Both demos follow the identical pattern:

```
Natural language → LLM planning → Signed dispatch → Policy check → Local execution → Real results
```

The repo analyzer and the dev report are just two instances. The pattern works for any workflow that needs real tool execution: security scanning, infrastructure checks, data pipeline monitoring, document processing. Anything where an LLM needs hands.

---

## Neither can do it alone

This is the core point.

| Question | Fetch alone | OpenClaw alone | Together |
|---|---|---|---|
| Can anyone on the internet use it? | Yes | No | **Yes** |
| Can it understand natural language? | Yes | No | **Yes** |
| Does it have sandboxed, policy-checked execution? | Not built-in | Yes | **Yes** |
| Can it plan tasks intelligently? | Yes | No | **Yes** |
| Does it work without a public IP? | Yes (mailbox) | N/A | **Yes** |
| Is every request cryptographically signed? | Yes | Verified | **Yes** |

**Fetch without OpenClaw** = an agent network with great reach and coordination, but no dedicated safe execution layer for running untrusted workloads.

**OpenClaw without Fetch** = a powerful execution runtime that nobody outside your machine can discover or use.

**Together** = publicly accessible AI agents that plan intelligently and execute safely on local machines.

---

## Trust model: why this isn't scary

"A remote AI agent triggering execution on my machine?" Fair concern. Here's why it's safe:

**No shell access.** The agent sends named actions (`clone_repo`, `analyze_repo`), not bash commands. The connector maps each action to a pre-built function. There's no command injection surface.

**Signed everything.** Every task plan carries an Ed25519 signature. The connector verifies it against the orchestrator's known public key. Tampered plans are rejected before any execution begins.

**Double policy check.** The orchestrator enforces its policies (rate limits, action allowlists, max steps). The connector enforces its own (path sandboxing, action allowlists). The orchestrator cannot override local policy. Your machine always has veto power.

**Read-only analysis.** For the repo analyzer specifically: the repo is cloned into a temp directory, treated as data (not code), scanned with static tools, and deleted. Nothing from the repo is ever executed, imported, or installed.

---

## Try it yourself

The agent is live on Fetch's testnet:

1. Go to [ASI:One](https://asi1.ai)
2. Chat with: `agent1qws7lxx6055khltdank6d8ln2ch6ng9z997dv7zvk079xh4p8ejg2u3zjse`
3. Try: **"Analyze https://github.com/fastapi/fastapi"** or **"Generate my weekly dev report"**

**See a real conversation:** [View Sample Chat on ASI:One](https://asi1.ai/chat/f7ccb160-88bc-46a0-bd44-041483eca338)

**Source code:** [github.com/cmaliwal/fetchai-openclaw-orchestrator](https://github.com/cmaliwal/fetchai-openclaw-orchestrator)

---

## Beyond the demos

The repo analyzer and weekly report are just starting points. The same integration pattern (Fetch for planning and reach, OpenClaw for safe execution) extends to any workflow where AI needs to interact with the real world:

- **Security scanning**: run `pip-audit`, `bandit`, `npm audit` on real codebases
- **Infrastructure monitoring**: check server health, disk usage, service status
- **Data pipelines**: process local files, transform data, generate outputs
- **CI/CD dashboards**: pull real build status from your actual pipelines
- **Comparative analysis**: "compare repo A vs repo B" with real metrics

The pattern is always the same: a Fetch agent handles discovery and planning, OpenClaw handles execution, and the user never has to choose between capability and safety.

---

## The takeaway

Every AI agent platform is racing to make agents smarter. But smarter doesn't help when the task requires running `git log` on a repository that was updated ten minutes ago.

LLMs need hands. Fetch.ai gives agents a network to be discovered and a brain to plan. OpenClaw gives them hands to execute, safely, locally, under the user's control.

Neither is complete without the other. Together, they close the gap between AI that talks and AI that works.

---

*Built with [Fetch.ai uAgents](https://fetch.ai), [OpenClaw](https://openclaw.ai), and [ASI:One](https://asi1.ai).*

*For the full technical deep-dive with code samples, see the [Step-by-Step Technical Walkthrough](./fetch-openclaw-integration.md).*
