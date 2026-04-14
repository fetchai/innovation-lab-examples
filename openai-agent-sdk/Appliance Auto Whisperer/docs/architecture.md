# Architecture

## Request path

1. **Client** → `POST /v1/chat` with JSON (`app/models/messages.ChatRequest`).
2. **Protocol** (`app/chat/`) parses payload, runs **Coordinator** (`app/orchestration/coordinator.py`).
3. **OrchestratorAgent** (`app/agents/orchestrator_agent.py`) sequences:
   - OpenAI diagnosis (`app/services/openai/diagnosis_client.py`)
   - Parts sourcing (`app/agents/parts_sourcing_agent.py`) — Bright Data hooks live under `app/services/brightdata/`
   - Tutorials (`app/agents/tutorial_agent.py`) — `app/services/youtube/`
   - Synthesis (`app/agents/synthesizer_agent.py`) — pricing heuristics under `app/services/pricing/`
4. **Aggregator** merges structured JSON; **Markdown formatter** builds user-facing text.

## Deployment

- **Docker** — `Dockerfile` runs `uvicorn` on `$PORT` (default 8000).
- **Render** — `render.yaml` uses Docker build; set secrets for API keys.
