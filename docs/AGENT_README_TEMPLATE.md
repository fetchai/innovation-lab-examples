# Agent README Template

Use this template when adding a new agent example to this repository.

**Community contributors:** create your agent under `contributors/<your-agent-name>/` and follow [contributors/README.md](../contributors/README.md).

---

## 1) Project Title

`<agent-name>`

Short one-line summary of what this agent does.

## 2) Overview

Describe the problem this agent solves and the expected use case.

- **Category:** `<e.g., automation, research, payments, MCP>`
- **Tech stack:** `<Python/uAgents/LLM/API/etc.>`
- **Status:** `<prototype | demo | production-ready>`

## 3) Features

- Feature 1
- Feature 2
- Feature 3

## 4) Prerequisites

- Python `<version>`
- pip / uv
- API keys (if required)

## 5) Installation

```bash
git clone <your-fork-url>
cd <agent-folder>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6) Environment Variables

Create a `.env` file using `.env.example`.

```bash
cp .env.example .env
```

Example `.env.example` (keep only variables your agent actually uses):

```env
# Optional: required only if your agent uses ASI:One
ASI1_API_KEY=your_asi1_api_key_here
# Optional: required only if your agent connects to Agentverse
AGENTVERSE_API_KEY=your_agentverse_key_here
```

### Variables

- `ASI1_API_KEY` (optional): Used for ASI:One LLM requests.
- `AGENTVERSE_API_KEY` (optional): Used for Agentverse access.

## 7) Run the Agent

```bash
python agent.py
```

Include optional commands if your project has multiple entry points.

## 8) Expected Output

Describe what users should see after running the agent.

Example:

- Agent starts successfully
- Registers or connects to expected service
- Returns response for sample input

## 9) Demo

Add at least one demo image or GIF.

```markdown
![ASI Demo](./assets/demo.png)
```

## 10) Agent Profile

If deployed or published, add the agent profile URL.

```markdown
[View Agent Profile](https://agentverse.ai/)
```

## 11) Architecture (Optional but Recommended)

Briefly explain important components and data flow.

## 12) Troubleshooting

List common issues and fixes.

- Missing env var error -> Check `.env` values.
- Dependency conflict -> Recreate virtual environment.

## 13) License

Mention the license if different from repository default.

---

## Quick Checklist Before PR

- README updated using this template.
- `.env.example` added if env vars are needed.
- Demo image/GIF added in `assets/`.
- Agent profile link included (if available).
- `ruff check .` passed.
- `ruff format .` applied.
