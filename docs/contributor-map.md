# Contributor map

Use this map to find the smallest safe place to make a change.

```text
API / SDK consumers
        │
        ▼
api/ ─────────────── sdk/python/
  │                         │
  └──────────────┬──────────┘
                 ▼
          core/memory_store/
          ┌──────┼─────────┐
          ▼      ▼         ▼
       write  retrieve   policy
       guard   engine    engine
          │      │         │
          └──────┴────┬────┘
                       ▼
                  core/audit/
                       │
                       ▼
             Postgres + pgvector
```

| If you want to… | Start here | Add/adjust tests here |
| --- | --- | --- |
| Change request validation or auth | `api/schemas.py`, `api/auth.py` | `tests/integration/test_api.py` |
| Change a write decision | `core/write_governor/`, `core/governance/` | `tests/unit/`, `tests/integration/test_memory_store.py` |
| Change retrieval eligibility | `core/retrieval_engine/`, `core/policy_engine/` | `tests/unit/test_retrieval_engine.py`, integration tests |
| Change audit/provenance behavior | `core/audit/`, `core/memory_store/store.py` | `tests/unit/test_audit.py`, integration tests |
| Change the Python client | `sdk/python/metaworkers/` | `tests/unit/test_sdk_client.py`, SDK E2E tests |
| Change the browser console | `web/app/`, `web/components/`, `web/lib/` | `web` lint, typecheck, and build |
| Improve first-run setup | `scripts/quickstart.*`, `deploy/`, `docs/quickstart.md` | shell/PowerShell validation plus a Docker smoke test |
| Add an integration | `docs/integrations/` and a dedicated adapter package | mocked contract + integration test |

Keep changes at the narrowest boundary. A new adapter should call the existing
governed API rather than reimplementing scanner or policy logic.
