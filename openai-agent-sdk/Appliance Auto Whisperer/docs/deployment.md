# Deployment

## Local — REST API (`main.py`)

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Local — uAgents bureau (`diagnostic_bureau.py`)

```bash
python diagnostic_bureau.py
```

Uses **mailbox** when `AGENT_ENDPOINT` is unset; set `AGENTVERSE_API_KEY` for Agentverse.

## Docker

- **Bureau (recommended for Fetch / ASI:One):** `Dockerfile.bureau` → `make docker-build-bureau`
- **REST only:** root `Dockerfile` → `make docker-build`

### Docker Compose (local)

Use the agent folder’s `docker-compose.yml` with your configured `.env`:

```bash
docker-compose up --build
```

- REST API: `http://localhost:8000/health` and `POST http://localhost:8000/v1/chat`
- uAgents bureau: binds on `PORT=8001` (see `diagnostic_bureau.py`)

## Render + mailbox → Agentverse

1. Deploy from `render.yaml` (service `repair-orchestrator-bureau`, `Dockerfile.bureau`).
2. Set secrets: `OPENAI_API_KEY`, `YOUTUBE_API_KEY`, optional Bright Data, **`AGENTVERSE_API_KEY`**, stable agent **seeds**.
3. **Do not** set `AGENT_ENDPOINT` for mailbox mode. Render injects **`PORT`**; the bureau binds to it.
4. From deploy logs, copy the **`repair-orchestrator`** address; register that public agent in **Agentverse** for ASI:One.

See the main `README.md` for the full checklist.
