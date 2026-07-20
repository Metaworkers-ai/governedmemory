"""The one governance decision engine used by native and external writes."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from core.detection import score_injection
from core.governance.models import GovernanceDecision, GovernanceEvaluationRequest
from core.models import Policy, SourceType, Taint
from core.policy_engine import evaluate_purpose_binding

_UNTRUSTED_SOURCE_TYPES = {SourceType.UNTRUSTED_WEB, SourceType.UNTRUSTED_EMAIL}


class GovernanceEvaluationService:
    """Evaluate trust, storage, and retrieval without persisting content.

    The caller owns persistence and audit transaction boundaries.  This keeps
    the service reusable by MemoryStore and external-memory adapters while
    ensuring scanner and policy behavior cannot drift between them.
    """

    def __init__(
        self,
        policy_lookup: Callable[[str, str], Policy] | None = None,
        *,
        injection_threshold: float | None = None,
        severe_injection_threshold: float | None = None,
    ) -> None:
        self._policy_lookup = policy_lookup
        self._injection_threshold = (
            injection_threshold
            if injection_threshold is not None
            else float(os.getenv("INJECTION_THRESHOLD", "0.7"))
        )
        self._severe_injection_threshold = (
            severe_injection_threshold
            if severe_injection_threshold is not None
            else float(os.getenv("SEVERE_INJECTION_THRESHOLD", "0.95"))
        )

    def evaluate(
        self,
        request: GovernanceEvaluationRequest,
        *,
        policy: Policy | None = None,
        strict_untrusted_write: bool = False,
        deny_severe_injection: bool = False,
        correlation_id: str | None = None,
    ) -> GovernanceDecision:
        if not request.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")

        correlation_id = correlation_id or str(uuid.uuid4())
        source_type = request.source_type or (
            request.provenance.source_type if request.provenance else SourceType.USER
        )
        content = request.content or ""
        injection_score, injection_labels = score_injection(content)
        source_untrusted = source_type in _UNTRUSTED_SOURCE_TYPES
        injection_flagged = injection_score >= self._injection_threshold

        reasons: list[str] = []
        if source_untrusted:
            reasons.append(f"source_type={source_type.value}")
        if injection_flagged:
            reasons.append(
                f"injection_score={injection_score:.2f} ({'/'.join(injection_labels)})"
            )

        taint = Taint.UNTRUSTED if source_untrusted or injection_flagged else Taint.TRUSTED
        storage = "allow"
        retrieval = "exclude" if taint != Taint.TRUSTED else "allow"
        policy_id = policy.id if policy else "default"

        if request.purpose and policy:
            allowed, reason = evaluate_purpose_binding(policy, request.purpose, source_type.value)
            if not allowed:
                storage = "deny"
                reasons.append(reason)

        if strict_untrusted_write and taint != Taint.TRUSTED:
            storage = "deny"
            reasons.append("strict_untrusted_write is enabled")
        elif deny_severe_injection and injection_score >= self._severe_injection_threshold:
            storage = "deny"
            reasons.append(
                f"injection_score={injection_score:.2f} meets severe threshold "
                f"{self._severe_injection_threshold:.2f}"
            )

        if storage == "deny":
            retrieval = "exclude"
            status = "denied"
        else:
            status = "evaluated"

        return GovernanceDecision(
            correlation_id=correlation_id,
            storage=storage,
            retrieval=retrieval,
            taint=taint,
            taint_reason="; ".join(reasons) or None,
            injection_score=injection_score,
            injection_labels=injection_labels,
            policy_id=policy_id,
            status=status,
            evaluated_at=datetime.now(UTC),
        )
