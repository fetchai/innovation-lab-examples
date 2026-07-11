# Agent Contribution Guide

This repository is open for community contributions.  
Any user can submit a new agent example through a pull request.

This guide explains how to add agents in a consistent, review-friendly format.

## Getting Started

1. Fork the repository and clone your fork.
2. Create a feature branch from `main`.
3. Keep changes focused (one feature/fix per PR).
4. Use `./setup.sh <example-folder>` on macOS/Linux/Git Bash/WSL or `.\setup.ps1 <example-folder>` on Windows PowerShell to quickly test any example locally.

```bash
git checkout -b feat/short-description
```

Star this repository before raising a PR (CLI):

```bash
gh repo star fetchai/innovation-lab-examples
```

## Who Can Add an Agent?

- Anyone can contribute an agent example (community members, students, builders, and teams).
- You do not need to be part of the core team to open a PR.
- The PR author must star this repository before opening a PR.
- All contributions are reviewed before merge.

## How to Add a New Agent Example

### Community contributors (default)

**All community-submitted agents must live under `contributors/<your-agent-name>/`.**  
Read the full guide: [contributors/README.md](contributors/README.md).

When adding a new community agent:

1. Create `contributors/<your-agent-name>/` (do **not** add new top-level folders at the repo root).
2. Add source code and dependency files.
3. Add a complete `README.md` (use [docs/AGENT_README_TEMPLATE.md](docs/AGENT_README_TEMPLATE.md)).
4. Add demo assets (image/GIF).
5. Add `.env.example` if env vars are required.
6. Update [contributors/CHANGELOG.md](contributors/CHANGELOG.md).
7. Add your agent to the **Community Contributors** table in the root [README.md](README.md).

Recommended folder layout:

```text
contributors/<your-agent-name>/
  README.md
  requirements.txt
  .env.example
  agent.py
  assets/
    demo.png
```

### Maintainers / official examples

Fetch.ai team examples may be added at the repository root (e.g. `gemini-quickstart/`, `stripe-payment-agents/`) following the same README and quality standards.

## Tagging and Categorization

Every example should be tagged in its README with a difficulty level and category to help users navigate the repository.

**Difficulty levels:**

- **Beginner** — single agent, minimal setup, no external services
- **Intermediate** — API integrations, payment protocols, multi-file agents
- **Advanced** — multi-agent systems, Web3, complex orchestration

**Categories** (use one or more):

`Getting Started` · `LLM` · `A2A` · `MCP` · `Payments` · `RAG` · `Multi-Agent` · `Web3` · `Integration` · `Frontend` · `Tooling`

Add these to the top of your example README:

```markdown
- **Category:** `LLM`, `Payments`
- **Difficulty:** Intermediate
```

When you add a new example, also add it to the examples index table in the root [README.md](README.md).

## Local Development Checks (CLI)

Many examples are Python-based. Run these checks before opening a PR.

Install `ruff` (if needed):

```bash
python -m pip install ruff
```

Lint:

```bash
ruff check .
```

Format:

```bash
ruff format .
```

Optional auto-fix:

```bash
ruff check . --fix
```

## `.env` and Secrets Policy

- Never commit real secrets, API keys, private keys, or tokens.
- If your example uses environment variables, include a `.env.example` file.
- Document each variable in README with a short description.
- Add `.env` to `.gitignore` in project folders where needed.

Example:

```env
# .env.example
OPENAI_API_KEY=your_api_key_here
AGENTVERSE_API_KEY=your_agentverse_key_here
```

## README Quality Requirements

Every new or updated example should have a clear README. At minimum include:

- What the project does (2-4 lines).
- Prerequisites and installation steps.
- `.env` variable setup section.
- How to run the project.
- Expected output or behavior.
- Troubleshooting notes (if relevant).
- Agent profile link (if deployed/published).

Use this ready-to-copy template:
- `docs/AGENT_README_TEMPLATE.md`

## Demo and Agent Profile Requirements

To make examples easy to verify, please add:

- A demo image or GIF (recommended: ASI demo screenshot) in the example README.
- A link to the deployed or published agent profile (for example, Agentverse profile URL), when available.

Recommended asset path:

```text
<example-folder>/assets/demo.png
```

Recommended README snippet:

```markdown
## Demo
![ASI Demo](./assets/demo.png)

## Agent Profile
[View Agent Profile](https://agentverse.ai/)
```

## Pull Request Checklist

- Keep PRs small and scoped to one improvement.
- Add or update README for the agent.
- Include setup or testing notes for reviewers.
- Add `.env.example` if environment variables are required.
- Include demo image/GIF and agent profile link when applicable.
- Run `ruff check .` and `ruff format .` before submitting.
- Add a changelog entry:
  - Community agents: [contributors/CHANGELOG.md](contributors/CHANGELOG.md)
  - Other changes: root [CHANGELOG.md](CHANGELOG.md)
- Ensure all CI checks pass on `pull_request`:
  - `stargazer-gate`
  - `contributor-path-check`
  - `changelog-check`
  - `review-required`
  - `lint`
  - `format`
  - `typecheck`
  - `validate-architecture`
  - `test`
- Reference related issues when applicable.

## How to Raise Issues

- Use `ISSUES_GUIDE.md` before creating an issue.
- Choose the matching issue template:
  - Bug report
  - Error report
  - Wrong path report
  - Code issue report
  - Feature request
- Add clear reproduction steps, affected path, and logs.

PRs also use a default template:
- `.github/pull_request_template.md`

## Security Reporting

- Do not open public issues for security vulnerabilities.
- Follow `SECURITY.md` to report vulnerabilities responsibly.
- Never include real secrets (keys/tokens/private credentials) in issues or PRs.

## Merge Policy

- Direct merges to `main` are not allowed.
- **External contributors:** PRs need at least one approving review (`review-required` CI).
- **Maintainers** (Fetch.ai org, repo `write`/`admin`, or listed in [.github/MAINTAINERS](.github/MAINTAINERS)) **skip** `review-required` and `stargazer-gate` — you can merge your own PRs after other CI checks pass.
- Enable branch protection on `main` — see [.github/BRANCH_PROTECTION.md](.github/BRANCH_PROTECTION.md).

## Contributor badges (after merge)

When a **fork contributor’s PR is merged** with changes under `contributors/`:

1. The [**Award Contributor Badge**](.github/workflows/award-contributor-badge.yml) workflow adds the badge to the agent README and [contributors/BADGE_REGISTRY.json](contributors/BADGE_REGISTRY.json).
2. A comment on the PR includes markdown for your **GitHub Profile README**.
3. For **automatic** profile README updates, install the one-time workflow from [contributors/profile-badge-sync/](contributors/profile-badge-sync/README.md) in your `username/username` repo.
- Community users can open PRs; merge happens only after review approval and passing CI.
- New community agent folders must be under `contributors/` (`contributor-path-check`).
- Branch protection on `main` should require:
  - Required pull request reviews: **1** (dismiss stale reviews on new commits: recommended)
  - Required status checks:
    - `stargazer-gate`
    - `contributor-path-check`
    - `changelog-check`
    - `review-required`
    - `lint`
    - `format`
    - `typecheck`
    - `validate-architecture`
    - `test`

## Docker Support

If your example benefits from containerization, include a `Dockerfile` in the example folder. The repository also provides a root-level `Dockerfile` that can run any example:

```bash
docker build --build-arg EXAMPLE=your-example-folder -t your-example .
docker run --env-file your-example-folder/.env your-example
```

## Useful Links

- Innovation Lab docs: <https://innovationlab.fetch.ai/resources/docs/intro>
- Agentverse: <https://agentverse.ai/>
- ASI:One: <https://asi1.ai/>
