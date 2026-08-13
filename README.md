<div align="center">

# Fetch.ai Innovation Lab Examples

### 80+ production-ready AI agent examples in Python

Build **autonomous AI agents**, **multi-agent systems** and **agentic AI** workflows with
[uAgents](https://github.com/fetchai/uAgents), [ASI:One](https://asi1.ai/), [Agentverse](https://agentverse.ai/),
MCP, the A2A protocol, LangChain, CrewAI, Gemini, Claude and OpenAI.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Stars](https://img.shields.io/github/stars/fetchai/innovation-lab-examples?style=flat&logo=github)](https://github.com/fetchai/innovation-lab-examples/stargazers)
[![Forks](https://img.shields.io/github/forks/fetchai/innovation-lab-examples?style=flat&logo=github)](https://github.com/fetchai/innovation-lab-examples/network/members)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docs](https://img.shields.io/badge/Docs-Innovation%20Lab-000000)](https://innovationlab.fetch.ai/resources/docs/intro)

[Quickstart](#-quickstart) · [Examples](#-examples-index) · [Structure](#-repository-structure) · [Docker](#-docker-support) · [Contributing](#-contributing) · [FAQ](#-faq)

</div>


## 📈 Star history

<p align="center">
 <a href="https://github.com/fetchai/innovation-lab-examples/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/fetchai/innovation-lab-examples?style=for-the-badge&logo=github&label=Stars&color=1f6feb" /></a>
 <a href="https://github.com/fetchai/innovation-lab-examples/forks"><img alt="GitHub forks" src="https://img.shields.io/github/forks/fetchai/innovation-lab-examples?style=for-the-badge&logo=github&label=Forks&color=8957e5" /></a>
 <a href="https://github.com/fetchai/innovation-lab-examples/graphs/contributors"><img alt="Contributors" src="https://img.shields.io/github/contributors/fetchai/innovation-lab-examples?style=for-the-badge&logo=github&label=Contributors&color=2ea043" /></a>
 <a href="https://github.com/fetchai/innovation-lab-examples/commits/main"><img alt="Last commit" src="https://img.shields.io/github/last-commit/fetchai/innovation-lab-examples?style=for-the-badge&logo=git&label=Last%20commit&color=db6d28" /></a>
</p>

<p align="center">
 <a href="https://www.star-history.com/#fetchai/innovation-lab-examples&Date">
 </a>
</p>

If these examples save you time, a ⭐ helps other developers find them.

---

Every folder here is a **self-contained, runnable AI agent project** with its own README, dependencies and
environment template. Whether you are writing your first autonomous agent or architecting a multi-agent
system with real payments, there is a working example to start from.

## 🎯 Who is this for?

- **Beginners** exploring autonomous agents and Fetch.ai for the first time
- **Builders** integrating LLMs, payments or Web3 into agent workflows
- **Hackathon participants** who need a working starter in minutes
- **Contributors** who want to share their agent examples with the community

---

## ⚡ Quickstart

Run your first agent in under two minutes:

```bash
# 1. Clone the repo
git clone https://github.com/fetchai/innovation-lab-examples.git
cd innovation-lab-examples

# 2. Pick an example (e.g. the hackathon quickstarter)
cd fetch-hackathon-quickstarter

# 3. Create a virtual environment and install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 5. Run the agent
python agents/alice/agent.py
```

Or use the **automated setup script** from the repo root:

```bash
./setup.sh fetch-hackathon-quickstarter
```

> **Prerequisites:** Python 3.10+, pip and git. Some examples require API keys (ASI:One, OpenAI, Stripe, etc.) — check each example's `.env.example`.

---

## 📁 Repository structure

```text
innovation-lab-examples/
│
├── 📄 README.md                 # This file
├── 📄 CONTRIBUTING.md           # How to contribute
├── 📄 SECURITY.md               # Vulnerability reporting
├── 📄 ISSUES_GUIDE.md           # How to file a good issue
├── 📄 LICENSE                   # Apache 2.0
├── 🔧 setup.sh                  # One-command example setup
├── 🐳 Dockerfile                # Run any example in a container
├── 🐳 docker-compose.yml        # Compose support
├── 🔧 ruff.toml                 # Repo-wide lint baseline
│
├── 📂 .github/                  # CI and contributor templates
│   ├── workflows/               #   ci · pull_request_ci · review-required · pr-ai-review
│   ├── scripts/                 #   run-example-tests.sh (per-example test runner)
│   ├── ISSUE_TEMPLATE/
│   ├── pull_request_template.md
│   ├── CODEOWNERS
│   └── BRANCH_PROTECTION.md
│
├── 📂 scripts/                  # Repository tooling
│   └── pr-ai-review.mjs         #   ASI:One code review for pull requests
│
├── 📂 docs/                     # Shared guides and templates
│   └── AGENT_README_TEMPLATE.md
│
├── 📂 contributors/             # 👈 Community agents go here
│   ├── README.md                #   Contributor guide
│   ├── CHANGELOG.md             #   Community changelog
│   ├── community_agent/
│   ├── news-summarizer-agent/
│   └── gemini-task-manager-agent/
│
├── 🟢 Getting started
│   ├── fetch-hackathon-quickstarter/   # 👈 Start here
│   ├── av-script-example/
│   ├── asi-cloud-agent/
│   ├── deploy-agent-on-av/
│   ├── openclaw/
│   └── cursor-rules/
│
├── 🤖 LLM integration
│   ├── asi1-llm-example/
│   ├── news-card-agent/
│   ├── anthropic-quickstart/
│   ├── gemini-quickstart/
│   ├── openai-agent-sdk/
│   ├── Claude Agent SDK/
│   ├── google-genai-parallel-processing/
│   ├── flight-tracker-openai-workflow-agent/
│   ├── langchain-agents/
│   ├── pydantic-agent/
│   └── security-scanner-agent/
│
├── 🔗 Agent-to-agent (A2A)
│   ├── launch-your-a2a-agent/
│   ├── launch-your-a2a-research-team/
│   ├── a2a-cart-store/
│   └── a2a-uAgents-Integration/
│
├── 🧩 MCP
│   └── mcp-agents/
│
├── 💰 Payments
│   ├── fet-example/
│   ├── image-agent-payment-protocol/
│   ├── stripe-horoscope-agent/
│   └── stripe-payment-agents/
│
├── 🧠 RAG and knowledge
│   ├── Rag-agent/
│   ├── llama-index/
│   └── pdf-summariser-example/
│
├── 👥 Multi-agent systems
│   ├── google-adk/
│   ├── Crewai-agents/
│   ├── ag2-agents/
│   └── video-to-map-agent/
│
├── 🌐 Web3
│   ├── web3/
│   └── duffel-agent/
│
└── 🔌 External integrations
    ├── Composio/
    ├── Browser-based-agents/
    └── frontend-integration/
```

---

## 📚 Examples index

### 🟢 Getting Started

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [fetch-hackathon-quickstarter](fetch-hackathon-quickstarter/) | Hackathon-ready template with orchestrator + worker agents | Python, uAgents | 🟢 Beginner |
| [openclaw/](openclaw/) | **OpenClaw** — connector + orchestrator (`fetchai-openclaw-orchestrator`) and Agentverse caller skill (`agentverse-caller`) | Python, Shell, OpenClaw, Agentverse, uAgents | 🟢–🟡 |
| [av-script-example](av-script-example/) | Agentverse script deployment example | Python, uAgents | 🟢 Beginner |
| [asi-cloud-agent](asi-cloud-agent/) | Basic ASI Cloud agent deployment | Python, uAgents | 🟢 Beginner |
| [deploy-agent-on-av](deploy-agent-on-av/) | Deploy agents on Agentverse via Render | Python, uAgents, Render | 🟢 Beginner |
| [cursor-rules](cursor-rules/) | Cursor IDE rules for Fetch.ai development | MDC rules | 🟢 Beginner |

### 🤖 LLM Integration

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [asi1-llm-example](asi1-llm-example/) | ASI:One LLM with LangChain integration | Python, LangChain, ASI:One | 🟢 Beginner |
| [news-card-agent](news-card-agent/) | Live news rendered as ASI:One interactive cards (custom element-tree) with Tavily + ASI1 polish | Python, uAgents, ASI:One, Tavily, Cards | 🟡 Intermediate |
| [anthropic-quickstart](anthropic-quickstart/) | Claude integration series — basic, vision, functions, MCP, multi-agent | Python, Anthropic SDK, uAgents | 🟢–🔴 Series |
| [gemini-quickstart](gemini-quickstart/) | Google Gemini series — text, Imagen, Veo, Lyria, TTS, research, film | Python, Google Gemini, uAgents | 🟢–🔴 Series |
| [openai-agent-sdk](openai-agent-sdk/) | OpenAI Agents SDK examples (scholarship finder) | Python, OpenAI SDK, uAgents | 🟡 Intermediate |
| [Claude Agent SDK](Claude%20Agent%20SDK/) | Real estate search agent with Claude SDK | Python, Claude SDK, uAgents | 🟡 Intermediate |
| [google-genai-parallel-processing](google-genai-parallel-processing/) | Parallel processing with Google GenAI | Python, Google GenAI, uAgents | 🟡 Intermediate |
| [flight-tracker-openai-workflow-agent](flight-tracker-openai-workflow-agent/) | Flight tracking with OpenAI workflow agents | Python, OpenAI SDK, uAgents | 🟡 Intermediate |
| [langchain-agents](langchain-agents/) | Hackflow — hackathon competitive-intelligence agent built on LangChain Deep Agents with Stripe payments | Python, LangChain, uAgents, Stripe | 🔴 Advanced |
| [pydantic-agent](pydantic-agent/) | Shipping label booking agent using Pydantic AI and ASI:One interactive cards | Python, Pydantic AI, uAgents, Shippo | 🔴 Advanced |
| [security-scanner-agent](security-scanner-agent/) | LLM-powered code security scanner returning structured vulnerability reports | Python, uAgents, ASI:One | 🟡 Intermediate |

### 🔗 Agent-to-Agent (A2A)

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [launch-your-a2a-agent](launch-your-a2a-agent/) | Quick A2A agent launcher | Python, uAgents, A2A | 🟢 Beginner |
| [launch-your-a2a-research-team](launch-your-a2a-research-team/) | Multi-agent A2A research team | Python, uAgents, A2A | 🟡 Intermediate |
| [a2a-cart-store](a2a-cart-store/) | A2A shopping cart with Skyfire payments | Python, uAgents, Skyfire | 🟡 Intermediate |
| [a2a-uAgents-Integration](a2a-uAgents-Integration/) | A2A communication examples (YouTube, shopping, currency, competitor analysis) | Python, uAgents, LangGraph | 🟡–🔴 Collection |

### 🧩 MCP (Model Context Protocol)

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [mcp-agents](mcp-agents/) | MCP server agents — Gmail, Calendar, Events, Airbnb, Perplexity, GitHub, Context7 | Python, MCP, uAgents | 🟡 Intermediate |

### 💰 Payments

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [fet-example](fet-example/) | FET payment + ASI:One image generation agent | Python, uAgents, ASI:One, FET | 🟡 Intermediate |
| [image-agent-payment-protocol](image-agent-payment-protocol/) | Image generation with payment protocol | Python, uAgents, Skyfire | 🟡 Intermediate |
| [stripe-horoscope-agent](stripe-horoscope-agent/) | Horoscope agent with Stripe payments | Python, uAgents, Stripe | 🟡 Intermediate |
| [stripe-payment-agents](stripe-payment-agents/) | Stripe payment examples (property finder, expense calculator) | Python, uAgents, Stripe | 🔴 Advanced |

### 🧠 RAG & Knowledge

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [Rag-agent](Rag-agent/) | RAG agent with vector search | Python, uAgents, RAG | 🟡 Intermediate |
| [llama-index](llama-index/) | LlamaIndex RAG agent with Stripe payments | Python, LlamaIndex, uAgents, Stripe | 🔴 Advanced |
| [pdf-summariser-example](pdf-summariser-example/) | PDF summarization agent | Python, uAgents, ASI:One | 🟢 Beginner |

### 👥 Multi-Agent Systems

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [google-adk](google-adk/) | Google ADK patterns — sub-agents, search, policy, security, SEO audit, due diligence, trends | Python, uAgents, Google ADK | 🟡–🔴 Collection |
| [Crewai-agents](Crewai-agents/) | CrewAI agents — trip planner, code analyzer, meeting prep, blood report | Python, CrewAI, uAgents | 🟡–🔴 Collection |
| [ag2-agents](ag2-agents/) | AG2 framework — research synthesis, payment approval | Python, AG2, uAgents | 🔴 Advanced |
| [video-to-map-agent](video-to-map-agent/) | Turns YouTube travel vlogs into a day-by-day itinerary with route map, PDF and Excel output | Python, uAgents, ASI:One, Google Maps, Stripe | 🔴 Advanced |

### 🌍 Community Contributors

**New community agents belong in [`contributors/`](contributors/)** — see [contributors/README.md](contributors/README.md).

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [contributors/community_agent](contributors/community_agent/) | AI community growth agent for events and hackathons | Python, uAgents, ASI:One, Tavily | 🟡 Intermediate |
| [contributors/news-summarizer-agent](contributors/news-summarizer-agent/) | Fetches top headlines for a topic via NewsAPI and summarizes them with ASI:One, via Chat Protocol | Python, uAgents, NewsAPI, ASI:One | 🟡 Intermediate |
| [contributors/gemini-task-manager-agent](contributors/gemini-task-manager-agent/) | Natural-language task manager backed by Gemini | Python, uAgents, Gemini | 🟡 Intermediate |

### 🌐 Web3 & Blockchain

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [web3](web3/) | Web3 integrations — SingularityNET MeTTa, Internet Computer | Python, MeTTa, ICP, uAgents | 🔴 Advanced |
| [duffel-agent](duffel-agent/) | Flight booking agent with Duffel API and payments | Python, uAgents, Duffel, OpenAI | 🔴 Advanced |

### 🔌 External Integrations

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [Composio](Composio/) | Composio agents — Gmail and LinkedIn automation | Python, Composio, uAgents | 🟡 Intermediate |
| [Browser-based-agents](Browser-based-agents/) | Browser automation agents (Nike product scraper, job-application agent) | Python, Notte, Playwright, uAgents | 🟡 Intermediate |
| [frontend-integration](frontend-integration/) | Next.js + uAgents frontend integration | Python, Next.js, uAgents | 🟡 Intermediate |

---

## 🐳 Docker support

Run any example in a container without installing Python locally:

```bash
# Build and run a specific example
docker build --build-arg EXAMPLE=fetch-hackathon-quickstarter -t fetch-example .

# Run with your environment variables
docker run --env-file fetch-hackathon-quickstarter/.env fetch-example
```

Or use Docker Compose:

```bash
EXAMPLE=fetch-hackathon-quickstarter docker compose up
```

> Several examples also include their own `Dockerfile` and `docker-compose.yml` for custom setups.

---
## 🤝 Contributing

We welcome contributions from everyone — a new agent example, a bug fix or a documentation improvement.

1. **Star this repository** (required before opening a PR)
2. **Fork and create a feature branch** from `main`
3. **New agents go in `contributors/<your-agent-name>/`** — see [contributors/README.md](contributors/README.md)
4. **Pick an issue** — [good first issues](https://github.com/fetchai/innovation-lab-examples/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) or feature challenges (real-time booking, payments, etc.)
5. **Run linting** — `ruff check . && ruff format .`
6. **Run the tests** — `bash .github/scripts/run-example-tests.sh <your-example>`
7. **Open a PR** using the [PR template](.github/pull_request_template.md) — **PRs require maintainer review before merge**

Every example should include: `README.md`, `requirements.txt`, `.env.example` (if env vars are needed), and a demo screenshot.

Use the [Agent README Template](docs/AGENT_README_TEMPLATE.md) for new examples.

---

## 📖 Resources

| Resource | Link |
|----------|------|
| Innovation Lab Docs | [innovationlab.fetch.ai/resources/docs/intro](https://innovationlab.fetch.ai/resources/docs/intro) |
| Agentverse | [agentverse.ai](https://agentverse.ai/) |
| ASI:One API | [asi1.ai](https://asi1.ai/) |
| uAgents Framework | [github.com/fetchai/uAgents](https://github.com/fetchai/uAgents) |
| Contributing Guide | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Community Agents Folder | [contributors/README.md](contributors/README.md) |
| Security Policy | [SECURITY.md](SECURITY.md) |
| Community Changelog | [contributors/CHANGELOG.md](contributors/CHANGELOG.md) |
| Issues Guide | [ISSUES_GUIDE.md](ISSUES_GUIDE.md) |

---

## ❓ FAQ

<details>
<summary><strong>What is an AI agent?</strong></summary>

An AI agent is a program that perceives its environment, decides what to do and acts on its own to reach a
goal — rather than waiting for step-by-step instructions. The agents in this repo use an LLM for reasoning
and the [uAgents](https://github.com/fetchai/uAgents) framework for messaging, discovery and payments.
</details>

<details>
<summary><strong>Which example should I start with?</strong></summary>

[`fetch-hackathon-quickstarter`](fetch-hackathon-quickstarter/) — it shows the orchestrator + worker pattern
that most other examples build on. From there, pick the category matching your use case in the
[examples index](#-examples-index).
</details>

<details>
<summary><strong>Do I need API keys?</strong></summary>

Most examples need at least one. Each example ships a `.env.example` listing exactly what it reads. An
[ASI:One](https://asi1.ai/) key covers the majority; individual examples may also need OpenAI, Anthropic,
Google, Stripe or a vendor key.
</details>

<details>
<summary><strong>Are these examples free to use commercially?</strong></summary>

Yes. Everything here is [Apache 2.0](LICENSE) licensed. Third-party APIs each example calls have their own
terms and pricing.
</details>

<details>
<summary><strong>How do I deploy an agent to production?</strong></summary>

See [`deploy-agent-on-av`](deploy-agent-on-av/) for Agentverse deployment via Render, and
[`asi-cloud-agent`](asi-cloud-agent/) for ASI Cloud. Any example can also run in Docker — see
[Docker support](#-docker-support).
</details>

<details>
<summary><strong>How do multi-agent systems work here?</strong></summary>

Two patterns. **A2A** (agent-to-agent) connects independent agents over a shared protocol — see
[`a2a-uAgents-Integration`](a2a-uAgents-Integration/). **Framework orchestration** runs a team inside one
process — see [`Crewai-agents`](Crewai-agents/), [`ag2-agents`](ag2-agents/) and [`google-adk`](google-adk/).
</details>

<details>
<summary><strong>Can I add my own agent?</strong></summary>

Yes, and we would like you to. Put it in [`contributors/<your-agent-name>/`](contributors/) and read
[CONTRIBUTING.md](CONTRIBUTING.md) first.
</details>

---

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).

<div align="center">

**Topics:** ai-agents · autonomous-agents · multi-agent-systems · agentic-ai · llm-agents · uagents · fetchai · agentverse · asi-one · mcp · a2a-protocol · langchain · crewai · openai · python

Built by the [Fetch.ai](https://fetch.ai) Innovation Lab and its contributors.

</div>
