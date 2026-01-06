# Policy Agent with Context Management 📋

An intelligent policy assistant that adapts its responses based on your question type. Built with [Google ADK](https://google.github.io/adk-docs/) and [Fetch.ai uAgents](https://uagents.fetch.ai/docs), this agent uses advanced context management to provide structured, citation-backed answers with intent detection.

## Features

- **Multi-turn chat with memory**: Conversations persist even if the agent restarts or crashes
- **Durable execution**: Thanks to ADK session management and context caching, the agent maintains conversation context and adapts responses based on intent
- **uAgents chat compatibility**: Works out-of-the-box with uAgents / ASI:One chat UIs and agent-to-agent messaging
- **Policy & compliance assistant**: Powered by Gemini 3 Flash Preview for structured responses with citations, intent detection (answer/compare/list/summarize), and context-aware policy guidance
- **Session-aware conversations**: Each chat session is tracked and stored using ADK session management with context caching for efficient response generation
- **Intent detection**: Automatically detects user intent (answer, compare, list, summarize) and adapts responses accordingly
- **Context caching**: Static instruction headers cached for 1 hour with dynamic turn instructions

## Intent Types

The agent automatically detects your intent:

| Intent | Description | Example |
|--------|-------------|---------|
| **Answer** | Direct questions | "What is artificial intelligence?" |
| **Compare** | Comparison questions | "Compare Python and JavaScript" |
| **List Controls** | List requests | "List controls for security" |
| **Summarize** | Summary requests | "Summarize the benefits of cloud computing" |

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

The agent will start on `http://0.0.0.0:8007`

### Example Queries

Once running, send messages to the agent via Agentverse or direct chat protocol:

```
"Summarize the benefits of cloud computing"
"Compare Python and JavaScript"
"List controls for security compliance"
"What are the best practices for API security?"
"How do I implement GDPR compliance?"
```

## Response Format

Responses include:
- **Answer**: Main response text (formatted as plain text, no markdown)
- **Sources**: Clickable URLs (not just names)
- **Confidence**: Only shown if confidence is low (< 70%)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              uAgents Chat Protocol                      │
│              (Message Handler)                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Chat Handler                                │
│              (Intent Detection & Turn Instruction)       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ADK Runner                                  │
│              (Agent Execution with Context Cache)        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              ADK App                                     │
│              - Static Instruction (Cached)               │
│              - Dynamic Turn Instruction                  │
│              - Context Cache (TTL: 1 hour)               │
│              Model: gemini-3-flash-preview               │
│              Tools: google_search                        │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
policy_agent/
├── agent.py              # Main agent file with uAgents integration
├── app_setup.py          # ADK App configuration with context caching
├── chat_handler.py       # Intent detection and turn instruction building
├── steering.py           # Steering inputs and instruction builder
└── __init__.py
```

## Technology Stack

- **uAgents**: Chat protocol communication and agent-to-agent messaging
- **Google ADK (Agent Development Kit)**: Agent execution with context management
- **Gemini 3 Flash Preview**: LLM processing
- **Google Search**: Real-time information retrieval
- **Context Cache**: Efficient response generation with cached static instructions

## What You Can Ask

- Policy and compliance questions
- General knowledge with sources
- Comparison questions
- Summary requests
- List requests
- Any question needing structured, cited answers
