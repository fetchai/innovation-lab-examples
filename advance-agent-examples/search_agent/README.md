# Search Agent 🔍

An AI assistant with Google Search capability. Built with [Google ADK](https://google.github.io/adk-docs/) and [Fetch.ai uAgents](https://uagents.fetch.ai/docs), this agent can search the web for current information, facts, weather, time, and real-time data.

## Features

- **Multi-turn chat with memory**: Conversations persist even if the agent restarts or crashes
- **Durable execution**: Thanks to ADK session management, the agent maintains conversation context across requests
- **uAgents chat compatibility**: Works out-of-the-box with uAgents / ASI:One chat UIs and agent-to-agent messaging
- **Search-powered assistant**: Powered by Gemini 3 Pro Preview with Google Search tool for real-time information, current facts, weather, news, and up-to-date data retrieval
- **Session-aware conversations**: Each chat session is tracked and stored using ADK InMemorySessionService

## Prerequisites

- Python 3.10+
- Google Cloud Project with:
  - Gemini API enabled
  - API key for authentication

## Installation

### Local Setup

```bash
pip install -r requirements.txt
```

### Environment Variables

Copy the example environment file and update with your values:

```bash
cp .env.example .env
# Then edit .env with your API key
```

Or set the environment variables directly:

```bash
export GOOGLE_API_KEY=your-gemini-api-key
# OR
export GEMINI_API_KEY=your-gemini-api-key
```

Get your API key from: https://aistudio.google.com/app/apikey

## Usage

### Run Locally

```bash
python agent.py
```

The agent will start on `http://0.0.0.0:8006`

### Example Queries

Once running, send messages to the agent via Agentverse or direct chat protocol:

```
"What's the latest AI news?"
"What's the weather in Delhi?"
"What time is it in New York?"
"Find recent developments in quantum computing"
"What are the current stock prices for Apple?"
"Search for information about climate change"
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              uAgents Chat Protocol                      │
│              (Message Handler)                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ADK Runner                                  │
│              (Agent Execution with Tools)                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ADK Agent                                   │
│              Model: gemini-3-pro-preview                │
│              Tools: google_search                        │
│              Session: InMemorySessionService             │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
search_agent/
└── agent.py              # Main agent file with uAgents integration and Google Search
```

## Technology Stack

- **uAgents**: Chat protocol communication and agent-to-agent messaging
- **Google ADK (Agent Development Kit)**: Agent execution
- **Gemini 3 Pro Preview**: LLM processing
- **Google Search**: Real-time web search capabilities

## What You Can Ask

- Current news and events
- Weather information
- Time in different cities
- Latest facts and data
- Real-time information
- Stock prices
- Any question requiring current information
