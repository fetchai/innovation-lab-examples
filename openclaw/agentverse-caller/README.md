# Agentverse Caller (OpenClaw skill)

OpenClaw skill for calling [Fetch.ai](https://fetch.ai) [Agentverse](https://agentverse.ai) agents: search the marketplace, browse a curated catalog, and send chat messages by shortcut, name, or address.

**Location in this repo:** [`innovation-lab-examples/openclaw/agentverse-caller/`](https://github.com/fetchai/innovation-lab-examples/tree/main/openclaw/agentverse-caller) — see also [`openclaw/README.md`](../README.md).

## Contents

| Path | Purpose |
|------|---------|
| [`SKILL.md`](SKILL.md) | OpenClaw skill definition (metadata, usage rules, internal commands) |
| [`scripts/`](scripts/) | `catalog.py`, `search.py`, `call.py`, `fire.sh`, `result.sh`, `ask.sh` |
| [`references/`](references/) | Extra docs (e.g. mailbox setup) |

## Requirements

- Python 3 with `uagents` / `uagents-core` (see install hints in `SKILL.md` frontmatter)
- `AGENTVERSE_API_KEY` in the environment ([Agentverse API keys](https://agentverse.ai/profile/api-keys))

## Quick test

From this directory:

```bash
export AGENTVERSE_API_KEY="your_key"
python3 scripts/catalog.py
```

Full behaviour for OpenClaw is described in **`SKILL.md`**.
