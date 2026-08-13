# Changelog

All notable changes to this repository are documented in this file.

## [Unreleased]

### Added

- `Browser-based-agents/browser-use/`: Hackrawl, a browser-use based hackathon discovery, Q&A, and registration agent. Crawls hackathon listings across Cerebral Valley, Devpost, MLH, HackerEarth, Devfolio, ETHGlobal, DoraHacks, and Unstop; a filter → score → LLM rerank recommendation engine; an intent-routed Q&A agent backed by ASI:One; and a browser-driven registration flow with human-in-the-loop profile onboarding and a code-level dry-run submit guard. Profile storage backed by Supabase (`supabase/migrations/`), deployed to Agentverse via mailbox + chat protocol.
- `pydantic-agent/shipping-label-agent/`: the repo's first Pydantic AI example. A chat agent that shops shipping rates across USPS, UPS, FedEx, and DHL, walks through address validation and a couple of quick safety checks, then buys the label once the price is approved, entirely through ASI:One interactive cards. Test-mode only: a Stripe payment gate up front, a second charge for the exact label price before purchase, and Shippo test-mode labels throughout.
- `stripe-payment-agents/twitch-growth-agent/`: Twitch channel growth copilot built on the Fetch.ai uAgents framework. Integrates ASI:One LLM (intent classification, LangGraph 5-node growth pipeline, announcement drafting), Stripe embedded checkout (in-chat one-time unlock), Twitch Helix API (chat settings, announcements, raids, clips), and EventSub WebSocket (reactive copilot that monitors live stream events and proactively suggests actions).

- `Browser-based-agents/playwright/job-application-agent/`: Playwright + ASI:One + Stripe job application agent. Orchestrates a Chromium session to auto-fill Greenhouse application forms using a stored user profile, with LLM-drafted free-text answers via ASI:One, Stripe-gated premium features, and resume ingestion.
- GSSoC '26 label system: [.github/labels/gssoc-labels.json](.github/labels/gssoc-labels.json) definitions, [.github/scripts/create-gssoc-labels.sh](.github/scripts/create-gssoc-labels.sh) bootstrap script, `gssoc-label-bootstrap` workflow (auto-create/update labels), `gssoc-label-sync` workflow (copy `gssoc26`/`level1-3` labels from linked issues to PRs for dashboard tracking), and [docs/GSSOC.md](docs/GSSOC.md) guide
- `langchain-agents/deep-agents/hackflow-agent/`: LangChain Deep Agents hackathon intelligence agent for ASI:One. Three-subagent research pipeline (event_finder, sponsor_researcher, winner_researcher), Stripe-gated full analysis, ASI:One primary LLM with fallbacks, Tavily web search, and persisted cross-turn follow-up memory.
- `news-card-agent/`: ASI:One interactive-cards example. Live news rendered as a `card_kind: "custom"` element-tree (section → list of items with image, heading, text, badge, and a "Read Full Article" button). Tapping a button opens a fresh detail card. Multi-backend news cascade (Tavily → NewsAPI.org → Hacker News), ASI1 LLM-polished card copy, and no payment protocol.
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
- `openai-agent-sdk/Appliance Auto Whisperer`: Multi-agent right-to-repair assistant for ASI:One with orchestrator + parts/tutorial workers, streamlined bureau-first architecture, and updated README demo screenshots
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
- `community_agent/` moved to `contributors/community_agent/` — all new community agents must use `contributors/<agent-name>/`
- `CONTRIBUTING.md`, `README.md`, `ISSUES_GUIDE.md`, and PR template updated for contributor folder workflow
- `README.md` rewritten with project overview, quickstart guide, categorized examples index table, folder structure, Docker instructions, and resource links
- `CONTRIBUTING.md` expanded with setup script reference, tagging/categorization guidance, Docker support section, and issue flow references
### Fixed
- CI `test` job never ran any tests. `find ... | grep -q .` killed `find` with SIGPIPE, and under `set -o pipefail` that failure became the `if` condition, so every run reported "No test files found". Replaced with [`.github/scripts/run-example-tests.sh`](.github/scripts/run-example-tests.sh), which builds a virtualenv per example from that example's `requirements.txt` — a single root `pytest` cannot work because the examples have conflicting dependency sets. All seven suites now run (234 tests)
- CI `review-required` never re-evaluated after a maintainer approved, because it only triggered on push-style PR events. Moved to [`review-required.yml`](.github/workflows/review-required.yml) with a `pull_request_review` trigger, and it now uses each reviewer's latest state so `CHANGES_REQUESTED` overrides an earlier approval
- CI `lint`, `format` and `typecheck` failed on unrelated changes: deleted files were passed to `ruff`/`mypy` (fixed with `--diff-filter=ACMR`), and `mypy` aborted with "Duplicate module" whenever a PR touched two files sharing a basename (now invoked per file)
- Pinned the repo-wide ruff selection in [`ruff.toml`](ruff.toml) to `E4`/`E7`/`E9`/`F`. CI installs the latest ruff, whose default rule set has grown well past what these examples were written against, so upstream releases retroactively failed PRs on untouched code
- `ag2-agents/payment-approval` and `ag2-agents/research-synthesis-team` could not run: ag2 1.0 removed the `autogen` module, a2a-sdk 0.4 removed `a2a.types.TextPart`, and `uagents-adapter` dropped `SingleA2AAdapter`. Pinned to the last compatible line and gave the sync tests an event loop
- `mcp-agents/ticketlens-agent` could not import: mcp 2.0 renamed `streamablehttp_client`. Pinned `mcp<2.0`
- `stripe-payment-agents/twitch-growth-agent` integration tests call `os._exit(0)`, terminating pytest mid-run with a success code and silently dropping the other 28 tests. Deselected by default via `pytest.ini`; still runnable with `pytest -m integration`
- `duffel-agent` shipped real passenger PII (names, `fetch.ai` email addresses, phone numbers, dates of birth, a passport number) in `KNOWN_PASSENGERS`; replaced with an empty map and a commented template
- `Composio/linkedln/.env.example` defined `LINKEDLN_AUTH_CONFIG_ID` while the code reads `LINKEDIN_AUTH_CONFIG_ID`
- `fet-example/.env.example` asked for `GEMINI_API_KEY`, which the example never reads; it uses `ASI_ONE_API_KEY`
- `a2a-cart-store/README.md` told users to install a `../requirements.txt` that does not exist
- `README.md` examples index pointed at `advance-agent-examples/` (renamed to `google-adk/`) and omitted `google-adk`, `langchain-agents`, `pydantic-agent`, `security-scanner-agent` and `video-to-map-agent`
- `contributors/README.md` linked a `gemini-research-agent/` directory that does not exist, and omitted the two community agents that do
- Corrected seven relative links in example READMEs that pointed at the wrong directory depth
- `security-scanner-agent/,gitignore` was a typo for `.gitignore`, so its ignore rules never applied
- `.github/BRANCH_PROTECTION.md` listed `contributor-path-check` as a required status check; no workflow produces it, so requiring it would block every PR forever
- Fixed sandbox validation in `scan_directory` to properly reject paths outside the demo sandbox using `Path.relative_to()` (#159)

### Removed
- Committed build artifacts: a 5,310-file Python virtualenv under `frontend-integration/venv/`, 2,265 `__pycache__` entries, 15 `.DS_Store` files, and uAgents runtime state (`duffel-agent/state/*.sqlite`, `agent1q*_data.json`)
- Two dead files: an empty `duffel-agent/runner.py` and `mcp-agents/events-finder-mcp-agent/new-adapter.py`, an unreferenced orphan importing a `.protocol` module that does not exist
- The blanket `*.json` rule in `.gitignore`, replaced with credential-specific patterns; it silently dropped legitimate project files. `.dockerignore` is no longer ignored either
- Tracked `Crewai-agents/*/.env` files, renamed to `.env.example` (both only ever held empty placeholders, verified across the full history)