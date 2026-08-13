# Changelog

All notable changes to this repository are documented in this file.

## [Unreleased]

### Added

- AI code review on every pull request into `main`, powered by ASI:One: [`pr-ai-review.yml`](.github/workflows/pr-ai-review.yml) and [`scripts/pr-ai-review.mjs`](scripts/pr-ai-review.mjs). Posts inline comments on the diff, plus a summary, and fails the check on a high-confidence `must_fix` or a secret-scan hit so it can be made merge-blocking. Uses `pull_request_target` so the key is available on fork PRs, and deliberately never checks out or runs contributor code — it only reads the diff over the API. Requires an `ASI_ONE_API_KEY` secret; without it the job explains what is missing and passes rather than blocking
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
- `README.md` restructured for discoverability: keyword-led header, quick nav, a full annotated folder tree grouped by category, a [star history](https://star-history.com/#fetchai/innovation-lab-examples&Date) chart, and an FAQ covering the questions people actually search for. The repository had **no GitHub topics set at all**, which is the single largest discoverability gap on GitHub — 20 topics are now set (`ai-agents`, `autonomous-agents`, `multi-agent-systems`, `agentic-ai`, `llm-agents`, `uagents`, `mcp`, `a2a-protocol`, …) along with a keyword-led description and a homepage link. `contributors/gemini-task-manager-agent/` was missing from the index and is now listed
- `community_agent/` moved to `contributors/community_agent/` — all new community agents must use `contributors/<agent-name>/`
- `CONTRIBUTING.md`, `README.md`, `ISSUES_GUIDE.md`, and PR template updated for contributor folder workflow
- `README.md` rewritten with project overview, quickstart guide, categorized examples index table, folder structure, Docker instructions, and resource links
- `CONTRIBUTING.md` expanded with setup script reference, tagging/categorization guidance, Docker support section, and issue flow references
### Fixed
- `Dockerfile` and `setup.sh` failed on Windows and on examples with no `requirements.txt` (issue #143). The Dockerfile `COPY`d `requirements.txt` unconditionally, which is a hard build failure when the file is absent; the copy now happens with the rest of the example and the install is guarded. `setup.sh` assumed `.venv/bin/activate`, which does not exist under Git Bash on Windows — `.venv/Scripts/activate` is now used as a fallback. Fix contributed by @saurabhhhcodes in #149/#171/#177
- Remote code execution in `Crewai-agents/trip_planner` (issues #111, #138). `CalculatorTools.calculate` ran `eval()` on an expression written by the LLM, so a prompt-injected `__import__('os').system(...)` executed on the host. Replaced with an `ast`-based evaluator that walks only arithmetic nodes; anything else is refused, and exponents are bounded so `9**9**9` cannot hang the agent
- Cross-user session hijacking in `Composio/linkedln` (issue #130). One module-level `LinkedInAgent` was shared by every chat sender and its `user_id` was reassigned on each "connect" message, so a second user connecting redirected the first user's posts and tokens to their own LinkedIn account. Instances are now created per sender
- `NameError` crash in `mcp-agents/Github MCP Agent` (issue #134). The manual-token path read `scopes` outside the `if` that binds it, so any token GitHub does not report scopes for — fine-grained PATs and App tokens — crashed the handler instead of authenticating. Absent scopes are now treated as "not introspectable" and skip the classic-scope check
- `frontend-integration` could hang forever (issue #148). Both agent POST calls omitted `timeout`, so an agent that accepted the connection but never replied held the Flask worker indefinitely. Added a 30s timeout, and narrowed the bare `except` in the health check
- CI `test` job never ran any tests. `find ... | grep -q .` killed `find` with SIGPIPE, and under `set -o pipefail` that failure became the `if` condition, so every run reported "No test files found". Replaced with [`.github/scripts/run-example-tests.sh`](.github/scripts/run-example-tests.sh), which builds a virtualenv per example from that example's `requirements.txt` — a single root `pytest` cannot work because the examples have conflicting dependency sets. All seven suites now run (234 tests)
- CI `changelog-check` rejected large PRs that *did* update the changelog. `echo "$CHANGED" | grep -q '^CHANGELOG.md$'` dies with SIGPIPE once `grep` matches early and stops reading, and `set -o pipefail` turns that into a failed condition. Same root cause as the `test` job; replaced both pipelines with here-strings
- CI `review-required` never re-evaluated after a maintainer approved, because it only triggered on push-style PR events. Moved to [`review-required.yml`](.github/workflows/review-required.yml) with a `pull_request_review` trigger, and it now uses each reviewer's latest state so `CHANGES_REQUESTED` overrides an earlier approval
- CI `lint`, `format` and `typecheck` failed on unrelated changes: deleted files were passed to `ruff`/`mypy` (fixed with `--diff-filter=ACMR`), and `mypy` aborted with "Duplicate module" whenever a PR touched two files sharing a basename (now invoked per file)
- Pinned the repo-wide ruff selection in [`ruff.toml`](ruff.toml) to `E4`/`E7`/`E9`/`F`. CI installs the latest ruff, whose default rule set has grown well past what these examples were written against, so upstream releases retroactively failed PRs on untouched code
- `ag2-agents/payment-approval` and `ag2-agents/research-synthesis-team` could not run: ag2 1.0 removed the `autogen` module, a2a-sdk 0.4 removed `a2a.types.TextPart`, and `uagents-adapter` dropped `SingleA2AAdapter`. Pinned to the last compatible line and gave the sync tests an event loop
- `mcp-agents/ticketlens-agent` could not import: mcp 2.0 renamed `streamablehttp_client`. Pinned `mcp<2.0`
- `stripe-payment-agents/twitch-growth-agent` integration tests call `os._exit(0)`, terminating pytest mid-run with a success code and silently dropping the other 28 tests. Deselected by default via `pytest.ini`; still runnable with `pytest -m integration`
- `stripe-payment-agents/conversational-property-finder` could not start at all: it imports a `property_finder` package that does not exist anywhere in the repo (the directory was renamed without updating the imports, and a hyphenated directory can never be a package). Its `sys.path` bootstrap also ran *after* the import it was meant to enable. Now imports `asi1_agent` and `repliers_client` directly, with the path set up first. Added the missing `asi1_agent/.env.example` covering all 18 variables the code reads, and replaced README instructions that referenced `property_finder/` and the original author's local desktop path
- Five examples told users to `pip install -r requirements.txt` but shipped no such file: `mcp-agents/airbnb-mcp-agent`, `mcp-agents/calendar_chat_uagent`, `mcp-agents/gmail_chat_uagent`, `a2a-uAgents-Integration/.../shopping_agent`, and `Crewai-agents/Prep-for-a-meeting-Agent`. Each now has one derived from its actual imports, pinned consistently with its sibling examples. `shopping_agent` needed the same `a2a-sdk<0.4` and `uagents-adapter==0.6.2` pins as `ag2-agents`, since it imports `a2a.types.TextPart` and `SingleA2AAdapter`
- `fet-example/requirements.txt` omitted `cosmpy` and `requests`, both imported at runtime, and listed `Pillow` and `google-genai`, which the example never imports
- `pdf-summariser-example` shipped a `.env.example` and a README telling you to use it, but nothing ever called `load_dotenv`, so the file was ignored. `python-dotenv` was also missing from its requirements
- `Nike-products-agent/requirements.txt` asked for `notte` while the code imports `notte_sdk` and the README says `notte-sdk`. Installing `notte` does work (it depends on `notte-sdk`), but it pulls the whole agent framework for one SDK import
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
- GSSoC '26 program automation, now that the program has ended: `gssoc-label-bootstrap` and `gssoc-label-sync` workflows, [`.github/labels/gssoc-labels.json`](.github/labels/), `.github/scripts/create-gssoc-labels.sh`, and `docs/GSSOC.md`
- The contributor badge system that existed to support it: `award-contributor-badge` workflow, `.github/badges/` artwork, `contributors/BADGE_REGISTRY.json`, and `contributors/profile-badge-sync/`. Badge references removed from `CONTRIBUTING.md` and `contributors/README.md`; individual contributors' own credit lines in their agent READMEs are untouched
- `.github/scripts/create-fetch-tech-issues.sh`, a one-shot script that bulk-created the #54–#91 issue batch. It is not wired into CI and re-running it would duplicate issues
- Generic contributor infrastructure is kept: `CONTRIBUTING.md`, issue and PR templates, `CODEOWNERS`, `MAINTAINERS`, `stargazer-gate`, `review-required` and the `contributors/` folder
- Committed build artifacts: a 5,310-file Python virtualenv under `frontend-integration/venv/`, 2,265 `__pycache__` entries, 15 `.DS_Store` files, and uAgents runtime state (`duffel-agent/state/*.sqlite`, `agent1q*_data.json`)
- Two dead files: an empty `duffel-agent/runner.py` and `mcp-agents/events-finder-mcp-agent/new-adapter.py`, an unreferenced orphan importing a `.protocol` module that does not exist
- The blanket `*.json` rule in `.gitignore`, replaced with credential-specific patterns; it silently dropped legitimate project files. `.dockerignore` is no longer ignored either
- Tracked `Crewai-agents/*/.env` files, renamed to `.env.example` (both only ever held empty placeholders, verified across the full history)