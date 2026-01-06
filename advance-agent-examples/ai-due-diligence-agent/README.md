# AI Due Diligence Agent 🔍

An AI-powered multi-agent pipeline for startup investment analysis. Built with [Google ADK](https://google.github.io/adk-docs/) and [Fetch.ai uAgents](https://uagents.fetch.ai/docs), this agent conducts comprehensive due diligence on startups by researching company information, analyzing markets, building financial models, assessing risks, and generating professional investment reports.

## Features

- **Multi-Agent Pipeline**: 7-stage sequential analysis powered by Google's Gemini models
- **Web Research**: Real-time company and market research using Google Search
- **Financial Modeling**: Revenue projections with bear/base/bull scenarios
- **Risk Assessment**: Comprehensive risk analysis with severity ratings
- **Report Generation**: Professional HTML reports and visual infographics
- **Chat Protocol**: Discoverable on Agentverse via uAgents chat protocol

## Pipeline Stages

| Stage | Agent | Model | Description |
|-------|-------|-------|-------------|
| 1 | CompanyResearchAgent | gemini-3-flash-preview | Company basics, founders, product, funding, traction |
| 2 | MarketAnalysisAgent | gemini-3-flash-preview | TAM/SAM, competitors, positioning, trends |
| 3 | FinancialModelingAgent | gemini-3-pro-preview | Revenue projections with scenario analysis |
| 4 | RiskAssessmentAgent | gemini-3-pro-preview | Market, execution, financial, regulatory risks |
| 5 | InvestorMemoAgent | gemini-3-pro-preview | Structured investment memo synthesis |
| 6 | ReportGeneratorAgent | gemini-3-flash-preview | Professional HTML investment report |
| 7 | InfographicGeneratorAgent | gemini-3-flash-preview | Visual investment summary |

## Prerequisites

- Python 3.13+
- Google Cloud Project with:
  - Gemini API enabled
  - Cloud Storage bucket for artifacts
  - Service account with appropriate permissions

## Installation

### Local Setup

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file:

```env
# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_API_KEY=your-gemini-api-key
ASI_API_KEY=your-asi-api-key

# Agent Configuration
AI_DUE_DILIGENCE_AGENT_PORT=8000
AI_DUE_DILIGENCE_AGENT_SEED=your-unique-seed-phrase
```

## Usage

### Run Locally

```bash
python -m ai_due_diligence_agent
```

### Run with Docker

```bash
# Build and run
docker-compose up --build

# Or run in background
docker-compose up -d
```

### Example Queries

Once running, send messages to the agent via Agentverse or direct chat protocol:

```
"Analyze Stripe for Series D investment"
"Due diligence on https://agno.com"
"Evaluate Cursor IDE as a Series A opportunity"
"Check out https://lovable.dev for investment"
```

## Output Artifacts

The agent generates and stores artifacts in Google Cloud Storage:

| Artifact | Description |
|----------|-------------|
| `revenue_chart_*.png` | Financial projection charts |
| `investor_report_*.html` | Professional HTML investment report |
| `investment_infographic_*.png` | Visual summary infographic |

Artifacts are automatically cleaned up after 24 hours.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Root Agent (Coordinator)                       │
│                    DueDiligenceAnalyst                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DueDiligencePipeline                           │
│                   (SequentialAgent)                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Company  │→│ Market   │→│Financial │→│   Risk   │            │
│  │ Research │ │ Analysis │ │ Modeling │ │Assessment│            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│        │            │            │             │                │
│        ▼            ▼            ▼             ▼                │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐                        │
│  │ Investor │→│  Report  │→│Infographic│                        │
│  │   Memo   │ │Generator │ │ Generator │                        │
│  └──────────┘ └──────────┘ └───────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
ai_due_diligence_agent/
├── __init__.py
├── __main__.py          # Entry point
├── agent.py             # Multi-agent pipeline definition
├── executor.py          # uAgents chat protocol integration
└── tools.py             # Custom tools (charts, reports, infographics)
```
