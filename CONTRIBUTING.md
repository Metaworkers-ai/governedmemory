# Contributing to Governed Memory (Metaworkers.AI)

Welcome! This guide explains how to set up your environment, run tests, understand the codebase, and submit a contribution. Whether you're fixing a bug, implementing an epic from the backlog, or adding a new embedding provider — this document has you covered.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [First-Time Setup](#first-time-setup)
3. [Project Structure](#project-structure)
4. [Daily Development Loop](#daily-development-loop)
5. [Running Tests](#running-tests)
6. [Code Style](#code-style)
7. [Making Your First Contribution](#making-your-first-contribution)
8. [Architecture Decisions](#architecture-decisions)
9. [Common Gotchas](#common-gotchas)
10. [Pull Request Checklist](#pull-request-checklist)
11. [Glossary](#glossary)

---

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.11+ | Type hints used throughout (`X \| Y`, `list[str]`) |
| Docker Desktop | latest | Runs Postgres+pgvector for local dev and integration tests |
| Git | 2.40+ | Trunk-based development |
| conda or venv | any | Isolate dependencies |

**Windows users:** all commands below work in PowerShell or Git Bash. If you don't have `make`, run the commands inside each `make` target directly.

---

## First-Time Setup

### 1. Clone and create an environment

```bash
git clone https://github.com/Metaworkers-ai/governedmemory.git
cd governedmemory

# Option A — conda (recommended if you have it)
conda create -n mw python=3.11 -y
conda activate mw

# Option B — venv
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows PowerShell
```

### 2. Install dependencies

```bash
# Core + dev tools (required for tests)
pip install -r requirements-dev.txt

# Install the package in editable mode so `from core.models import ...` works
pip install -e .
```

> **Optional — local embedding model** (only needed if you want to run vector search with real embeddings):
> ```bash
> pip install -r requirements-embed-local.txt
> # This downloads ~420 MB (all-mpnet-base-v2). CPU-only version:
> pip install torch --index-url https://download.pytorch.org/whl/cpu
> ```

### 3. Configure environment

```bash
cp deploy/.env.example .env
# Edit .env if needed — defaults work for local Docker
```

### 4. Start the database

```bash
docker compose -f deploy/docker-compose.yml up -d
# Verify Postgres is healthy:
docker compose -f deploy/docker-compose.yml ps
```

### 5. Run migrations

```bash
python -m core.memory_store.migrate
# Expected output:
# [migrate] Applying 001_init.sql ... done.
# [migrate] 1 migration(s) applied.
```

### 6. Verify the setup

```bash
# Unit tests (no Docker needed)
pytest tests/unit/ -v

# Integration tests (Docker must be running)
pytest tests/integration/ -v
```

All tests should pass. If they do, you're ready to contribute.

---

## Project Structure

```
governedmemory/
├── core/                       ← ALL governance logic lives here
│   ├── models/                 ← Pydantic data models (E1)
│   │   ├── memory_record.py    ← MemoryRecord, WriteRequest, Provenance, Trust, ...
│   │   ├── audit_event.py      ← AuditEvent (append-only, hash-chained)
│   │   └── policy.py           ← Policy, PurposeBinding, PrivilegeRules
│   └── memory_store/           ← Storage layer (E1)
│       ├── store.py            ← MemoryStore class (write/read/search/quarantine/delete)
│       ├── embeddings.py       ← EmbeddingProvider ABC + pluggable implementations
│       ├── migrate.py          ← SQL migration runner (run with: python -m core.memory_store.migrate)
│       └── migrations/
│           └── 001_init.sql    ← Initial schema (memory, audit, policy tables)
│
├── metaworkers-mvp/            ← Original MVP (SQLite, kept for reference)
│
├── deploy/
│   ├── docker-compose.yml      ← Local Postgres+pgvector
│   └── .env.example            ← Environment variable template
│
├── tests/
│   ├── conftest.py             ← Shared fixtures
│   ├── unit/                   ← Fast tests, no Docker (models, logic)
│   └── integration/            ← Real DB tests (Docker required)
│
├── CONTRIBUTING.md             ← This file
├── pyproject.toml              ← Package metadata + ruff config
├── requirements-core.txt       ← Runtime deps
├── requirements-embed-local.txt ← sentence-transformers (optional)
└── requirements-dev.txt        ← Test + lint deps
```

### What's coming (future epics)

```
core/
├── write_governor/             ← E2: provenance→taint→dedup→embed pipeline
├── retrieval_engine/           ← E3: hybrid vector+lexical search + privilege gate
├── policy_engine/              ← E4: policy evaluator (OPA-ready)
├── detection/                  ← E5: injection scanner + taint classifier
└── audit/                      ← E6: provenance graph + cascade purge

sdk/python/                     ← E7: GovernedMemory SDK
api/                            ← E7: FastAPI /v1/* routes
adapters/                       ← E8: LangGraph, Mem0 shims
ui/                             ← E9: React provenance visualizer
benchmark/                      ← E10: poisoning attack library
coworker/                       ← E12: CX coworker showcase
enterprise/                     ← E13: RBAC stubs (gated)
```

---

## Daily Development Loop

```bash
# 1. Pull latest
git pull origin main

# 2. Start DB (if not already running)
docker compose -f deploy/docker-compose.yml up -d

# 3. Make your change in core/ or tests/

# 4. Run unit tests (fast, no Docker needed for pure logic changes)
pytest tests/unit/ -v

# 5. Run integration tests before pushing
pytest tests/integration/ -v

# 6. Lint
ruff check core/ tests/
ruff format core/ tests/

# 7. Commit and push a short-lived branch
git checkout -b feat/your-feature-name
git add core/ tests/
git commit -m "feat(e1): describe your change"
git push origin feat/your-feature-name
# Open a PR against main
```

---

## Running Tests

### Unit tests — fast, no Docker

```bash
pytest tests/unit/ -v
```

These test data models, enum values, validation, serialization. They run in under 1 second. No database, no embedding model. Run them every time you change a model.

### Integration tests — real Postgres

```bash
pytest tests/integration/ -v
```

These spin up a real Postgres+pgvector container via testcontainers (Docker required). First run takes ~15 seconds to pull the image. Subsequent runs are fast.

These tests verify the E1 definition of done:
- Write + read a record end-to-end
- Tenant isolation (cross-tenant reads return None)
- Migration idempotency (running twice is safe)
- Hash-chained audit log correctness

### Full suite with coverage

```bash
pytest -v --cov=core --cov-report=term-missing
```

### Running a single test

```bash
pytest tests/integration/test_memory_store.py::TestTenantIsolation::test_get_with_wrong_tenant_returns_none -v
```

### Skipping slow tests

Integration tests auto-skip if Docker is not available. You can also skip them explicitly:

```bash
pytest tests/unit/ -v -k "not integration"
```

---

## Code Style

We use **ruff** for linting and formatting (configured in `pyproject.toml`).

```bash
# Check for issues
ruff check core/ tests/

# Auto-fix fixable issues + format
ruff format core/ tests/
ruff check --fix core/ tests/
```

**Key conventions:**
- Line length: 100 characters
- Python 3.11+ type hints throughout (`list[str]`, `X | Y`, not `List[str]`, `Optional[X]`)
- No inline comments explaining *what* code does — name things well instead
- Comments only for non-obvious *why* (a hidden constraint, a workaround, a security invariant)
- `_require_tenant(tenant_id)` call at the top of every store method — never skip it

---

## Making Your First Contribution

### Adding a new embedding provider

This is a great first contribution — fully self-contained, no risk of breaking governance logic.

1. Open `core/memory_store/embeddings.py`
2. Add a new class that extends `EmbeddingProvider`
3. Implement `embed()`, `embed_batch()`, and the `dimensions` property
4. Add it to `core/memory_store/__init__.py`'s `__all__`
5. Add a unit test in `tests/unit/test_embeddings.py` (create the file if it doesn't exist)
6. Document the API key or package it requires in the class docstring

Example skeleton:
```python
class BedrockEmbeddingProvider(EmbeddingProvider):
    """AWS Bedrock Titan Embed — stays in your AWS account."""
    def __init__(self, model_id: str = "amazon.titan-embed-text-v2:0", region: str = "us-east-1"):
        import boto3
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id
        self._dims = 1024  # Titan Embed v2 output size

    def embed(self, text: str) -> list[float]:
        import json
        body = json.dumps({"inputText": text})
        resp = self._client.invoke_model(modelId=self._model_id, body=body)
        return json.loads(resp["body"].read())["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]  # Bedrock has no batch endpoint yet

    @property
    def dimensions(self) -> int:
        return self._dims
```

> **Note:** If your provider outputs a different number of dimensions than the current Postgres column (`vector(768)`), you must create a new migration to change the column type. See [Adding a Migration](#adding-a-migration).

### Adding a migration

1. Create `core/memory_store/migrations/002_your_change.sql`
2. Number files sequentially: `001`, `002`, `003`, ...
3. Write idempotent SQL (`IF NOT EXISTS`, `CREATE OR REPLACE`, etc.)
4. Run `python -m core.memory_store.migrate` to apply locally
5. Commit the `.sql` file in the same PR as the code that needs it

**Never edit an existing migration file.** If a migration has been applied to any environment, it cannot be changed — add a new one instead.

### Implementing an epic

Each epic in the engineering plan maps to a new subdirectory under `core/`. Before starting:

1. Read the relevant section of `Metaworkers_Detailed_Engineering_Plan.md`
2. Open a GitHub issue and describe your approach (get a quick review before writing code)
3. Create your directory with an `__init__.py`
4. Write tests first (unit tests for logic, integration tests for DB interactions)
5. Implement the feature
6. Update `CONTRIBUTING.md` if you add new setup steps

---

## Architecture Decisions

Understanding *why* things are designed this way will help you make good decisions when extending the system.

### Cloud-agnostic by DATABASE_URL

The store has zero cloud-specific code. The only configuration it needs is a Postgres DSN via `DATABASE_URL`. This works on:

- **Local Docker** (default for dev — `docker-compose.yml`)
- **AWS RDS** — `postgresql://user:pass@rds-endpoint:5432/db`
- **GCP Cloud SQL** — same DSN via the Cloud SQL Auth Proxy
- **Azure Postgres Flexible Server** — same DSN
- **Supabase, Neon, Railway** — all provide standard Postgres DSNs

If you ever add cloud-specific code (AWS SDK, GCP SDK) to `core/`, it must be behind an interface abstraction (like `EmbeddingProvider`), never called directly from the store.

### Model-agnostic via EmbeddingProvider

The embedding model is not part of governance. The `EmbeddingProvider` ABC decouples the store from any specific model. This matters because:

- OSS users want local, free, offline embeddings (sentence-transformers)
- Enterprise users may want OpenAI or a model in their cloud account
- The benchmark harness will test multiple models

`NullEmbeddingProvider` (zero vectors) exists so unit tests and CI pipelines that don't care about vector search quality don't need to download a model.

### Why Postgres + pgvector (not separate vector DB)

One database for structured queries, full-text search, vector search, and the append-only audit log. This means:
- No sync issues between two systems
- Transactional guarantees across memory + audit events
- Easier self-hosting for OSS users (one Docker image, not two)
- Works on every major cloud's managed Postgres

### Why raw SQL migrations (not Alembic)

Alembic adds complexity that slows down onboarding. Plain `.sql` files are:
- Readable by anyone (no Python ORM knowledge needed)
- Runnable manually (`psql < 001_init.sql`) for debugging
- Diffable in code review (you see exactly what changes)

The trade-off is no auto-generation of migrations from model changes. Always write them by hand.

### Why sync psycopg2 (not async asyncpg) for E1

E1 prioritizes contributor accessibility. Async Postgres requires `async def` throughout the call stack, which is unfamiliar to many contributors and complicates testing. The sync approach works fine for E1's throughput targets. When E7 (FastAPI) and latency benchmarks reveal a bottleneck, migrate to `asyncpg` in a targeted E7 PR — not before.

### Tenant isolation: non-negotiable

`tenant_id` must be in the `WHERE` clause of every single query. The `_require_tenant()` helper at the top of every store method is a guard against accidentally omitting it. If you add a new store method, call `_require_tenant(tenant_id)` as the first line. The integration test `TestTenantIsolation` verifies this property — all tests in that class must pass.

### Hash-chained audit log

Every audit event stores `hash = SHA-256(prev_hash + event_payload)`. This means:
- Deleting or modifying any event breaks the hash chain
- The chain can be verified offline (no trusted timestamp service needed)
- False negatives (security holes) are detectable in post-incident review

The audit table has no UPDATE or DELETE triggers — it is append-only by convention. E6 will add a formal verifier.

---

## Common Gotchas

**"I get `ImportError: No module named 'core'`"**
You haven't installed the package in editable mode. Run: `pip install -e .`

**"Integration tests hang forever"**
Docker is not running. Start it with `docker compose -f deploy/docker-compose.yml up -d` and wait for the health check to pass.

**"psycopg2.OperationalError: connection refused"**
Postgres is not ready yet. Wait 5–10 seconds after `docker compose up -d`.

**"Extension `vector` does not exist"**
You're not using the `pgvector/pgvector:pg16` Docker image. This image has pgvector pre-installed. Other Postgres images don't. Don't change the image in `docker-compose.yml`.

**"I changed a model field but tests still pass with the old value"**
Pydantic v2 ignores extra fields by default. Check that your migration adds the new column and that `_row_to_record()` in `store.py` reads it.

**"ivfflat index warning about too few rows"**
Normal in development. The ivfflat index needs at least `lists * 3` rows to be effective (lists=100 → 300 rows). Vector search still works — it just does a sequential scan. This is fine for dev; production datasets won't have this issue.

**"I want to use a different embedding model with 384 dimensions"**
1. Change `SentenceTransformerProvider("all-MiniLM-L6-v2")` in your code
2. Create `core/memory_store/migrations/002_change_embedding_dim.sql`:
   ```sql
   ALTER TABLE memory ALTER COLUMN embedding TYPE vector(384);
   DROP INDEX IF EXISTS idx_memory_embedding;
   CREATE INDEX idx_memory_embedding ON memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```
3. Run `python -m core.memory_store.migrate`

**"I'm on Windows and `make` doesn't work"**
Use Git Bash or WSL. Or run the commands inside each Makefile target directly in PowerShell.

---

## Pull Request Checklist

Before opening a PR, verify all of the following:

- [ ] `pytest tests/unit/ -v` passes
- [ ] `pytest tests/integration/ -v` passes (Docker must be running)
- [ ] `ruff check core/ tests/` reports no errors
- [ ] If you added a new model field: `_row_to_record()` in `store.py` reads it AND a migration adds the column
- [ ] If you added a new migration: it is idempotent (safe to run twice)
- [ ] If you added a new embedding provider: it has a unit test
- [ ] Every new store method calls `_require_tenant(tenant_id)` as its first line
- [ ] The tenant isolation tests in `TestTenantIsolation` still pass
- [ ] No secrets, API keys, or personal data in committed files
- [ ] PR description explains *why* the change is needed, not just what it does

---

## Glossary

| Term | Meaning |
|---|---|
| **tenant_id** | The enterprise/company using Metaworkers. All data is isolated per tenant. |
| **customer_id** | The end-customer whose memory is being stored (the CX subject). |
| **agent_id** | The AI agent that wrote or retrieved a memory record. |
| **taint** | The trust status of a memory: `trusted`, `untrusted`, or `quarantined`. |
| **provenance** | Where a memory came from: source type, source reference, confidence score. |
| **purpose** | What agent actions are allowed to use this memory (e.g., `cx_support`, `billing`). |
| **privilege gate** | Read-path filter that drops `untrusted`/`quarantined` records for privileged actions. |
| **Write Governor** | The write pipeline: provenance → injection scan → taint → purpose → dedup → embed → persist. |
| **Retrieval Engine** | The read pipeline: hybrid fetch → rerank → purpose check → privilege gate → audit. |
| **injection score** | Float 0–1 indicating how likely a memory is a prompt injection attempt. |
| **hash chain** | The audit log's tamper-evidence mechanism: each event hashes the previous event's hash. |
| **ivfflat** | pgvector's inverted file index for approximate nearest-neighbor vector search. |
| **NullEmbeddingProvider** | All-zero vectors, used only in tests to avoid loading an ML model. |
