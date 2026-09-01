<p align="center">
  <img src="assets/banner.png" alt="TripMate — AI Travel Agent" width="720">
</p>

<h1 align="center">TripMate</h1>

<p align="center">
  Your AI travel companion — search, compare & book flights, hotels, and packages in one conversation.
</p>

<p align="center">
  <a href="https://asi1.ai/chat">Try on ASI:One</a> ·
  <a href="https://mcp.lastminute.com/mcp">lastminute.com MCP</a> ·
  <a href="https://innovationlab.fetch.ai">Fetch.ai Innovation Lab</a>
</p>

---

## What is this?

**TripMate** is a personal AI travel agent that helps you plan and book trips — without jumping between tabs, apps, or websites.

Ask in plain language. The agent searches real-time flights, hotels, and flight + hotel packages via [lastminute.com MCP](https://mcp.lastminute.com/mcp), then shows results as **interactive cards** you can tap, review, and book.

No forms. No endless scrolling. Just tell it where you want to go.

---

## What can it do?

✈️ **Search flights** — real-time pricing across global airlines  
🏨 **Search hotels** — star rating, amenities, and location filters  
🧳 **Flight + Hotel packages** — bundled deals in a single request  
🎴 **Interactive cards** — carousel, review, forms, and one-tap booking links  
🔍 **Smart filters** — times, airports, stops, airlines, price, stars, facilities  
⭐ **Smart recommendations** — best options ranked by price, duration & convenience  
🔗 **Book instantly** — secure deeplinks straight to lastminute.com in a new tab

---

## Example queries

### Flights

```
Find flights from Milan to London on December 15th
```

```
Show me direct morning flights from Rome to Paris under 150 EUR
```

### Hotels

```
Search for a 4-star hotel in London with a pool, checking in Sep 20 and checking out Sep 23
```

### Flight + Hotel packages

```
Find me flight and hotel packages from Rome to Madrid for 3 nights, checking in on Sep 20
```

---

## How it works

1. **You ask** — in natural language
2. **Agent searches** — lastminute.com MCP returns live results
3. **You pick** — flights, hotels, or packages in interactive cards
4. **You confirm** — review card with summary rows
5. **You book** — redirect card opens lastminute.com in a new tab

---

## Card flow

| Step | Card type | What you do |
|------|-----------|-------------|
| Search | `form` / `carousel` | Enter trip details or pick an option |
| Confirm | `review` | Approve or cancel |
| Book | `custom` | Tap to open booking page (new tab) |

---

## Project structure

```
├── agent.py              # uAgent entry point (mailbox + chat protocol)
├── prompt.md             # ASI1 system prompt
├── requirements.txt
├── assets/
│   ├── banner.png
│   └── logo.png
└── tripmate/
    ├── handler.py        # Chat handler + card actions
    ├── cards.py          # ASI:One card builders
    ├── results.py        # MCP result → carousel payloads
    ├── mcp_client.py     # lastminute MCP bridge (mcp-remote)
    ├── graph.py          # LangGraph + ASI1 agent
    └── ...
```

---

## Run locally

### Prerequisites

- Python 3.10+
- Node.js + `npx` (for `mcp-remote` bridge to lastminute MCP)

### Setup

```bash
git clone https://github.com/fetchai/innovation-lab-examples.git
cd innovation-lab-examples/dynamic-ui-on-asi1/tripmate
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example env file and add your API key:

```bash
cp .env.example .env
# Edit .env and set ASI_ONE_API_KEY
```

### Start the agent

```bash
python agent.py
```

The agent runs on `http://0.0.0.0:8000` with mailbox enabled for Agentverse / ASI:One.

### Deploy on Render

1. Connect the GitHub repo and set **Python version** to `3.11` (or use `runtime.txt`).
2. **Start command:** `python agent.py`
3. Add environment variable:
   - `ASI_ONE_API_KEY` — your ASI:One API key

Render sets `PORT` automatically; the agent reads it from the environment.

---

## Built with

| | |
|---|---|
| 🤖 **Agent Framework** | [Fetch.ai uAgents](https://fetch.ai) |
| 💬 **Chat Platform** | [ASI:One](https://asi1.ai) |
| 🧠 **LLM** | [ASI1](https://asi1.ai) via LangGraph |
| ✈️ **Travel Data** | [lastminute.com MCP Server](https://mcp.lastminute.com/mcp) |

---

## Supported languages

English · Italian · Spanish · French · German · Dutch · Polish · Swedish · Danish · Norwegian · Finnish

---

## Try it

👉 **[asi1.ai/chat](https://asi1.ai/chat)** — start a conversation and ask about your next trip.

---

## Source

Adapted from [gautammanak1/TripMate](https://github.com/gautammanak1/TripMate).

---

<p align="center">
  Built with ❤️ using Fetch.ai & lastminute.com
</p>

<p align="center">
  <img src="assets/logo.png" alt="TripMate logo" width="64">
</p>
