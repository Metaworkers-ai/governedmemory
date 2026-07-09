# Makefile — convenience commands for local development
# On Windows without make: use Git Bash, WSL, or run commands directly.

.PHONY: install install-embed install-api api db-up db-down test-unit test-integration test lint

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	pip install -e ".[dev]" -r requirements-dev.txt

install-embed:
	pip install -r requirements-embed-local.txt

install-api:
	pip install -r requirements-api.txt

# ── API server (E7) ───────────────────────────────────────────────────────────

api:
	uvicorn api.main:app --reload --port 8000

# ── Database ──────────────────────────────────────────────────────────────────

db-up:
	docker compose -f deploy/docker-compose.yml up -d
	@echo "Waiting for Postgres to be ready..."
	@sleep 3

db-down:
	docker compose -f deploy/docker-compose.yml down

db-reset:
	docker compose -f deploy/docker-compose.yml down -v
	docker compose -f deploy/docker-compose.yml up -d

# ── Tests ─────────────────────────────────────────────────────────────────────

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test:
	pytest -v --cov=core --cov-report=term-missing

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	ruff check core/ tests/
	ruff format --check core/ tests/

format:
	ruff format core/ tests/
	ruff check --fix core/ tests/
