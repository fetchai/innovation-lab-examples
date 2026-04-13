#!/usr/bin/env bash
# docker-entrypoint.sh — single-container bureau mode
#
# Starts all three agents in one container (Render background-worker style).
# Workers are started first and given WORKER_READY_WAIT seconds to register on
# the Almanac before the orchestrator begins routing to them.
#
# Usage (Render one-dyno / single container):
#   docker build -f Dockerfile.bureau -t whisperer-bureau .
#   docker run --env-file .env -e PORT=8001 -p 8001:8001 \
#              --entrypoint /app/docker-entrypoint.sh whisperer-bureau
#
# Environment vars respected:
#   WORKER_READY_WAIT  — seconds to wait after starting workers (default: 8)
#   LOG_LEVEL          — passed through to all processes

set -euo pipefail

WORKER_READY_WAIT="${WORKER_READY_WAIT:-8}"

echo "[entrypoint] Starting parts-sourcing-agent on port 8002 ..."
python workers/parts_agent.py &
PARTS_PID=$!

echo "[entrypoint] Starting tutorial-agent on port 8003 ..."
python workers/tutorial_agent.py &
TUTORIAL_PID=$!

echo "[entrypoint] Waiting ${WORKER_READY_WAIT}s for workers to register on Almanac ..."
sleep "${WORKER_READY_WAIT}"

echo "[entrypoint] Starting repair-orchestrator on port ${PORT:-8001} ..."
python diagnostic_bureau.py &
ORCH_PID=$!

# Forward SIGTERM/SIGINT to all child processes so Docker shutdown is clean.
_shutdown() {
    echo "[entrypoint] Shutting down all agents ..."
    kill "$PARTS_PID" "$TUTORIAL_PID" "$ORCH_PID" 2>/dev/null || true
    wait "$PARTS_PID" "$TUTORIAL_PID" "$ORCH_PID" 2>/dev/null || true
    echo "[entrypoint] All agents stopped."
}
trap _shutdown SIGTERM SIGINT

# Wait for any child to exit; if any crashes, shut the rest down.
wait -n 2>/dev/null || wait
_shutdown
