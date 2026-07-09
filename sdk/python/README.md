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
```

## Status

Covers `write`, `retrieve`, `quarantine`, `delete` (non-cascade), and `audit`. `provenance()` and `delete(..., cascade=True)` raise `GovernedMemoryError` with a 501 status until the server's E6 work (provenance graph traversal) lands — they're included now so this client won't need a breaking change once it does.

## Errors

Any non-2xx response raises `metaworkers.GovernedMemoryError`, with `.status_code` and `.detail` from the server's response. Connection-level failures (server unreachable, timeout) raise the underlying `urllib.error.URLError` instead.
