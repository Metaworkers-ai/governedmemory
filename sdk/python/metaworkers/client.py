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


class GovernanceDenied(GovernedMemoryError):
    """Raised by an adapter when governance denies external storage."""

    def __init__(self, decision: dict):
        self.decision = decision
        super().__init__(403, decision.get("taint_reason") or "governance denied storage")


class ExternalBindingPending(GovernedMemoryError):
    """Mem0 has IDs, but the governance binding still needs recovery."""

    def __init__(
        self,
        correlation_id: str,
        idempotency_key: str,
        external_memory_ids: list[str],
        claim_token: str | None = None,
    ):
        self.correlation_id = correlation_id
        self.idempotency_key = idempotency_key
        self.external_memory_ids = external_memory_ids
        self.claim_token = claim_token
        super().__init__(409, "external memory binding is pending")


class ExternalOperationFailed(GovernedMemoryError):
    """The external operation reached a terminal failure state."""

    def __init__(self, detail: dict | str):
        self.detail_payload = detail if isinstance(detail, dict) else {"message": detail}
        self.correlation_id = self.detail_payload.get("correlation_id")
        self.idempotency_key = self.detail_payload.get("idempotency_key")
        self.external_memory_ids = self.detail_payload.get("external_memory_ids", [])
        super().__init__(409, self.detail_payload.get("message", str(detail)))


class ExternalOperationInProgress(GovernedMemoryError):
    """Another caller owns the external write for this idempotency key."""

    def __init__(
        self,
        correlation_id: str,
        idempotency_key: str,
        claim_expires_at: str | None = None,
    ):
        self.correlation_id = correlation_id
        self.idempotency_key = idempotency_key
        self.claim_expires_at = claim_expires_at
        super().__init__(409, "external write is already in progress")


class ExternalContractError(GovernedMemoryError):
    """The wrapped Mem0 object returned an unsupported shape."""

    def __init__(
        self,
        detail: str,
        *,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
    ):
        self.correlation_id = correlation_id
        self.idempotency_key = idempotency_key
        super().__init__(502, detail)


class TenantMismatch(GovernedMemoryError):
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            403, f"configured tenant {expected!r} does not match API tenant {actual!r}"
        )


class IdempotencyConflictError(GovernedMemoryError):
    def __init__(self, detail: dict | str):
        self.detail_payload = detail if isinstance(detail, dict) else {"message": detail}
        super().__init__(409, self.detail_payload.get("message", str(detail)))


class ExternalBindingConflictError(IdempotencyConflictError):
    pass


class ExternalScopeError(GovernedMemoryError):
    def __init__(self, detail: dict | str):
        self.detail_payload = detail if isinstance(detail, dict) else {"message": detail}
        super().__init__(403, self.detail_payload.get("message", str(detail)))


class ExternalOperationNotFoundError(GovernedMemoryError):
    def __init__(self, detail: dict | str):
        self.detail_payload = detail if isinstance(detail, dict) else {"message": detail}
        super().__init__(404, self.detail_payload.get("message", str(detail)))


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
                    payload = json.loads(body)
                    detail = payload.get("detail", detail) if isinstance(payload, dict) else payload
                except json.JSONDecodeError:
                    pass
            if isinstance(detail, dict):
                code = detail.get("code")
                if code == "external_operation_failed":
                    raise ExternalOperationFailed(detail) from None
                if code == "external_write_claim_error":
                    raise ExternalOperationFailed(detail) from None
                if code == "external_contract_violation":
                    raise ExternalContractError(
                        detail.get("message", "external contract violation")
                    ) from None
                if code == "tenant_mismatch":
                    raise TenantMismatch(
                        detail.get("expected", ""), detail.get("actual", "")
                    ) from None
                if code == "idempotency_conflict":
                    raise IdempotencyConflictError(detail) from None
                if code == "external_binding_conflict":
                    raise ExternalBindingConflictError(detail) from None
                if code == "external_scope_violation":
                    raise ExternalScopeError(detail) from None
                if code == "external_operation_not_found":
                    raise ExternalOperationNotFoundError(detail) from None
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

    def evaluate_external_write(
        self,
        *,
        customer_id: str,
        agent_id: str,
        session_id: str,
        content: str,
        source: Source,
        idempotency_key: str,
        purpose: str | None = None,
        strict_untrusted_write: bool = False,
        correlation_id: str | None = None,
    ) -> dict:
        """Evaluate a Mem0 write without storing a duplicate memory."""
        return self._request(
            "POST",
            "/v1/external-memories/evaluate-write",
            json_body={
                "customer_id": customer_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "content": content,
                "provenance": {
                    "source_type": source.type,
                    "source_ref": source.ref,
                    "confidence": source.confidence,
                },
                "purpose": purpose,
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_id,
                "strict_untrusted_write": strict_untrusted_write,
            },
        )

    def mark_external_failure(
        self,
        *,
        correlation_id: str,
        reason: str,
        external_memory_ids: list[str] | None = None,
        claim_token: str | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/external-memories/fail",
            json_body={
                "correlation_id": correlation_id,
                "reason": reason,
                "external_memory_ids": external_memory_ids or [],
                "claim_token": claim_token,
            },
        )

    def assert_tenant(self, expected_tenant_id: str) -> None:
        actual = self._request("GET", "/v1/identity")["tenant_id"]
        if actual != expected_tenant_id:
            raise TenantMismatch(expected_tenant_id, actual)

    def bind_external_memories(
        self,
        *,
        correlation_id: str,
        external_memory_ids: list[str],
        claim_token: str | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/external-memories/bind",
            json_body={
                "correlation_id": correlation_id,
                "external_memory_ids": external_memory_ids,
                "claim_token": claim_token,
            },
        )

    def retry_binding(
        self,
        *,
        correlation_id: str,
        external_memory_ids: list[str],
        claim_token: str | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/external-memories/retry-binding",
            json_body={
                "correlation_id": correlation_id,
                "external_memory_ids": external_memory_ids,
                "claim_token": claim_token,
            },
        )

    def complete_external_noop(
        self,
        *,
        correlation_id: str,
        claim_token: str | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/external-memories/complete-noop",
            json_body={"correlation_id": correlation_id, "claim_token": claim_token},
        )

    def evaluate_external_candidates(
        self,
        *,
        candidates: list[dict],
        customer_id: str | None = None,
        agent_id: str,
        session_id: str,
        purpose: str | None = None,
        compatibility_mode: str = "compatible",
        idempotency_key: str | None = None,
    ) -> dict:
        return self._request(
            "POST",
            "/v1/external-memories/evaluate-candidates",
            json_body={
                "candidates": candidates,
                "customer_id": customer_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "purpose": purpose,
                "compatibility_mode": compatibility_mode,
                "idempotency_key": idempotency_key,
            },
        )

    def get_external_governance(self, external_memory_id: str) -> dict:
        return self._request("GET", f"/v1/external-memories/{external_memory_id}/governance")

    def quarantine_external_memory(
        self,
        external_memory_id: str,
        reason: str = "manual quarantine",
        *,
        agent_id: str = "system",
        session_id: str = "external-quarantine",
    ) -> dict:
        return self._request(
            "POST",
            f"/v1/external-memories/{external_memory_id}/quarantine",
            json_body={"reason": reason, "agent_id": agent_id, "session_id": session_id},
        )

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
