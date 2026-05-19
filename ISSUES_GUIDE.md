# Issues Guide

Use this guide to raise clear, actionable issues for this repository.

## Contributor program

This repo is part of the **Fetch.ai Innovation Lab open-source program**. Community members can:

1. **Pick labeled issues** — `good first issue`, `help wanted`, `challenge`, or **`fetch-tech`** (uAgents / Agentverse / ASI:One)
2. **Build new agents** under [`contributors/<your-agent-name>/`](contributors/README.md)
3. **Open a PR** that passes CI and receives maintainer approval before merge

### Fetch.ai stack issues (full briefs)

Issues tagged **`fetch-tech`**, **`uagents`**, **`agentverse`**, or **`asi-one`** focus on Innovation Lab patterns — chat protocol, mailbox deploy, ASI:One, FET/Skyfire payments, A2A bridges, and multi-agent bureaus. Each issue includes acceptance criteria and repo references.

Browse: [fetch-tech issues](https://github.com/fetchai/innovation-lab-examples/issues?q=is%3Aissue+is%3Aopen+label%3Afetch-tech)

See [contributors/README.md](contributors/README.md) for the full contributor workflow.

## When to Raise an Issue

Open an issue if you find:

- A bug in behavior
- Runtime or setup errors
- Wrong file/folder path in docs or code
- Incorrect code logic or broken example flow
- Missing or outdated instructions
- You want to **claim** a challenge (real-time booking, payments, etc.) before opening a PR

## Before You Open an Issue

1. Search existing issues to avoid duplicates.
2. Test with the latest `main` branch.
3. Collect logs, traceback, and reproduction steps.
4. For new agents, comment on a challenge issue or use the **Contributor — good first issue** / **Challenge — real-time AI agent** templates.

## Issue Types

- **Bug Report**: Something is broken or not working as expected.
- **Error Report**: Runtime/import/install error with logs.
- **Wrong Path Report**: Incorrect file path, import path, or docs path.
- **Code Issue Report**: Wrong logic, incorrect implementation, or bad output.
- **Feature request**: New capability or repo improvement.
- **Contributor — good first issue**: Starter tasks for new contributors.
- **Challenge — real-time AI agent**: Flight/hotel/payment/live-booking style agents under `contributors/`.

## What to Include

- Clear title
- Expected behavior
- Actual behavior
- Exact steps to reproduce
- File path(s) affected
- Error message / stack trace
- Environment details (OS, Python version)
- Screenshots (if useful)
- For agent challenges: proposed APIs, sandbox mode, and target folder name

## Fast Issue Creation (CLI)

```bash
gh issue create --title "Bug: short title" --body "Steps, expected, actual, logs"
```

## Useful Links

- Contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Community agents folder: [contributors/README.md](contributors/README.md)
- Agent README template: [docs/AGENT_README_TEMPLATE.md](docs/AGENT_README_TEMPLATE.md)
- Branch protection (maintainers): [.github/BRANCH_PROTECTION.md](.github/BRANCH_PROTECTION.md)
