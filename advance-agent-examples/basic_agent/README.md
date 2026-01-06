# Basic Chat Agent 💬

A simple AI assistant that answers your questions using [Google ADK](https://google.github.io/adk-docs/) and Gemini AI. This agent communicates through uAgents chat protocol, providing multi-turn conversations with persistent memory.

## Features

- **Multi-turn chat with memory**: Conversations persist even if the agent restarts or crashes
- **Durable execution**: Thanks to ADK session management, the agent maintains conversation context across requests
- **uAgents chat compatibility**: Works out-of-the-box with uAgents / ASI:One chat UIs and agent-to-agent messaging
- **General-purpose assistant**: Powered by Gemini 2.5 Flash for reasoning, summaries, explanations, and natural conversation
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

The agent will start on `http://0.0.0.0:8005`

### Example Queries

Once running, send messages to the agent via Agentverse or direct chat protocol:

```
"What is artificial intelligence?"
"Explain how machine learning works"
"Help me understand neural networks"
"What are the benefits of cloud computing?"
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
│              (Agent Execution)                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              LlmAgent (from YAML)                        │
│              Model: gemini-2.5-flash                      │
│              Session: InMemorySessionService             │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
basic_agent/
├── agent.py              # Main agent file with uAgents integration
└── root_agent.yaml       # ADK agent configuration (model, instructions)
```

## What You Can Ask

- General knowledge questions
- Explanations of concepts
- Help with understanding topics
- Any conversational queries

## Technology Stack

- **uAgents**: Chat protocol communication and agent-to-agent messaging
- **Google ADK (Agent Development Kit)**: Agent execution and management
- **Gemini 2.5 Flash**: LLM processing
- **YAML configuration**: Agent setup defined in `root_agent.yaml`
