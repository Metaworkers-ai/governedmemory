# Technical history

This document preserves the repository's implementation history without
making internal epic names part of the public product narrative.

## Current components

| Area | Location | Responsibility |
| --- | --- | --- |
| Models | `core/models/` | Memory, trust, provenance, purpose, policy, and audit data models |
| Memory store | `core/memory_store/` | Tenant-scoped writes, reads, retrieval, quarantine, deletion, and schema setup |
| Write governance | `core/write_governor/` | Injection scoring and duplicate/supersession handling |
| Retrieval governance | `core/retrieval_engine/` | Hybrid ranking and trust/purpose filtering |
| Policy engine | `core/policy_engine/` | Purpose binding and privileged-action decisions |
| Detection | `core/detection/` | Heuristic, classifier, and ensemble scoring with reproducible metrics |
| Audit | `core/audit/` | Provenance traversal, cascade planning, and hash-chain verification |
| API | `api/` | FastAPI routes and API-key tenant resolution |
| SDK | `sdk/python/` | Stdlib-only `metaworkers` client |
| Console | `web/` | Next.js UI backed by the REST API |
| Local demo | `scripts/` + `deploy/` | Docker Quickstart, seed data, readiness, and diagnostics |

## Evolution

The project began as a direct Python/Postgres memory store. Governance was then
added at the write boundary (provenance, taint, injection scoring, and
deduplication), followed by a retrieval entry point that applies trust and
purpose gates before returning records. Policy evaluation and privileged-action
checks made those decisions explicit and auditable.

The detection package added a pure-Python classifier and held-out evaluation
without changing the default heuristic behavior. The audit work added
provenance graph traversal, cascade-purge planning, and formal hash-chain
verification. Finally, the REST API and Next.js console became the primary
browser-facing path, while the older Streamlit app remained an optional local
development tool.

## Design boundaries

- `MemoryStore.write()` and `MemoryStore.retrieve()` are the governed product
  entry points.
- Raw vector/lexical search is diagnostic and intentionally does not apply the
  privilege gate.
- The API resolves the tenant from the API key; request bodies do not choose a
  tenant.
- Integrations coordinate existing governance; they do not duplicate the
  scanner, policy engine, or semantic search pipeline.

For implementation-level decisions, read the source and the focused tests
alongside this history. Historical milestone names are useful for archaeology,
not for describing product guarantees.
