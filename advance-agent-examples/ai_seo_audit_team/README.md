![uagents](https://img.shields.io/badge/uagents-4A90E2) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4) ![adk](https://img.shields.io/badge/adk-4285F4) ![google](https://img.shields.io/badge/google-4285F4) ![gemini](https://img.shields.io/badge/gemini-4285F4)

# AI SEO Audit Team

An autonomous, multi-agent SEO audit workflow that analyzes web pages, researches competitive SERPs, and produces actionable optimization reports.

## What This Agent Does

**Multi-turn chat with memory** Conversations persist even if the agent restarts or crashes.

**Durable execution** Thanks to ADK session management, the agent maintains conversation context across requests.

**uAgents chat compatibility** Works out-of-the-box with uAgents / ASI:One chat UIs and agent-to-agent messaging.

**End-to-end SEO analysis** Takes a webpage URL, crawls the live page with Firecrawl, researches real-time SERP competition, and produces a prioritized SEO optimization report.

**Multi-agent workflow** Three specialized agents work sequentially: Page Auditor → SERP Analyst → Optimization Advisor, each contributing to the final comprehensive report.

**Session-aware conversations** Each chat session is tracked and stored using ADK InMemorySessionService.

## Technology Stack

This agent is built using **uAgents** for chat protocol communication and agent-to-agent messaging, **Google ADK (Agent Development Kit)** for agent execution with SequentialAgent workflow, **Gemini 2.5 Flash** model for LLM processing, **Firecrawl MCP** for accurate web page scraping, and **Google Search** tool for competitive SERP analysis. The agent uses uAgents Protocol for receiving and sending messages, ADK Runner for executing the multi-agent workflow with tool integration, and InMemorySessionService for session management. The workflow consists of three sequential agents: Page Auditor (scrapes and audits pages), SERP Analyst (researches competitors), and Optimization Advisor (synthesizes findings into actionable reports).

## How It Works

1. **You provide a URL** → Agent receives it via chat protocol
2. **Page Auditor scrapes** → Uses Firecrawl to extract page structure, content, and technical signals
3. **SERP Analyst researches** → Uses Google Search to analyze competitors for the discovered keyword
4. **Optimization Advisor reports** → Combines audit + SERP insights into a prioritized Markdown report

## Example Queries

**Question 1:**
```
Audit https://example.com
```

**Question 2:**
```
Please analyze https://mywebsite.com/blog/post for SEO optimization opportunities
```

## What You Can Ask

- SEO audits for any public webpage URL
- On-page SEO analysis (titles, headings, content depth, links)
- Competitive SERP research and analysis
- Keyword strategy recommendations
- Technical SEO issue identification
- Content optimization opportunities
- Prioritized optimization roadmaps

## Requirements

- Python 3.10+
- Node.js (for Firecrawl MCP server via npx)
- Google API Key (Gemini API)
- Firecrawl API Key ([get one here](https://firecrawl.dev/app/api-keys))
