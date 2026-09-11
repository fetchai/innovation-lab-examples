# Docker deployment (MCP server)

The **MCP HTTP server** (`src/index.ts`) is containerized. The Python **uAgent** (`src/fetch_uagent.py`) is not included in this image; run it separately on a host or VM that can reach this service.

## Prerequisites

- Docker 24+ and Docker Compose v2
- A `.env` file (copy from `.env.example`) with at least **`GOOGLE_MAPS_API_KEY`**

## Quick start

```bash
cp .env.example .env
# Edit .env — set GOOGLE_MAPS_API_KEY (required), optional YELP_API_KEY, etc.

docker compose up -d --build
```

- **Health:** `http://localhost:${PORT:-3000}/health`
- **MCP endpoint:** `http://localhost:${PORT:-3000}/mcp`

The compose file maps **host** port `${PORT:-3000}` → container port **3000**. The process inside the container always listens on `3000` (see `docker-compose.yml` `environment.PORT`).

## Point the TypeScript agent / uAgent at Docker

On the machine running `fetch_uagent.py` or any MCP client, set:

```bash
MCP_SERVER_URL=http://<host>:3000/mcp
```

Examples:

- MCP on same machine, uAgent on host: `http://127.0.0.1:3000/mcp`
- MCP in Docker, uAgent on host (Docker Desktop): `http://127.0.0.1:3000/mcp` (published port)
- uAgent in another container on the same Compose project: add both services to `docker-compose.yml` and use `http://mcp:3000/mcp` on the internal network (not covered by default file; extend as needed)

## Build image only

```bash
docker build -t mcp-restaurant-booking:latest .
docker run --rm -p 3000:3000 --env-file .env mcp-restaurant-booking:latest
```

## Production notes

- Do not bake `.env` into images; pass secrets via Compose `env_file`, orchestrator secrets, or `-e`.
- Use TLS termination (reverse proxy) in front of the container for public deployments.
- Rotate API keys if they were ever committed or logged.
