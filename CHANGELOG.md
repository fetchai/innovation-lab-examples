# Changelog

All notable changes to this repository are documented in this file.

## [Unreleased]

### Added

- `pharmacy-locator-agent/`: Beginner-friendly uAgent combining ASI:One location extraction with the free OpenStreetMap Overpass API
- `stripe-payment-agents/twitch-growth-agent/`: Twitch channel growth copilot built on the Fetch.ai uAgents framework. Integrates ASI:One LLM (intent classification, LangGraph 5-node growth pipeline, announcement drafting), Stripe embedded checkout (in-chat one-time unlock), Twitch Helix API (chat settings, announcements, raids, clips), and EventSub WebSocket (reactive copilot that monitors live stream events and proactively suggests actions).
- `Browser-based-agents/playwright/job-application-agent/`: Playwright + ASI:One + Stripe job application agent. Orchestrates a Chromium session to auto-fill Greenhouse application forms using a stored user profile, with LLM-drafted free-text answers via ASI:One, Stripe-gated premium features, and resume ingestion.
- GSSoC '26 label system: [.github/labels/gssoc-labels.json](.github/labels/gssoc-labels.json) definitions, [.github/scripts/create-gssoc-labels.sh](.github/scripts/create-gssoc-labels.sh) bootstrap script, `gssoc-label-bootstrap` workflow (auto-create/update labels), `gssoc-label-sync` workflow (copy `gssoc26`/`level1-3` labels from linked issues to PRs for dashboard tracking), and [docs/GSSOC.md](docs/GSSOC.md) guide
- `langchain-agents/deep-agents/hackflow-agent/`: LangChain Deep Agents hackathon intelligence agent for ASI:One. Three-subagent research pipeline (event_finder, sponsor_researcher, winner_researcher), Stripe-gated full analysis, ASI:One primary LLM with fallbacks, Tavily web search, and persisted cross-turn follow-up memory.
- `news-card-agent/`: ASI:One interactive-cards example. Live news rendered as a `card_kind: "custom"` element-tree (section ? list of items with image, heading, text, badge, and a "Read Full Article" button). Tapping a button opens a fresh detail card. Multi-backend news cascade (Tavily ? NewsAPI.org ? Hacker News), ASI1 LLM-polished card copy, and no payment protocol.
- Auto badge workflow [award-contributor-badge.yml](.github/workflows/award-contributor-badge.yml) for merged external contributor PRs; [BADGE_REGISTRY.json](contributors/BADGE_REGISTRY.json) and [profile-badge-sync](contributors/profile-badge-sync/) for GitHub Profile README
- Maintainer bypass for `review-required` and `stargazer-gate` (Fetch.ai org, repo write access, [.github/MAINTAINERS](.github/MAINTAINERS))
- GitHub issues #54–#91 for intermediate bugs, docs, and `ai-agent-idea` challenges
- `contributors/` folder with [contributors/README.md](contributors/README.md) guide and [contributors/CHANGELOG.md](contributors/CHANGELOG.md) for community agent submissions
- CI gates: `contributor-path-check`, `changelog-check`, and `review-required` (no merge without approval when branch protection is enabled)
- Issue templates: contributor good-first tasks and real-time agent challenge
- `.github/BRANCH_PROTECTION.md` maintainer setup for required reviews and status checks
- `security-scanner-agent/`: LLM-powered code security analysis agent that scans code snippets via ASI:One and returns structured vulnerability reports (type, severity, line number, description, suggested fix). Built on a multi-agent Bureau using the standard Agent Chat Protocol; ASI:One-compatible and discoverable on Agentverse.
- `ticketlens-agent/`: Live real-time travel discovery AI agent powered by TicketLens MCP. High-precision reasoning utilizing the ASI1 LLM, persistent `uAgents` storage, and directly actionable booking deep links.
- `openclaw/`: OpenClaw examples — `fetchai-openclaw-orchestrator` (connector + orchestrator, repo health analyzer) and `agentverse-caller` (OpenClaw skill to search and message Agentverse agents)
- `stripe-payment-agents/youtube-growth-analyzer-agent`: Multi-agent YouTube channel analyzer with free preview and Stripe-gated premium report flow, built for Agentverse/ASI:One chat + payment protocols
- `openai-agent-sdk/Appliance Auto Whisperer`: Multi-agent right-to-repair system — Gemini Vision (via OpenAI SDK) identifies broken parts from photos, Bright Data scrapes prices from 6+ retailers, YouTube Data API finds repair tutorials. Orchestrator coordinates workers via REST fan-out with Docker Compose support.

### Changed

- `openai-agent-sdk/Appliance Auto Whisperer`: Multi-agent right-to-repair assistant for ASI:One with orchestrator + parts/tutorial workers, streamlined bureau-first architecture, and updated README demo screenshots
- `google-adk/google-trends-agent`: Fetch.ai uAgent that answers natural-language Google Trends questions with per-query Stripe payment gating, using ASI:One LLM for BigQuery SQL generation and result interpretation
- `stripe-payment-agents/conversational-property-finder`: ASI1 conversational property search agent (Repliers MLS, optional Stripe details paywall, OpenAI/regex parsing)
- `ag2-agents/` — Two AG2 (formerly AutoGen) multi-agent examples: a payment approval workflow and a research synthesis team, both integrated with uAgents via the A2A protocol
- `community_agent/` — AI Community Growth Agent for planning events, conferences, and hackathons
- `community_agent/` moved to `contributors/community_agent/` — all new community agents must use `contributors/<agent-name>/`
- `CONTRIBUTING.md`, `README.md`, `ISSUES_GUIDE.md`, and PR template updated for contributor folder workflow
- `security-scanner-agent/`: LLM-powered code security analysis agent that scans code snippets via ASI:One and returns structured vulnerability reports (type, severity, line number, description, suggested fix). Built on a multi-agent Bureau using the standard Agent Chat Protocol; ASI:One-compatible and discoverable on Agentverse.
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
- `README.md` rewritten with project overview, quickstart guide, categorized examples index table, folder structure, Docker instructions, and resource links
- `CONTRIBUTING.md` expanded with setup script reference, tagging/categorization guidance, Docker support section, and issue flow references

### Fixed
- Fixed sandbox validation in `scan_directory` to properly reject paths outside the demo sandbox using `Path.relative_to()` (#159)
