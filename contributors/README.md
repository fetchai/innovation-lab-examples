# Community Contributors — Agent Examples

This folder is the **home for all community-submitted agent examples**. If you are contributing a new agent to this repository, create it here — not at the repository root.

Maintained examples (Fetch.ai team) live in top-level folders such as `fetch-hackathon-quickstarter/`, `gemini-quickstart/`, etc. **Community PRs for new agents must go under `contributors/<your-agent-name>/`.**

---

## Quick start

1. **Star** the repository (required for CI — see [CONTRIBUTING.md](../CONTRIBUTING.md)).
2. **Fork** and branch from `main`:
   ```bash
   git checkout -b feat/my-agent-name
   ```
3. **Create your agent folder**:
   ```text
   contributors/<your-agent-name>/
     README.md
     requirements.txt
     .env.example          # if API keys are needed
     agent.py              # or your entry script
     assets/
       demo.png            # screenshot or GIF (recommended)
   ```
4. **Copy the README template**: [docs/AGENT_README_TEMPLATE.md](../docs/AGENT_README_TEMPLATE.md)
5. **Add a changelog entry** in [contributors/CHANGELOG.md](./CHANGELOG.md).
6. **Update the root README** — add your agent to the **Community Contributors** table in [README.md](../README.md).
7. **Open a PR** — your PR must pass CI and receive **at least one review** before merge.

---

## What makes a good contributor agent?

| Area | Guidance |
|------|----------|
| **Purpose** | Solves a clear, real-world task (booking, search, payments, automation, etc.) |
| **Runnable** | Works locally with documented setup; include `.env.example` |
| **Fetch.ai stack** | Prefer **uAgents**, **ASI:One**, **Agentverse**, **A2A**, or **MCP** where relevant |
| **Docs** | Complete README with install, env vars, run steps, and demo |
| **Safety** | No real secrets in code; read-only or sandbox APIs for demos when possible |

---

## Real-time / transactional agents (challenge ideas)

Looking for inspiration? These are high-value patterns the community is encouraged to build (see open issues):

- **Flight booking** — search, compare, hold or mock-book via a travel API (e.g. Duffel, Amadeus sandbox)
- **Hotel booking** — availability, pricing, reservation flow with clear mock/sandbox mode
- **Payment gateway** — Stripe or similar with a gated premium step (see `stripe-payment-agents/` for patterns)
- **Event tickets** — live inventory + checkout deep links (see `mcp-agents/ticketlens-agent/`)
- **Multi-step workflows** — planner → payment → confirmation with chat protocol

Reference examples elsewhere in the repo:

- [flight-tracker-openai-workflow-agent](../flight-tracker-openai-workflow-agent/)
- [stripe-payment-agents](../stripe-payment-agents/)
- [mcp-agents/ticketlens-agent](../mcp-agents/ticketlens-agent/)
- [contributors/community_agent](./community_agent/) — community growth / events agent

---

## Changelog

Every non-documentation change under `contributors/` must update [contributors/CHANGELOG.md](./CHANGELOG.md). The root [CHANGELOG.md](../CHANGELOG.md) is updated by maintainers when we cut releases.

---

## CI checks for contributor PRs

Your pull request must pass:

| Check | What it does |
|-------|----------------|
| `stargazer-gate` | PR author has starred the repo |
| `contributor-path-check` | New agent folders are only under `contributors/` |
| `changelog-check` | `contributors/CHANGELOG.md` updated when you change code |
| `review-required` | At least one approving review — **skipped for maintainers** |
| `lint` / `format` / `typecheck` | Python quality on changed files |
| `validate-architecture` | Required repo files present |
| `test` | Runs pytest when tests exist |

**PRs cannot be merged without review approval** when branch protection is enabled (see [.github/BRANCH_PROTECTION.md](../.github/BRANCH_PROTECTION.md)). Maintainers with repo write access skip this check.

---

## Contributor badge (after your PR merges)

1. Badge is added to your agent `README.md` under `contributors/<your-agent>/`
2. You are listed in [BADGE_REGISTRY.json](./BADGE_REGISTRY.json)
3. Install [profile-badge-sync](./profile-badge-sync/README.md) in your `GitHubUsername/GitHubUsername` repo for **automatic** profile README badge, or paste the markdown from the merge comment.

---

## Need help?

- [CONTRIBUTING.md](../CONTRIBUTING.md) — full contribution policy
- [ISSUES_GUIDE.md](../ISSUES_GUIDE.md) — how to file bugs and pick up tasks
- [Innovation Lab docs](https://innovationlab.fetch.ai/resources/docs/intro)
- Comment on an issue or ask in your PR — maintainers are happy to guide you

---

## Existing community agents

| Agent | Description |
|-------|-------------|
| [community_agent](./community_agent/) | AI community growth agent for events, conferences, and hackathons |
| [gemini-research-agent](./gemini-research-agent/) | Multi-agent research and summarization assistant powered by Google Gemini |