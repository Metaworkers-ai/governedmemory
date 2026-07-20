"""Synchronous Mem0 OSS adapter.

Mem0 remains the content/embedding/search system of record.  This adapter
only evaluates proposed writes, binds native Mem0 IDs, and filters/annotates
Mem0 search results using GovernedMemory decisions.
"""

from __future__ import annotations

import uuid
import warnings
from collections.abc import Mapping
from typing import Any

from ..client import (
    ExternalBindingPending,
    GovernanceDenied,
    GovernedMemory,
    GovernedMemoryError,
    Source,
)


class GovernedMem0:
    """Govern an existing synchronous Mem0 ``Memory`` instance."""

    def __init__(
        self,
        mem0: Any,
        governance: GovernedMemory,
        *,
        tenant_id: str,
        agent_id: str | None = None,
        compatibility_mode: str = "compatible",
        untrusted_write_mode: str = "allow",
    ) -> None:
        if compatibility_mode not in {"strict", "observe", "compatible"}:
            raise ValueError("compatibility_mode must be strict, observe, or compatible")
        if untrusted_write_mode not in {"allow", "deny"}:
            raise ValueError("untrusted_write_mode must be allow or deny")
        if not tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        self.mem0 = mem0
        self.governance = governance
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.compatibility_mode = compatibility_mode
        self.untrusted_write_mode = untrusted_write_mode

    @staticmethod
    def _message_content(messages: Any) -> str:
        if isinstance(messages, str):
            return messages
        if isinstance(messages, Mapping):
            return str(messages.get("content", ""))
        if isinstance(messages, list):
            return "\n".join(
                str(item.get("content", ""))
                for item in messages
                if isinstance(item, Mapping) and item.get("content") is not None
            )
        raise TypeError("Mem0 messages must be a string, mapping, or list of mappings")

    @staticmethod
    def _result_items(result: Any) -> tuple[list[Any], bool]:
        if isinstance(result, Mapping):
            items = result.get("results", [])
            return (items if isinstance(items, list) else [], True)
        if isinstance(result, list):
            return result, False
        return [], False

    @staticmethod
    def _external_id(item: Any) -> str | None:
        if not isinstance(item, Mapping):
            return None
        value = item.get("id")
        if value is None and isinstance(item.get("metadata"), Mapping):
            value = item["metadata"].get("id")
        return str(value) if value is not None else None

    @staticmethod
    def _with_governance(result: Any, governance: dict) -> Any:
        if isinstance(result, Mapping):
            enriched = dict(result)
            enriched["governance"] = governance
            return enriched
        return {"results": result, "governance": governance}

    def _context(
        self,
        *,
        user_id: str | None,
        agent_id: str | None,
        run_id: str | None,
        metadata: Mapping[str, Any] | None,
        idempotency_key: str,
    ) -> tuple[str, str, str, str | None, Source]:
        metadata = metadata or {}
        customer_id = str(user_id or metadata.get("customer_id") or agent_id or self.agent_id or "default")
        resolved_agent = str(agent_id or metadata.get("agent_id") or self.agent_id or "mem0-agent")
        session_id = str(run_id or metadata.get("session_id") or idempotency_key)
        purpose = metadata.get("purpose")
        source_type = str(metadata.get("source_type") or "user")
        source_ref = str(metadata.get("source_ref") or f"mem0:{idempotency_key}")
        return customer_id, resolved_agent, session_id, purpose, Source(
            type=source_type, ref=source_ref, confidence=float(metadata.get("confidence", 1.0))
        )

    def add(
        self,
        messages: Any,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        purpose: str | None = None,
        source: Source | None = None,
        idempotency_key: str | None = None,
        untrusted_write_mode: str | None = None,
        **mem0_kwargs: Any,
    ) -> Any:
        """Evaluate, delegate to Mem0, bind IDs, and preserve Mem0 results."""
        key = idempotency_key or str(uuid.uuid4())
        customer_id, resolved_agent, session_id, metadata_purpose, default_source = self._context(
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata,
            idempotency_key=key,
        )
        source = source or default_source
        purpose = purpose or metadata_purpose
        strict = (untrusted_write_mode or self.untrusted_write_mode) == "deny"
        content = self._message_content(messages)
        evaluation = self.governance.evaluate_external_write(
            customer_id=customer_id,
            agent_id=resolved_agent,
            session_id=session_id,
            content=content,
            source=source,
            purpose=purpose,
            idempotency_key=key,
            strict_untrusted_write=strict,
        )
        if evaluation.get("storage") == "deny":
            raise GovernanceDenied(evaluation)
        if evaluation.get("status") == "completed":
            # The caller is replaying an already completed operation.  Do not
            # call Mem0.add() again; the original Mem0 result is intentionally
            # not duplicated in GovernedMemory.
            return {
                "results": [],
                "governance": {**evaluation, "idempotency_key": key, "idempotent_replay": True},
            }
        if evaluation.get("status") == "binding_pending":
            raise ExternalBindingPending(
                evaluation["correlation_id"],
                key,
                evaluation.get("external_memory_ids", []),
            )

        mem0_metadata = dict(metadata or {})
        mem0_metadata.update(
            {
                "governedmemory_correlation_id": evaluation["correlation_id"],
                "governedmemory_operation_id": evaluation.get("operation_id"),
            }
        )
        try:
            result = self.mem0.add(
                messages,
                user_id=user_id or customer_id,
                agent_id=agent_id or resolved_agent,
                run_id=run_id or session_id,
                metadata=mem0_metadata,
                **mem0_kwargs,
            )
        except Exception:
            raise

        items, _ = self._result_items(result)
        external_ids = [external_id for external_id in (self._external_id(i) for i in items) if external_id]
        if not external_ids:
            raise GovernedMemoryError(502, "Mem0 returned no stable memory IDs; governance binding is impossible")
        try:
            bound = self.governance.bind_external_memories(
                correlation_id=evaluation["correlation_id"],
                external_memory_ids=external_ids,
            )
        except Exception as exc:
            raise ExternalBindingPending(
                evaluation["correlation_id"], key, external_ids
            ) from exc
        return self._with_governance(
            result,
            {
                **bound,
                "idempotency_key": key,
                "storage_decision": evaluation.get("storage"),
            },
        )

    def search(
        self,
        query: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        filters: Mapping[str, Any] | None = None,
        top_k: int = 10,
        purpose: str | None = None,
        **mem0_kwargs: Any,
    ) -> Any:
        """Delegate semantic search to Mem0, then batch-filter candidates."""
        search_filters = dict(filters or {})
        if user_id is not None:
            search_filters["user_id"] = user_id
        if agent_id is not None:
            search_filters["agent_id"] = agent_id
        if run_id is not None:
            search_filters["run_id"] = run_id
        result = self.mem0.search(
            query,
            filters=search_filters,
            top_k=top_k,
            **mem0_kwargs,
        )
        items, mapping_result = self._result_items(result)
        resolved_agent = agent_id or self.agent_id or "mem0-agent"
        session_id = run_id or "mem0-search"
        candidates = [{"external_memory_id": self._external_id(item)} for item in items]
        evaluation = self.governance.evaluate_external_candidates(
            candidates=candidates,
            agent_id=resolved_agent,
            session_id=session_id,
            purpose=purpose,
            compatibility_mode=self.compatibility_mode,
        )
        kept: list[Any] = []
        annotated: list[dict] = list(evaluation.get("decisions", []))
        for item, decision in zip(items, evaluation.get("decisions", []), strict=False):
            if decision["decision"] == "exclude":
                continue
            if self.compatibility_mode == "observe" and decision["status"] in {
                "untracked",
                "missing_id",
            }:
                warnings.warn(
                    f"Mem0 result {decision.get('external_memory_id')!r} is untracked",
                    RuntimeWarning,
                    stacklevel=2,
                )
            if isinstance(item, Mapping):
                enriched = dict(item)
                enriched["governance"] = decision
                kept.append(enriched)
            else:
                kept.append(item)
        if mapping_result:
            output = dict(result)
            output["results"] = kept
        else:
            output = kept
        return self._with_governance(
            output,
            {
                "operation_id": evaluation.get("operation_id"),
                "correlation_id": evaluation.get("correlation_id"),
                "audit_id": evaluation.get("audit_id"),
                "compatibility_mode": self.compatibility_mode,
                "decisions": annotated,
            },
        )

    def quarantine(self, external_memory_id: str, reason: str = "manual quarantine") -> dict:
        """Quarantine governance metadata without deleting from Mem0."""
        return self.governance.quarantine_external_memory(external_memory_id, reason)

    def get_governance(self, external_memory_id: str) -> dict:
        return self.governance.get_external_governance(external_memory_id)

    def retry_binding(self, *, correlation_id: str, external_memory_ids: list[str]) -> dict:
        return self.governance.retry_binding(
            correlation_id=correlation_id,
            external_memory_ids=external_memory_ids,
        )
