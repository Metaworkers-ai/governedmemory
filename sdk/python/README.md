# metaworkers

Thin Python client for a self-hosted [GovernedMemory](https://github.com/Metaworkers-ai/governedmemory) REST API server.

No third-party dependencies — stdlib `urllib.request` only. This talks to a running server over HTTP; it doesn't touch Postgres or any governance logic directly. Run the server first (see the main repo's `deploy/docker-compose.yml`), then:

```bash
pip install -e sdk/python   # not yet published to PyPI
```

```python
from metaworkers import GovernedMemory, Source

mem = GovernedMemory(base_url="http://localhost:8000", api_key="some-secret-key")

mem.write(
    customer_id="cust-1", agent_id="cx-1", session_id="s-1",
    content="customer prefers email contact",
    source=Source(type="user", ref="msg-1001", confidence=0.9),
    purpose=["cx_support"],
)

results = mem.retrieve(
    query="how does this customer want to be contacted?",
    agent_id="cx-1", session_id="s-1", purpose="cx_support", k=5,
)

mem.quarantine("mem-uuid")
mem.delete("mem-uuid")
events = mem.audit()

# E6 — provenance lineage + cascade purge
lineage = mem.provenance("mem-uuid")          # {memory_id, ancestors, descendants}
plan = mem.cascade_preview("mem-uuid")        # dry run: what cascade delete would remove
mem.delete("mem-uuid", cascade=True)          # hard-delete it and everything derived from it

# Listing (no query/ranking/gate — plain reads)
customers = mem.list_customers()
memories = mem.list_memories("cust-1")
```

## Status

Covers every route the server (E7) exposes: `write`, `retrieve`, `quarantine`, `delete` (including `cascade=True`, backed by E6's provenance graph), `cascade_preview`, `provenance`, `audit`, `list_customers`, and `list_memories`.

## Errors

Any non-2xx response raises `metaworkers.GovernedMemoryError`, with `.status_code` and `.detail` from the server's response. Connection-level failures (server unreachable, timeout) raise the underlying `urllib.error.URLError` instead.

## Mem0 adapter

For the supported synchronous Mem0 OSS client, see
[`docs/integrations/mem0.md`](../../docs/integrations/mem0.md). The adapter
keeps Mem0 as the memory system of record and adds GovernedMemory evaluation,
external-ID bindings, quarantine, and audit metadata around the existing
`add()` and `search()` calls.
