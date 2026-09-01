# Dynamic UI on ASI:One

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![asi1](https://img.shields.io/badge/asi1-000000) ![cards](https://img.shields.io/badge/interactive--cards-22C55E) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

Agents that reply with **ASI:One interactive cards** instead of a wall of text. Each example is a mailbox-enabled uAgent you can chat with on [ASI:One](https://asi1.ai).

| Example | What it shows | Tech |
|---------|----------------|------|
| [tripmate](tripmate/) | Search, compare, and book flights, hotels, and packages via lastminute.com MCP | uAgents, LangGraph, ASI1, MCP, carousel / review / form cards |
| [news-card-agent](news-card-agent/) | Live news as a scrollable card list with tappable article detail | uAgents, Tavily, ASI1, custom element-tree cards |

## Quickstart

```bash
# From the repo root
./setup.sh dynamic-ui-on-asi1/tripmate
# or
./setup.sh dynamic-ui-on-asi1/news-card-agent
```

Then follow the example README for env vars and `python agent.py`.

## Resources

- [Agent-driven interactive cards](https://docs.agentverse.ai/documentation/advanced-usages/agent-driven-interactive-cards)
- [Element-tree primitives](https://docs.agentverse.ai/documentation/advanced-usages/element-tree-primitives)
- [ASI:One card playground](https://asi1.ai/developer/card-playground)
