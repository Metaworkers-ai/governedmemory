"""
GovernedMemory — thin HTTP client for a self-hosted GovernedMemory REST API
server (E7).

Deliberately built on the standard library only (urllib.request + json), no
third-party HTTP library dependency. This mirrors the same "zero install
friction" stance core/detection/classifier.py takes for the OSS default
classifier: a client that makes requests via stdlib alone beats a nicer
client library that requires pulling in a dependency just to try the SDK.

This talks to the server over plain HTTP -- it never touches Postgres or
any of the governance logic directly (see api/main.py for that). That's
the point: self-hosters run the server, everyone else just installs this.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class GovernedMemoryError(Exception):
    """Raised for any non-2xx response from the API server.

    `status_code` and `detail` let a caller branch on what went wrong
    (e.g. 401 = bad API key, 404 = memory not found, 501 = not implemented
    yet pending E6). Connection-level failures (server unreachable, DNS,
    timeout) are not wrapped -- those surface as the underlying
    urllib.error.URLError, a genuinely different failure mode.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


@dataclass
class Source:
    """Where a memory came from. Maps to core.models.Provenance server-side
    (source_type/source_ref there; type/ref here, matching the engineering
    plan's documented SDK sample)."""

    type: str
    ref: str
    confidence: float = 1.0


class GovernedMemory:
    """Client for one tenant's self-hosted GovernedMemory API server.

    >>> mem = GovernedMemory(base_url="http://localhost:8000", api_key="...")
    >>> mem.write(
    ...     customer_id="cust-1", agent_id="cx-1", session_id="s-1",
    ...     content="customer prefers email contact",
    ...     source=Source(type="user", ref="msg-1001", confidence=0.9),
    ... )
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = self._base_url + path
        if query:
            params = {k: v for k, v in query.items() if v is not None}
            if params:
                url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(json_body).encode() if json_body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            body = e.read()
            detail = e.reason
            if body:
                try:
                    detail = json.loads(body).get("detail", detail)
                except json.JSONDecodeError:
                    pass
            raise GovernedMemoryError(e.code, detail) from None

    def write(
        self,
        *,
        customer_id: str,
        agent_id: str,
        session_id: str,
        content: str,
        source: Source,
        purpose: list[str] | None = None,
    ) -> dict:
        """Write a new governed memory. Returns the created record (a dict
        matching core.models.MemoryRecord's fields)."""
        body: dict[str, Any] = {
            "customer_id": customer_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "content": content,
            "provenance": {
                "source_type": source.type,
                "source_ref": source.ref,
                "confidence": source.confidence,
            },
        }
        if purpose is not None:
            body["purpose"] = {"allowed_purposes": purpose}
        return self._request("POST", "/v1/memory", json_body=body)

    def retrieve(
        self,
        *,
        query: str,
        agent_id: str,
        session_id: str,
        purpose: str | None = None,
        k: int = 10,
        include_untrusted: bool = False,
    ) -> list[dict]:
        """Governed hybrid retrieval. Returns matching records (taint- and
        purpose-filtered server-side), most relevant first."""
        body = {
            "query": query,
            "agent_id": agent_id,
            "session_id": session_id,
            "purpose": purpose,
            "k": k,
            "include_untrusted": include_untrusted,
        }
        return self._request("POST", "/v1/retrieve", json_body=body)

    def quarantine(self, memory_id: str, reason: str = "manual quarantine") -> bool:
        resp = self._request(
            "POST", "/v1/quarantine", json_body={"memory_id": memory_id, "reason": reason}
        )
        return resp["success"]

    def delete(self, memory_id: str, cascade: bool = False) -> bool:
        """Delete a memory. cascade=True also hard-deletes every memory
        transitively derived from it (E6's provenance graph) -- irreversible,
        same as a plain delete. Use cascade_preview() first to see the delete
        set without touching the database."""
        resp = self._request(
            "DELETE", f"/v1/memory/{memory_id}", query={"cascade": str(cascade).lower()}
        )
        return resp["success"]

    def cascade_preview(self, memory_id: str) -> dict:
        """Dry-run for delete(memory_id, cascade=True): what would be
        deleted -- {root_id, descendant_ids, descendant_count} -- without
        deleting anything."""
        return self._request("GET", f"/v1/memory/{memory_id}/cascade-preview")

    def audit(self, limit: int = 50) -> list[dict]:
        """Most recent audit events for this tenant, newest first."""
        return self._request("GET", "/v1/audit", query={"limit": limit})

    def provenance(self, memory_id: str) -> dict:
        """A memory's lineage (E6): {memory_id, ancestors, descendants},
        each a list of memory ids walked transitively over parent_ids."""
        return self._request("GET", f"/v1/provenance/{memory_id}")

    def list_customers(self) -> list[dict]:
        """Distinct customers for this tenant, with memory counts and last
        activity -- for navigation UIs."""
        return self._request("GET", "/v1/customers")

    def list_memories(self, customer_id: str) -> list[dict]:
        """All memories for one customer, newest first. Unlike retrieve(),
        this applies no query, ranking, or privilege gate -- a plain listing
        scoped by customer_id only."""
        return self._request("GET", "/v1/memories", query={"customer_id": customer_id})
