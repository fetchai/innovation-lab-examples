# AI Due Diligence Sub Agents — Multi-Agent Venture Capital Due Diligence Pipeline

A sophisticated multi-agent system for automated venture capital due diligence, powered by Google's Agent Development Kit (ADK) and Gemini models. Each specialized agent handles a distinct phase of the investment analysis workflow.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               AI Due Diligence Sub Agents Agent Pipeline                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐              │
│   │   Company    │──▶│    Market     │──▶│   Financial      │              │
│   │   Research   │    │   Analysis   │    │    Modeling      │              │
│   │   :8009      │    │   :8010      │    │    :8011         │              │
│   └──────────────┘    └──────────────┘    └──────────────────┘              │
│          │                   │                     │                        │
│          └───────────────────┴─────────────────────┘                        │
│                              │                                              │
│                              ▼                                              │
│                    ┌──────────────────┐                                     │
│                    │  Risk Assessment │                                     │
│                    │      :8012       │                                     │
│                    └──────────────────┘                                     │
│                              │                                              │
│                              ▼                                              │
│                    ┌──────────────────┐                                     │
│                    │  Investor Memo   │                                     │
│                    │      :8013       │                                     │
│                    └──────────────────┘                                     │
│                              │                                              │
│              ┌───────────────┴───────────────┐                              │
│              ▼                               ▼                              │
│    ┌──────────────────┐           ┌────────────────────┐                    │
│    │ Report Generator │           │ Infographic Gen    │                    │
│    │      :8014       │           │      :8015         │                    │
│    └──────────────────┘           └────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Specifications

### 1️⃣ Company Research Agent
> **Port:** `8009` | **Model:** `gemini-3-flash-preview`

Conducts structured company research using live web search to gather fundamental data.

| Attribute | Details |
|-----------|---------|
| **Role** | Senior Investment Analyst |
| **Tool** | `google_search` |
| **Specialties** | Company basics, founders, team backgrounds, product overview, technology, funding history, investors, traction signals, partnerships, news, press mentions, early-stage discovery |

**Example Query:**
```
Can you tell me what Anthropic does and who founded it?
```

---

### 2️⃣ Market Analysis Agent
> **Port:** `8010` | **Model:** `gemini-3-flash-preview`

Analyzes market size, competitive landscape, and industry trends.

| Attribute | Details |
|-----------|---------|
| **Role** | Market Research Analyst |
| **Tool** | `google_search` |
| **Specialties** | Market size (TAM/SAM), market growth, competitive landscape, competitor funding, positioning, differentiation, industry trends, emerging technologies, regulatory trends, category creation |

**Example Query:**
```
How big is the market for enterprise AI tools and who are the main competitors?
```

---

### 3️⃣ Financial Modeling Agent
> **Port:** `8011` | **Model:** `gemini-3-pro-preview`

Builds comprehensive financial projections with multi-scenario analysis.

| Attribute | Details |
|-----------|---------|
| **Role** | Financial Analyst |
| **Tool** | `generate_financial_chart` |
| **Output** | Revenue projection charts (PNG) saved to GCS |
| **Specialties** | ARR estimation, revenue modeling, growth scenarios (bear/base/bull), financial projections, valuation modeling, exit multiples, MOIC, IRR, unit economics, runway analysis, scenario analysis |

**Example Query:**
```
If an AI startup is making around $2M a year, what could its growth and valuation look like over the next 5 years?
```

---

### 4️⃣ Risk Assessment Agent
> **Port:** `8012` | **Model:** `gemini-3-pro-preview`

Performs deep multi-dimensional risk analysis for venture investments.

| Attribute | Details |
|-----------|---------|
| **Role** | Senior VC Risk Analyst |
| **Tool** | None (LLM reasoning only) |
| **Specialties** | Market risk, execution risk, financial risk, regulatory risk, exit risk, risk severity scoring, mitigation strategies, downside analysis, investment protection terms, VC risk frameworks |

**Example Query:**
```
What are the biggest risks in investing in an early-stage AI startup?
```

---

### 5️⃣ Investor Memo Agent
> **Port:** `8013` | **Model:** `gemini-3-pro-preview`

Synthesizes all research into a decision-ready investment memorandum.

| Attribute | Details |
|-----------|---------|
| **Role** | Senior Investment Partner |
| **Tool** | None (LLM synthesis only) |
| **Specialties** | Investment memo writing, executive summaries, investment thesis, return narratives, risk synthesis, decision recommendations, VC memos, strategic insights, early-stage evaluation |

**Example Query:**
```
Can you summarize whether investing in an AI startup like VectorFlow AI would be a good idea?
```

---

### 6️⃣ Report Generator Agent
> **Port:** `8014` | **Model:** `gemini-3-flash-preview`

Generates polished, McKinsey-style HTML investment reports.

| Attribute | Details |
|-----------|---------|
| **Role** | Professional Report Generator |
| **Tool** | `generate_html_report` |
| **Output** | Investor-grade HTML reports saved to GCS |
| **Specialties** | HTML report generation, investment reports, executive formatting, professional layouts, print-ready reports, consulting-style docs, artifact generation |

**Example Query:**
```
Can you turn this investment summary into a professional report?
```

---

### 7️⃣ Infographic Generator Agent
> **Port:** `8015` | **Model:** `gemini-3-flash-preview`

Creates concise visual investment summaries for quick decision-making.

| Attribute | Details |
|-----------|---------|
| **Role** | Visual Summary Creator |
| **Tool** | `generate_infographic` (uses `gemini-3-pro-image-preview`) |
| **Output** | Investment infographic images (PNG) saved to GCS |
| **Specialties** | Investment infographics, visual summaries, key metrics visualization, risk visualization, market snapshots, executive dashboards, artifact generation |

**Example Query:**
```
Can you create a quick visual summary of this investment?
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Framework** | Google Agent Development Kit (ADK) v1.21+ |
| **Models** | Gemini 3 Flash Preview, Gemini 3 Pro Preview |
| **Runtime** | Python 3.13+ |
| **Package Manager** | uv |
| **Containerization** | Docker / Docker Compose |
| **Artifact Storage** | Google Cloud Storage (GCS) |
| **A2A Protocol** | uAgents Adapter v0.6.2 |

---

## 📁 Project Structure

```
AI Due Diligence Sub Agents/
├── agents/
│   ├── company_research.py      # Company fundamentals research
│   ├── market_analysis.py       # Market & competitive analysis
│   ├── financial_modeling.py    # Financial projections & charts
│   ├── risk_assessment.py       # Multi-dimensional risk analysis
│   ├── investor_memo.py         # Investment memo synthesis
│   ├── report_generator.py      # HTML report generation
│   └── infographic_generator.py # Visual summary creation
├── shared/
│   ├── agent.py                 # AgentManager class & configuration
│   ├── executor.py              # Base agent executor
│   ├── runner.py                # Agent runner utilities
│   └── tools.py                 # Custom tools (charts, reports, infographics)
├── docker-compose.yml           # Multi-container orchestration
├── Dockerfile                   # Container build configuration
├── pyproject.toml               # Python dependencies
├── .env                         # Environment configuration
└── README.md
```

---

## ⚙️ Configuration

All agent configurations are managed via environment variables in `.env`:

### API Keys
```bash
GOOGLE_API_KEY=<your-google-api-key>
ASI_API_KEY=<your-asi-api-key>
GOOGLE_STORAGE_BUCKET_NAME=<your-gcs-bucket>
```

### Per-Agent Configuration Pattern
Each agent follows this naming convention:
```bash
<AGENT_PREFIX>_NAME=<agent-name>
<AGENT_PREFIX>_MODEL=<gemini-model>
<AGENT_PREFIX>_DESCRIPTION=<description>
<AGENT_PREFIX>_INSTRUCTION=<system-prompt>
<AGENT_PREFIX>_AGENT_PORT=<http-port>
<AGENT_PREFIX>_A2A_PORT=<a2a-port>
<AGENT_PREFIX>_COORDINATOR_PORT=<coordinator-port>
<AGENT_PREFIX>_SPECIALTIES=<comma-separated-specialties>
```

### Common Agent Settings
```bash
AGENT_CACHE_MIN_TOKENS=2048
AGENT_CACHE_TTL_SECONDS=1800
AGENT_CACHE_INTERVALS=10
AGENT_COMPACTION_INTERVAL=3
AGENT_COMPACTION_OVERLAP=1
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Google Cloud credentials configured
- API keys in `.env` file

### Run All Agents
```bash
docker compose up --build
```

### Run Individual Agent
```bash
# Using uv directly
uv run -m agents.company_research

# Or via Docker
docker compose up company-research-agent
```

### Agent Endpoints

| Agent | HTTP Port | A2A Port | Coordinator Port |
|-------|-----------|----------|------------------|
| Company Research | 8009 | 9001 | 11020 |
| Market Analysis | 8010 | 9002 | 11021 |
| Financial Modeling | 8011 | 9003 | 11022 |
| Risk Assessment | 8012 | 9004 | 11023 |
| Investor Memo | 8013 | 9005 | 11024 |
| Report Generator | 8014 | 9006 | 11025 |
| Infographic Generator | 8015 | 9007 | 11026 |

---

## 📊 Output Artifacts

Generated artifacts are stored in Google Cloud Storage with time-limited signed URLs:

| Agent | Artifact Type | Format |
|-------|---------------|--------|
| Financial Modeling | Revenue Projection Charts | PNG |
| Report Generator | Investment Reports | HTML |
| Infographic Generator | Visual Summaries | PNG |