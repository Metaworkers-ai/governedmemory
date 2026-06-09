# Metaworkers.AI — Governed Customer Memory MVP

A persistent, policy-controlled memory layer for enterprise AI support agents.
Agents get a **Customer Memory Card** — cited, governed, PII-safe context — instead of a blank session.

---

## What this MVP demonstrates

| Capability | Description |
|---|---|
| **Memory ingestion** | POST any CX event (ticket, CRM, chat, voice, KB) with governance metadata |
| **Customer Memory Card** | Ranked, governed, cited memory snapshot delivered to a support agent |
| **ACL enforcement** | Memories scoped to roles (`support`, `billing`, `manager`, `legal`, `admin`) |
| **Sensitivity gating** | `public / internal / confidential / pii` — higher tiers require higher role levels |
| **PII masking** | Emails, phones, SSNs, credit cards auto-redacted for lower-privilege agents |
| **Retention / expiry** | Every memory has a per-record `retention_days`; expired memories are purged at retrieval |
| **Staleness detection** | Newer records on the same topic trigger a warning on older records |
| **GDPR forget** | `DELETE /memories/{id}` hard-deletes any single memory |
| **Relevance ranking** | Keyword overlap + confidence + recency scoring |

---

## Project structure

```
metaworkers-mvp/
├── main.py           # FastAPI app — all HTTP routes
├── models.py         # Pydantic data models
├── memory_store.py   # SQLite CRUD layer
├── governance.py     # ACL, PII masking, retention, staleness
├── retrieval.py      # Memory ranking + card builder
├── seed_data.py      # Load realistic demo CX data
├── demo_cli.py       # Rich terminal demo across 4 scenarios
├── requirements.txt
└── README.md
```

---

## Setup & run

### 1. Activate the conda environment

```bash
conda activate mw
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the API server

```bash
uvicorn main:app --reload
```

The server starts at **http://localhost:8000**.
Interactive API docs (Swagger UI): **http://localhost:8000/docs**

### 4. Load demo data (separate terminal)

```bash
conda activate mw
python seed_data.py
```

This inserts 8 realistic memories across 2 demo customers:
- `cust_jane_001` — Enterprise plan, billing dispute, refund promise, stale billing preference
- `cust_bob_002` — PII masking demo (email/phone redacted for `support` role)

### 5. Run the interactive CLI demo

```bash
python demo_cli.py
```

Steps through 4 scenarios showing ACL filtering, PII masking, and staleness warnings.

### 6. Call the API directly

**Get a Memory Card (support agent):**
```bash
curl "http://localhost:8000/memory-card/cust_jane_001?agent_role=support"
```

**Agent runtime query:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"cust_jane_001","query_text":"refund billing","agent_role":"support","max_results":5}'
```

**Ingest a new memory:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust_jane_001",
    "content": "Customer confirmed renewal for Q4 2026 on call today.",
    "source_ref": "Call transcript 2026-06-08",
    "source_type": "voice",
    "sensitivity": "internal",
    "retention_days": 365,
    "allowed_roles": ["support", "manager"],
    "confidence": 0.97,
    "tags": ["renewal"]
  }'
```

**Delete a memory (GDPR erasure):**
```bash
curl -X DELETE http://localhost:8000/memories/{memory_id}
```

---

## Key API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest a memory from any CX source |
| `GET` | `/memory-card/{customer_id}` | Governed Memory Card for an agent |
| `POST` | `/query` | Agent runtime query with keyword ranking |
| `DELETE` | `/memories/{memory_id}` | GDPR / right-to-erasure delete |
| `GET` | `/health` | Health check + total memory count |
| `GET` | `/docs` | Swagger UI |

---

## TODO — next engineering milestones

### Core infrastructure
- [ ] **Vector embeddings** — replace keyword scoring with `sentence-transformers` or OpenAI embeddings for semantic retrieval; store vectors in SQLite via `sqlite-vec` or migrate to Chroma/Qdrant
- [ ] **Identity resolution** — unify a customer across Zendesk ticket email, Salesforce contact ID, voice caller ID, and chat session into a single `customer_id`; needs fuzzy matching + a resolution graph
- [ ] **Real connector ingestion** — webhook handlers for Zendesk, Salesforce, Intercom events; OAuth token management; field mapping per source type
- [ ] **Async ingestion pipeline** — replace synchronous `add_memory` with a queue (Celery + Redis or RQ) so high-volume CX events don't block the API
- [ ] **Conflict detection** — when a new memory contradicts an existing one on the same topic (beyond same-tag heuristic), flag both and surface the conflict in the Memory Card

### Governance & compliance
- [ ] **Fine-grained PII detection** — integrate `presidio` or an LLM-based NER step at ingest time to auto-tag PII fields instead of relying on the caller
- [ ] **Retention scheduler** — cron job or APScheduler task to hard-delete expired records and emit an audit log entry
- [ ] **Full audit log** — append-only table recording every memory read, write, delete, and ACL denial with timestamp + agent ID
- [ ] **SOC 2 / HIPAA prep** — encryption-at-rest for the SQLite DB (SQLCipher), TLS enforcement, secrets management via environment variables / Vault

### Agent integration
- [ ] **LangChain / LlamaIndex tool** — wrap `POST /query` as a LangChain `Tool` so any agent framework can call Metaworkers as a retrieval step
- [ ] **Zendesk app sidebar** — embed the Memory Card as a real-time sidebar in the Zendesk agent workspace via the Zendesk Apps Framework
- [ ] **Streaming Memory Card** — stream memories to the agent as they're retrieved rather than waiting for the full card (improves TTFT for long histories)
- [ ] **Memory write-back** — let the agent POST new memories mid-conversation (e.g. recording a promise made during a call)

### Product & UX
- [ ] **Admin dashboard** — React/Next.js UI: search customers, view memory cards, manually mark stale, trigger deletes, view audit log
- [ ] **Memory diff view** — show what changed in a customer's memory card between two timestamps (useful for handoffs)
- [ ] **Design-partner onboarding script** — Voicemonk CX workflow integration: pull CX events from Voicemonk API, push into `/ingest`, inject memory card into agent prompt
- [ ] **Metrics endpoint** — expose KPIs tracked in the pitch: repeat-question rate, time-to-resolution delta, CSAT correlation

### Infrastructure & scale
- [ ] **PostgreSQL migration** — swap SQLite for Postgres with pgvector when moving beyond single-node dev
- [ ] **Multi-tenant isolation** — namespace all queries by `org_id`; enforce row-level security so tenant A cannot reach tenant B memories
- [ ] **Rate limiting** — per-org and per-agent-role rate limits on `/query` and `/ingest`
- [ ] **Docker + docker-compose** — containerize API + DB for reproducible deployment; add a `docker-compose.yml` with API + Postgres + Redis services
