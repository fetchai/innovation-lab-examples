# TicketLens AI Agent

TicketLens AI is a high-precision travel discovery agent powered by the TicketLens MCP (Model Context Protocol). It transforms fragmented travel research into a curated, bookable itinerary in seconds.

---

## 1) Overview

The agent solves the complex task of real-time travel planning by providing live searching for the best tours, landmarks, and hidden gems worldwide. It automatically organizes results into intuitive categories and generates direct booking links. 

- **Category:** `LLM`, `MCP`
- **Tech stack:** `Python`, `uAgents`, `ASI:One`, `MCP`

## 2) Features

- **Intelligent Trip Discovery**: Live searching for global activities via TicketLens MCP.
- **Rich Experience Presentation**: Grounded summaries, photos, pricing, and ratings for every recommendation.
- **Direct Deep-Linking**: Instant, verified booking links tailored to providers (e.g. Viator, GetYourGuide).
- **Quota-Aware Reasoning**: Automatic history pruning and persistent state caching to efficiently manage remote API limits.

## 3) Prerequisites

- Python 3.10+
- pip
- ASI:One API Key (`ASI1_API_KEY`)

## 4) Installation

```bash
git clone https://github.com/fetchai/innovation-lab-examples.git
cd innovation-lab-examples/mcp-agents/ticketlens-agent
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## 5) Environment Variables

Create a `.env` file using the provided template.

```bash
cp .env.example .env
```

Your `.env` should look like this:

```env
# Agentverse / ASI1 Connectivity
ASI1_API_KEY=your_asi1_api_key_here
ASI1_MODEL=asi1


# TicketLens MCP Infrastructure
MCP_SERVER_URL=https://mcp.ticketlens.com/
```

### Variables
- `ASI1_API_KEY` (required): Used for ASI:One LLM requests.
- `MCP_SERVER_URL` (optional): Defaults to the official TicketLens MCP server.

## 6) Run the Agent

### Native Execution
```bash
python agent.py
```

### Docker Execution
To run the agent in an isolated container using the included Docker configurations:
```bash
docker compose up -d --build
```

To view the agent's logs:
```bash
docker compose logs -f ticketlens-agent
```

## 7) Expected Output

- The agent starts successfully, loads all remote TicketLens MCP tools, and exposes an agent interface.
- If registered, you can immediately begin chatting with the agent on Agentverse.
- The agent responds with heavily curated categorizations of events and POIs, seamlessly embedding rich markdown thumbnail imagery for your selected destination.

## 8) Demo

![ASI Demo](./assets/demo.png)

## 9) Architecture

```
User Chat ──► Chat Protocol ──► LLM (ASI:One) ──► MCP Client ──► TicketLens API
    ▲              │                                │
    │              ▼                                ▼
    └────── uAgents Context Storage ◄───────────────┘
                     (Quota & Cache State)
```

**Flow**: User sends natural language → `chat_protocol` evaluates intent → ASI:One reasoning engine dictates tool calls → `mcp_client` queries TicketLens → Responses are cached in `ctx.storage` → Final markdown results are rendered back to user.

### 📁 Three Core Files

#### 1. `mcp_client.py` - Network & Cache Layer
**Purpose**: Manages communication with the remote TicketLens MCP server and protects global API quotas.
- **Persistent Caching**: Utilizes the `uAgents` storage wrapper (`ctx.storage`) to aggressively cache POI and tour data, verifying TTL cleanly before triggering remote network requests.
- **Image Enrichment**: Auto-injects explicit CDN resolution links to raw internal POI database IDs.

#### 2. `chat_protocol.py` - Reasoning Engine
**Purpose**: The central brain driving conversational interaction and LLM tool execution.
- **Parallel Tool Resolving**: Simultaneously fields multiple sub-queries defined by the LLM (e.g. searching "Louvre" and "Eiffel Tower" within one pass) using isolated `asyncio` task groups.
- **Session Pruning**: Automatically prunes conversation buffers (`history_{user_address}`) after configurable inactivity windows to optimize token context.

#### 3. `agent.py` - Lifecycle Orchestrator
**Purpose**: System entrypoint and infrastructure definition.
- **Mailbox Protocol**: Configures the agent to communicate seamlessly via the Agentverse Mailbox system while exposing a local inspector HTTP server on port `8000`.
- **Bootstrapping**: Fetches and stores the MCP remote tool capabilities dictionary during the `@agent.on_event("startup")` lifecycle hook.

## 10) Troubleshooting

- **_InactiveRpcError / Connection Issues** -> This is a benign error when Agentverse session resets. Functionality is unharmed.
- **Missing env var error** -> Ensure `ASI1_API_KEY` is fully configured in your `.env`.

## 12) License

This codebase is provided under the repository's main open-source license.
