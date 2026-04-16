---
name: fetch-agents
description: Call Fetch.ai Agentverse agents by address. Search the Agentverse marketplace, browse a curated catalog of top agents (Tavily Search, ASI1-Mini, DALL-E 3, Technical Analysis, Asset Signal, Translator, Statistics, Github), and send ChatMessages to any agent. Use when working with Fetch.ai, Agentverse, uAgents, decentralized AI agents, or when the user wants to discover or message an agent on the Fetch.ai network.
homepage: https://github.com/fetchai/innovation-lab-examples/tree/main/openclaw/agentverse-caller
metadata:
  {
    "openclaw": {
      "emoji": "🤖",
      "requires": { "bins": ["python3"], "env": ["AGENTVERSE_API_KEY"] },
      "primaryEnv": "AGENTVERSE_API_KEY",
      "os": ["darwin", "linux"],
      "install": [
        { "id": "uagents", "kind": "uv", "package": "uagents", "label": "Install uagents (uv)" },
        { "id": "uagents-core", "kind": "uv", "package": "uagents-core", "label": "Install uagents-core (uv)" }
      ]
    }
  }
---

# Fetch Agents

Send queries to Fetch.ai Agentverse agents and return the agent's reply in natural language.

## CRITICAL RULES — READ FIRST

1. **NEVER show the user a bash command, a script path, or anything that looks like `python3 ...` or `bash ...`.** Those are for YOU to run internally. The user is chatting in Telegram/CLI and wants plain language.
2. **If the user asks "how do I use X" or "how does this work" — DO NOT respond with commands.** Respond with plain-English example prompts, like: *"Just ask me things like 'get trading signals for TSLA' or 'translate hello to French' and I'll take care of the rest."*
3. **When the user makes an actual request (get signals, translate, etc.), run the script yourself and reply with the agent's answer.** Format it nicely. Do not tell them to run anything.
4. The only time you reveal paths or commands is if the user explicitly asks for debug/diagnostic info.

## How to answer common user questions

- *"How do I use this?" / "What can this do?"* → Explain in plain English: it calls Fetch.ai Agentverse agents for real-time data, translations, stats, stock signals, image generation, etc. Give 3-4 example prompts the user can try (in natural language, NOT bash).
- *"What agents are available?" / "Show me the catalog"* → Run `catalog.py` and format the result as a friendly list.
- *"Find a [topic] agent"* → Run `search.py` and return the top matches in plain text.
- *Any actual task* (signals, translation, stats, etc.) → Run `fire.sh`, tell the user to hold on ~40 seconds, then run `result.sh` and reply with the agent's answer in your own words.

## Natural-language prompts the user might send

- "get me trading signals for TSLA" → call `signals` agent
- "what does ASI1-Mini think about quantum computing?" → call `asi` agent
- "translate 'hello world' to Japanese" → call `translate` agent
- "compute stats for 1, 2, 3, 4, 5" → call `stats` agent
- "stock analysis on AAPL" → call `stocks` agent
- "search the agentverse for weather agents" → run marketplace search
- "latest news on Fetch.ai" → call `search` (Tavily web search) agent
- "get github info for fetchai" → call `github` agent
- "generate an image of a cyberpunk cat" → call `image` agent
- "call the Crypto Fear & Greed Agent for the current index" → agent by name, auto-searched

## Agent Shortcuts

| Key | Agent | Purpose |
|-----|-------|---------|
| `stats` | Average Agent | Mean, median, mode, variance, std dev |
| `signals` | Asset Signal | BUY/SELL/WAIT trading signals |
| `stocks` | Technical Analysis | Stock SMA/EMA/WMA indicators |
| `image` | DALL-E 3 Generator | Image generation from text |
| `asi` | ASI1-Mini | General-purpose AI chat |
| `translate` | OpenAI Translator | Text translation |
| `github` | Github Organisation | GitHub org metadata |
| `search` | Tavily Search | Web search (NOT marketplace search) |

---

## Internal Execution (for you, the agent, not the user)

The following are the commands **YOU** run with the exec tool. Never show these to the user.

### Show the curated catalog
Runs in <5 seconds. Use for "what agents are available?" type questions.
```bash
python3 {baseDir}/scripts/catalog.py
```

### Search the Agentverse marketplace
Runs in <5 seconds. Use when the user wants to find agents by topic.
```bash
python3 {baseDir}/scripts/search.py "query" -n 10
```

### Call an agent (two-step, ~40 seconds total)
Calling an Agentverse agent takes 30-60 seconds. Use the two-step pattern:

**Step 1 — Fire (returns instantly):**
```bash
bash {baseDir}/scripts/fire.sh <shortcut-or-address-or-name> "user's query"
```

Accepts: a shortcut key from the table above, a full `agent1q...` address, or an agent name (auto-searched).

**Step 2 — Tell the user** something like: "Calling the agent, this takes about 30-60 seconds..."

**Step 3 — After 30-60 seconds, read the result:**
```bash
bash {baseDir}/scripts/result.sh
```

Then reply to the user with the agent's answer, rewritten in your own words / formatted nicely. Never show the raw command.

### Rules

1. Resolve `{baseDir}` to the absolute path of this SKILL.md's parent directory.
2. Single absolute-path command per exec call. No `cd`, no `&&`.
3. The user never sees the commands or paths. Just give them the agent's answer.
