# Fetch.ai Innovation Lab Examples

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Stars](https://img.shields.io/github/stars/fetchai/innovation-lab-examples?style=social)](https://github.com/fetchai/innovation-lab-examples)

A curated collection of **production-quality agent examples** built with [Fetch.ai](https://fetch.ai) technologies — uAgents, ASI:One, Agentverse, A2A protocol, MCP, and more.

Whether you're building your first agent or architecting multi-agent systems with payments, this repo has a working example for you.

---

## 🎯 Who Is This For?

- **Beginners** exploring autonomous agents and Fetch.ai for the first time
- **Builders** integrating LLMs, payments, or Web3 into agent workflows
- **Hackathon participants** who need a working starter in minutes
- **Contributors** who want to share their agent examples with the community

---

## ⚡ Quickstart — Run Your First Example in Under 2 Minutes

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

> **Prerequisites:** Python 3.10+, pip, and git. Some examples require API keys (ASI:One, OpenAI, Stripe, etc.) — check each example's `.env.example`.

---

## 📁 Repository Structure

```text
innovation-lab-examples/
├── README.md                  # This file
├── CONTRIBUTING.md            # Contribution guide
├── CHANGELOG.md               # Release changelog
├── SECURITY.md                # Vulnerability reporting
├── ISSUES_GUIDE.md            # How to file issues
├── LICENSE                    # Apache 2.0
├── setup.sh                   # Quickstart setup script
├── Dockerfile                 # Run any example in Docker
├── docker-compose.yml         # Docker Compose support
├── docs/                      # Templates and guides
│   └── AGENT_README_TEMPLATE.md
├── .github/                   # CI workflows and templates
│   ├── workflows/
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/
│
├── fetch-hackathon-quickstarter/   # Start here!
├── advance-agent-examples/         # Advanced patterns
├── gemini-quickstart/              # Google Gemini series
├── anthropic-quickstart/           # Claude series
├── ...                             # 30+ examples below
```

---

## 📚 Examples Index

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
| [anthropic-quickstart](anthropic-quickstart/) | Claude integration series — basic, vision, functions, MCP, multi-agent | Python, Anthropic SDK, uAgents | 🟢–🔴 Series |
| [gemini-quickstart](gemini-quickstart/) | Google Gemini series — text, Imagen, Veo, Lyria, TTS, research, film | Python, Google Gemini, uAgents | 🟢–🔴 Series |
| [openai-agent-sdk](openai-agent-sdk/) | OpenAI Agents SDK examples (scholarship finder) | Python, OpenAI SDK, uAgents | 🟡 Intermediate |
| [Claude Agent SDK](Claude%20Agent%20SDK/) | Real estate search agent with Claude SDK | Python, Claude SDK, uAgents | 🟡 Intermediate |
| [google-genai-parallel-processing](google-genai-parallel-processing/) | Parallel processing with Google GenAI | Python, Google GenAI, uAgents | 🟡 Intermediate |
| [flight-tracker-openai-workflow-agent](flight-tracker-openai-workflow-agent/) | Flight tracking with OpenAI workflow agents | Python, OpenAI SDK, uAgents | 🟡 Intermediate |

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
| [advance-agent-examples](advance-agent-examples/) | Advanced patterns — sub-agents, search, policy, security, SEO, due diligence | Python, uAgents, Google ADK | 🟡–🔴 Collection |
| [Crewai-agents](Crewai-agents/) | CrewAI agents — trip planner, code analyzer, meeting prep, blood report | Python, CrewAI, uAgents | 🟡–🔴 Collection |
| [ag2-agents](ag2-agents/) | AG2 framework — research synthesis, payment approval | Python, AG2, uAgents | 🔴 Advanced |
| [community_agent](community_agent/) | AI community growth agent for events and hackathons | Python, uAgents, ASI:One, Tavily | 🟡 Intermediate |
| [pdf-podcast-agent](pdf-podcast-agent/) | PDF-to-podcast with live debate, Q&A, and Stripe payments | Python, uAgents, ASI:One, OpenAI TTS, Stripe | 🔴 Advanced |

### 🌐 Web3 & Blockchain

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [web3](web3/) | Web3 integrations — SingularityNET MeTTa, Internet Computer | Python, MeTTa, ICP, uAgents | 🔴 Advanced |
| [duffel-agent](duffel-agent/) | Flight booking agent with Duffel API and payments | Python, uAgents, Duffel, OpenAI | 🔴 Advanced |

### 🔌 External Integrations

| Example | Description | Tech Stack | Difficulty |
|---------|-------------|------------|------------|
| [Composio](Composio/) | Composio agents — Gmail and LinkedIn automation | Python, Composio, uAgents | 🟡 Intermediate |
| [Browser-based-agents](Browser-based-agents/) | Browser automation agents (Nike product scraper) | Python, Notte, uAgents | 🟡 Intermediate |
| [frontend-integration](frontend-integration/) | Next.js + uAgents frontend integration | Python, Next.js, uAgents | 🟡 Intermediate |

---

## 🐳 Docker Support

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

We welcome contributions from everyone! Whether it's a new agent example, a bug fix, or documentation improvement.

1. **Star this repository** (required before opening a PR)
2. **Fork and create a feature branch** from `main`
3. **Follow the folder structure** — see [CONTRIBUTING.md](CONTRIBUTING.md)
4. **Run linting** — `ruff check . && ruff format .`
5. **Open a PR** using the [PR template](.github/pull_request_template.md)

Every example should include: `README.md`, `requirements.txt`, `.env.example` (if env vars needed), and a demo screenshot.

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
| Security Policy | [SECURITY.md](SECURITY.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Issues Guide | [ISSUES_GUIDE.md](ISSUES_GUIDE.md) |

---

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE).
