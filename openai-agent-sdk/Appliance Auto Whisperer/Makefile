.PHONY: install dev run test lint \
        docker-build docker-build-bureau \
        docker-up docker-down docker-logs \
        docker-up-rest smoke

install:
	python -m pip install -r requirements.txt
	python -m pip install -e ".[dev]"

dev: install
	python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

run:
	python -m uvicorn main:app --host 0.0.0.0 --port 8000

test:
	python -m pytest tests -v

lint:
	python -m ruff check app tests

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker build -t appliance-auto-whisperer:local .

docker-build-bureau:
	docker build -f Dockerfile.bureau -t repair-orchestrator-bureau:local .

# Full 3-agent bureau (parts-agent + tutorial-agent + orchestrator)
docker-up:
	docker compose --profile bureau up --build

# REST API only
docker-up-rest:
	docker compose --profile rest up --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Smoke test ────────────────────────────────────────────────────────────────

smoke:
	python scripts/smoke_test.py
