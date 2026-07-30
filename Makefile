# Makefile — convenience commands for local development
# On Windows without make: use Git Bash, WSL, or run commands directly.

.PHONY: install install-embed install-api install-sdk install-mem0 api db-up db-down test-unit test-integration test test-mem0-contract docs-check smoke lint format

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	pip install -r requirements-dev.txt
	pip install -e .
	pip install -e sdk/python

install-embed:
	pip install -r requirements-embed-local.txt

install-api:
	pip install -r requirements-api.txt

install-sdk:
	pip install -e sdk/python

install-mem0:
	pip install -e "sdk/python[mem0]"

# ── API server ───────────────────────────────────────────────────────────────
install-agentdojo:
	pip install -r requirements-agentdojo.txt

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

test-mem0-contract:
	pytest tests/unit/test_mem0_contract.py -v

docs-check:
	python scripts/check_docs_links.py

smoke:
	python scripts/smoke_quickstart.py
test-agentdojo-contract:
	pytest tests/contract/ -v

test:
	pytest -v --cov=core --cov-report=term-missing

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	ruff check core/ api/ tests/ sdk/python/ integrations/ scripts/
	ruff format --check core/ api/ tests/ sdk/python/ integrations/ examples/ scripts/check_docs_links.py scripts/smoke_quickstart.py

format:
	ruff format core/ api/ tests/ sdk/python/ integrations/ examples/ scripts/check_docs_links.py scripts/smoke_quickstart.py
	ruff check --fix core/ api/ tests/ sdk/python/ integrations/ scripts/
	ruff check core/ api/ tests/ sdk/python/ integrations/
	ruff format --check core/ api/ tests/ sdk/python/ integrations/

format:
	ruff format core/ api/ tests/ sdk/python/ integrations/
	ruff check --fix core/ api/ tests/ sdk/python/ integrations/
