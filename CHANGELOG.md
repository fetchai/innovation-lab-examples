# Changelog

All notable changes to this repository are documented in this file.

## [Unreleased]

### Added

- `stripe-payment-agents/youtube-growth-analyzer-agent`: Multi-agent YouTube channel analyzer with free preview and Stripe-gated premium report flow, built for Agentverse/ASI:One chat + payment protocols
- `openai-agent-sdk/Appliance Auto Whisperer`: Multi-agent right-to-repair system — Gemini Vision (via OpenAI SDK) identifies broken parts from photos, Bright Data scrapes prices from 6+ retailers, YouTube Data API finds repair tutorials. Orchestrator coordinates workers via REST fan-out with Docker Compose support.

- `google-adk/google-trends-agent`: Fetch.ai uAgent that answers natural-language Google Trends questions with per-query Stripe payment gating, using ASI:One LLM for BigQuery SQL generation and result interpretation

- `stripe-payment-agents/conversational-property-finder`: ASI1 conversational property search agent (Repliers MLS, optional Stripe details paywall, OpenAI/regex parsing)
- `ag2-agents/` — Two AG2 (formerly AutoGen) multi-agent examples: a payment approval workflow and a research synthesis team, both integrated with uAgents via the A2A protocol
- `community_agent/` — AI Community Growth Agent for planning events, conferences, and hackathons
- `CONTRIBUTING.md` with agent-focused contribution workflow and merge policy
- Pull request CI workflow with checks for `stargazer-gate`, `lint`, `format`, `typecheck`, `validate-architecture`, and `test`
- `.github/CODEOWNERS` for required reviewer routing
- `ISSUES_GUIDE.md` and issue templates for bug/error/path/code/feature reports
- `.github/pull_request_template.md` for structured PR submissions
- `docs/AGENT_README_TEMPLATE.md` for contributor-ready agent README format
- `SECURITY.md` for vulnerability reporting and security expectations
- `setup.sh` — automated quickstart script for setting up any example in one command
- `Dockerfile` and `docker-compose.yml` — run any example in a container
- `.dockerignore` for clean Docker builds
- `.github/workflows/ci.yml` — push-to-main CI (lint, format, architecture, test)
- Tagging and categorization guidelines in `CONTRIBUTING.md`
- Missing `requirements.txt` for `community_agent`, `av-script-example`, `asi1-llm-example`, `advance-agent-examples/{search,policy,basic}_agent`
- Missing `.env.example` for `community_agent`, `duffel-agent`, `deploy-agent-on-av`, `asi-cloud-agent`, `pdf-summariser-example`, `flight-tracker-openai-workflow-agent`, `google-genai-parallel-processing/brand-management-agent`, `Rag-agent/ango`, `asi1-llm-example`
- Missing `README.md` for `duffel-agent`, `deploy-agent-on-av`

### Changed

- `README.md` rewritten with project overview, quickstart guide, categorized examples index table, folder structure, Docker instructions, and resource links
- `CONTRIBUTING.md` expanded with setup script reference, tagging/categorization guidance, Docker support section, and issue flow references