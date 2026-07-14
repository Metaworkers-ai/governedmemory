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
11. [License](#license)
12. [Glossary](#glossary)

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

### 5. Create the database schema

```bash
python -c "import os; from dotenv import load_dotenv; from core.memory_store import init_db; load_dotenv(); init_db(os.environ['DATABASE_URL'])"
# Prints nothing on success. Safe to run multiple times (all DDL uses IF NOT EXISTS).
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
│   ├── memory_store/           ← Storage layer (E1)
│   │   ├── store.py            ← MemoryStore class + init_db() + schema (_SCHEMA_SQL)
│   │   └── embeddings.py       ← EmbeddingProvider ABC + pluggable implementations
│   ├── write_governor/         ← Write Governor (E2) — runs inside every MemoryStore.write()
│   │   ├── injection_scanner.py ← Heuristic, rule-based prompt-injection scorer
│   │   └── dedup.py             ← Exact-duplicate detection + version supersession
│   ├── retrieval_engine/       ← Retrieval Engine (E3) — runs inside MemoryStore.retrieve()
│   │   ├── fusion.py            ← Reciprocal rank fusion (vector + lexical)
│   │   └── privilege_gate.py    ← Taint + record-level purpose enforcement on read
│   ├── policy_engine/          ← Policy Engine (E4) — runs inside retrieve()/check_privilege()
│   │   └── evaluator.py         ← Tenant-level purpose-binding + privileged-action evaluation
│   ├── detection/               ← Detection (E5) — score_injection() wired into MemoryStore.write()
│   │   ├── classifier.py        ← InjectionClassifier (trained Naive Bayes, pure Python, no ML deps)
│   │   ├── dataset.py           ← Bundled labeled examples + deterministic train/test split
│   │   ├── metrics.py           ← precision/recall/F1 evaluation for any scorer
│   │   └── scanner.py           ← score_injection() — DETECTION_BACKEND-selectable heuristic/classifier/ensemble
│   └── audit/                   ← Audit Graph (E6) — provenance graph + cascade purge + hash-chain verifier
│       ├── provenance_graph.py  ← ProvenanceGraph — ancestors()/descendants() over parent_ids edges
│       ├── cascade_purge.py     ← plan_cascade_purge() — delete-set planner (root + all descendants)
│       └── verifier.py          ← verify_chain() — recomputes + checks every event's hash, not just linkage
│
├── api/                        ← FastAPI REST server (E7) — wraps core/ behind /v1/*
│   ├── main.py                  ← App + routes: memory, retrieve, quarantine, delete, audit, customers, memories, provenance
│   ├── auth.py                  ← Per-tenant API key resolution (GOVERNEDMEMORY_API_KEYS)
│   ├── schemas.py                ← Request bodies (no tenant_id field -- resolved from the API key)
│   └── deps.py                  ← MemoryStore singleton, built at startup
│
├── sdk/python/                  ← metaworkers: thin HTTP client for the API server (E7)
│   └── metaworkers/
│       └── client.py            ← GovernedMemory class -- stdlib-only, no core/ dependency, own pyproject.toml
│
├── frontend/
│   └── app.py                  ← Streamlit UI — try the store end-to-end in a browser (predates E7, talks to MemoryStore directly)
│
├── web/                         ← Next.js console on the REST API (E7) -- replacing frontend/ above
│   ├── app/                     ← Pages (Write, Browse, Search, Governance, Audit Log) + actions.ts (Server Actions)
│   ├── components/              ← Nav, ContextBar, shared UI primitives
│   ├── lib/                     ← backend.ts (server-only REST client) + types.ts
│   └── Dockerfile               ← Standalone build; wired into deploy/docker-compose.yml's `web` service
│
├── site/                        ← Public landing page (static, no build step) -- deployed to S3 + CloudFront
│   ├── index.html
│   └── README.md                ← Deploy commands
│
├── scripts/
│   ├── demo_data.py             ← Shared demo dataset (one tenant, five customers, 50 memories, one policy)
│   ├── seed_demo.py             ← Populate the demo tenant
│   ├── categorize_demo.py       ← Readiness report: taint/source/purpose breakdown, audit chain check
│   ├── train_detection.py       ← Train + save an E5 classifier artifact
│   ├── eval_detection.py        ← Precision/recall/F1 report across E5's detection backends
│   └── verify_audit.py          ← E6: formally verify a tenant's audit chain, inspect a memory's provenance
│
├── deploy/
│   ├── docker-compose.yml      ← Local Postgres+pgvector, and (E7) the api service
│   ├── Dockerfile               ← API server image (E7)
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
├── requirements-frontend.txt   ← Streamlit (optional)
└── requirements-dev.txt        ← Test + lint deps
```

### What's coming (future epics)

```
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

These tests verify the definition of done across epics:
- Write + read a record end-to-end, tenant isolation, `init_db()` idempotency, hash-chained audit log (E1)
- Content-based injection tainting independent of `source_type`, dedup/supersede on duplicate writes (E2)
- `retrieve()` excludes untrusted/quarantined by default, enforces purpose binding, respects `k`, emits an audit event (E3)
- `get_policy()`/`upsert_policy()` roundtrip, `retrieve()` respects a configured purpose binding, `check_privilege()` denies untrusted memories for privileged actions and emits a `policy_decision` audit event (E4)
- `get_provenance()` reports ancestors/descendants across multi-hop chains and is tenant-scoped, `purge_cascade()` deletes a root and all its descendants (but never its ancestors) and emits one audit event listing every id removed, `verify_audit_chain()` is valid after normal operations and catches an in-place `UPDATE` on a stored event (E6)

E5 (`core/detection/`) is pure Python with no DB dependency, so its coverage lives entirely in `tests/unit/test_detection.py`: classifier train/predict/save/load, precision/recall/F1 computation, and all three `score_injection()` backends (`heuristic`/`classifier`/`ensemble`) — including that the default `heuristic` backend is byte-identical to E2's `scan_for_injection()`, so installing E5 doesn't change `MemoryStore.write()`'s behavior unless `DETECTION_BACKEND` is set.

E6 (`core/audit/`) is also pure Python with no DB dependency — `tests/unit/test_audit.py` covers `ProvenanceGraph` traversal (transitive ancestors/descendants, cycle safety, dangling parent_ids), `plan_cascade_purge()`'s delete-set computation, and `verify_chain()` against hand-built hash chains (intact, in-place tamper, deleted event, reordered events). The DB-integrated entry points (`MemoryStore.get_provenance()`, `.purge_cascade()`, `.verify_audit_chain()`) are covered in `tests/integration/test_memory_store.py` instead, since those need a real audit table and real memory rows to be meaningful.

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

> **Note:** If your provider outputs a different number of dimensions than the current Postgres column (`vector(768)`), you must change the schema too. See [Changing the schema](#changing-the-schema).

### Changing the schema

There's no separate migration system — the full schema lives in `_SCHEMA_SQL` in `core/memory_store/store.py`, and `init_db()` applies it idempotently (every statement uses `IF NOT EXISTS` / equivalent).

1. Edit `_SCHEMA_SQL` directly — e.g. add a column, change a type, add an index
2. Keep every statement idempotent: `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `DROP INDEX IF EXISTS` before recreating, etc.
3. Run `init_db(dsn)` locally to apply it (safe to call repeatedly — see `tests/integration/test_memory_store.py::TestMigrations::test_init_db_is_idempotent`)
4. If you change an existing column's type on data that might already exist in a deployed environment, note that in your PR description — `IF NOT EXISTS` guards additions, not type changes, so those need a deliberate rollout plan.

### Implementing an epic

Each epic maps to a new subdirectory under `core/` (see the roadmap in [Project Structure](#project-structure) and the epic table in `README.md`). Before starting:

1. Open a GitHub issue describing your approach (get a quick review before writing code)
2. Create your directory with an `__init__.py`
3. Write tests first (unit tests for logic, integration tests for DB interactions)
4. Implement the feature
5. Update `CONTRIBUTING.md` if you add new setup steps

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

### Why one idempotent schema file (not Alembic, not numbered migrations)

Both Alembic and a numbered-migrations directory add ceremony that this stage of the project doesn't need yet. Instead, the entire schema lives in one `_SCHEMA_SQL` string in `store.py`, applied by `init_db()`, with every statement written as `IF NOT EXISTS` / equivalent so it's always safe to run again. This is:
- Readable by anyone (no Python ORM knowledge needed, no migration history to trace through)
- Runnable manually (copy `_SCHEMA_SQL` into `psql`) for debugging
- Diffable in code review (the schema change is the diff, not a new file)

The trade-off is that it doesn't handle destructive/lossy changes (dropping a column, changing a type on live data) automatically — those need a deliberate rollout plan, called out in the PR. If this project reaches a point where many contributors are shipping schema changes concurrently, revisit this decision and consider numbered migrations or Alembic.

### Why sync psycopg2 (not async asyncpg) for E1

E1 prioritizes contributor accessibility. Async Postgres requires `async def` throughout the call stack, which is unfamiliar to many contributors and complicates testing. The sync approach works fine for E1's throughput targets. When E7 (FastAPI) and latency benchmarks reveal a bottleneck, migrate to `asyncpg` in a targeted E7 PR — not before.

### Tenant isolation: non-negotiable

`tenant_id` must be in the `WHERE` clause of every single query. The `_require_tenant()` helper at the top of every store method is a guard against accidentally omitting it. If you add a new store method, call `_require_tenant(tenant_id)` as the first line. The integration test `TestTenantIsolation` verifies this property — all tests in that class must pass.

### Hash-chained audit log

Every audit event stores `hash = SHA-256(prev_hash + event_payload)`. This means:
- Deleting or modifying any event breaks the hash chain
- The chain can be verified offline (no trusted timestamp service needed)
- False negatives (security holes) are detectable in post-incident review

The audit table has no UPDATE or DELETE triggers — it is append-only by convention, not by enforcement. `MemoryStore.verify_audit_chain()` (E6, `core/audit/verifier.py`) is the formal check: it recomputes each event's hash from its own stored fields and confirms it matches the recorded hash, in addition to confirming `prev_hash` links to the event before it — so an in-place `UPDATE` on an existing row is caught, not just a deleted or reordered event.

That verifier only works because of an E6 fix worth knowing about if you touch `_audit()`: the hash payload folds in a `ts` string, but pre-E6, that `ts` was computed in Python for the hash while the `ts` *column* was populated by a separate `NOW()` at `INSERT` time — two different instants, so the persisted row could never reproduce the hash that was supposedly computed from it. `_audit()` now stores the exact `ts` string it hashes. If you ever change what goes into the payload, keep the stored columns and the hashed payload in sync, or verification silently becomes impossible again.

`Provenance.parent_ids` (present since E1) is what E6's provenance graph and cascade purge are built on. It's plain JSONB, not a foreign key — a `parent_ids` entry pointing at a deleted or out-of-tenant record is tolerated as a leaf rather than enforced or cleaned up. `MemoryStore.purge_cascade()` deletes a record and everything transitively derived from it in one transaction, and emits one `AuditOp.PURGE` event listing every id removed; `delete()` (E1) is untouched and still removes exactly one record — use whichever matches the intent.

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
Pydantic v2 ignores extra fields by default. Check that `_SCHEMA_SQL` adds the new column and that `_row_to_record()` in `store.py` reads it.

**"ivfflat index warning about too few rows"**
Normal in development. The ivfflat index needs at least `lists * 3` rows to be effective (lists=100 → 300 rows). Vector search still works — it just does a sequential scan. This is fine for dev; production datasets won't have this issue.

**"I want to use a different embedding model with 384 dimensions"**
1. Change `SentenceTransformerProvider("all-MiniLM-L6-v2")` in your code
2. Update the `vector(768)` column type in `_SCHEMA_SQL` (in `core/memory_store/store.py`) to `vector(384)`, and rebuild the ivfflat index to match
3. Run `init_db(dsn)` again — for a fresh local DB this is enough; for an environment with existing 768-dim data, you'll need to re-embed and backfill, since `ALTER COLUMN TYPE` isn't safe to run blindly against live vectors of a different dimension

**"I'm on Windows and `make` doesn't work"**
Use Git Bash or WSL. Or run the commands inside each Makefile target directly in PowerShell.

---

## Pull Request Checklist

Before opening a PR, verify all of the following:

- [ ] `pytest tests/unit/ -v` passes
- [ ] `pytest tests/integration/ -v` passes (Docker must be running)
- [ ] `ruff check core/ tests/` reports no errors
- [ ] If you added a new model field: `_row_to_record()` in `store.py` reads it AND `_SCHEMA_SQL` adds the column
- [ ] If you changed `_SCHEMA_SQL`: every new statement is idempotent (`init_db()` must be safe to run twice)
- [ ] If you added a new embedding provider: it has a unit test
- [ ] Every new store method calls `_require_tenant(tenant_id)` as its first line
- [ ] The tenant isolation tests in `TestTenantIsolation` still pass
- [ ] No secrets, API keys, or personal data in committed files
- [ ] PR description explains *why* the change is needed, not just what it does
- [ ] Commits include a `Signed-off-by` line (see [License](#license) below)

---

## License

This project is licensed under [MIT](LICENSE). By submitting a contribution, you agree it's licensed under the same terms.

We use the [Developer Certificate of Origin (DCO)](https://developercertificate.org/) instead of a separate CLA — it's lighter-weight and just confirms you have the right to submit the code. Sign off every commit with `-s`:

```bash
git commit -s -m "feat(e1): describe your change"
```

This adds a `Signed-off-by: Your Name <you@example.com>` trailer to the commit message. If you forget, `git commit --amend -s` fixes the last commit.

---

## Glossary

| Term | Meaning |
|---|---|
| **tenant_id** | The enterprise/company using Metaworkers. All data is isolated per tenant. |
| **customer_id** | The end-customer whose memory is being stored (the CX subject). |
| **agent_id** | The AI agent that wrote or retrieved a memory record. |
| **taint** | The trust status of a memory: `trusted`, `untrusted`, or `quarantined`. |
| **provenance** | Where a memory came from: source type, source reference, confidence score. |
| **provenance graph** | The directed graph formed by every memory's `parent_ids` — what a memory was derived from (ancestors) and what was derived from it (descendants). |
| **cascade purge** | Deleting a memory and everything transitively derived from it (its full descendant set), in one operation. |
| **purpose** | What agent actions are allowed to use this memory (e.g., `cx_support`, `billing`). |
| **privilege gate** | Read-path filter that drops `untrusted`/`quarantined` records for privileged actions. |
| **Write Governor** | The write pipeline: provenance → injection scan → taint → purpose → dedup → embed → persist. |
| **Retrieval Engine** | The read pipeline: hybrid fetch → rerank → purpose check → privilege gate → audit. |
| **injection score** | Float 0–1 indicating how likely a memory is a prompt injection attempt. |
| **hash chain** | The audit log's tamper-evidence mechanism: each event hashes the previous event's hash. |
| **ivfflat** | pgvector's inverted file index for approximate nearest-neighbor vector search. |
| **NullEmbeddingProvider** | All-zero vectors, used only in tests to avoid loading an ML model. |
