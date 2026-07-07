"""
Policy evaluator (E4).

The Policy model (core/models/policy.py) existed since E1 — a policy table,
purpose_bindings, privilege_rules, a policy_id stamped on every memory — but
nothing ever read it. Every write defaulted policy_id="default" and every
retrieval only checked a record's own allowed_purposes (E3's privilege gate).
AuditOp.POLICY_DECISION was defined and never emitted. This module is what
actually evaluates a Policy document; MemoryStore wires it in.

Two independent evaluations, matching the two halves of the Policy model:

  - Purpose binding: given a purpose and a policy, is the retrieved record's
    source_type an acceptable origin for that purpose? A purpose with no
    binding defined, or a binding with an empty allowed_source_types, is
    permissive by default — mirroring the same "empty = open" convention
    used throughout (Access.acl, Purpose.allowed_purposes). This is a
    *tenant-level* policy check, layered on top of E3's *record-level*
    allowed_purposes check — they answer different questions ("should this
    purpose ever use this kind of source?" vs. "did this specific write
    restrict itself to certain purposes?").

  - Privileged action: given an action name and a memory's current taint,
    is the action allowed? PrivilegeRules.privileged_actions defaults to
    ["send_email", "refund", "escalate"] with require_trust=True — so by
    default, any of those three actions are denied against untrusted or
    quarantined memories, even with zero policy configuration.
"""

from __future__ import annotations

from collections.abc import Callable

from core.models import MemoryRecord, Policy, Taint


def evaluate_purpose_binding(policy: Policy, purpose: str, source_type: str) -> tuple[bool, str]:
    """Is `source_type` an acceptable origin for `purpose` under this policy?"""
    binding = next((b for b in policy.purpose_bindings if b.purpose == purpose), None)
    if binding is None:
        return (
            True,
            f"no binding defined for purpose '{purpose}' under policy '{policy.id}' — default allow",
        )
    if not binding.allowed_source_types:
        return True, f"binding for '{purpose}' allows any source type"
    if source_type in binding.allowed_source_types:
        return True, f"source_type '{source_type}' is allowed for purpose '{purpose}'"
    return False, (
        f"source_type '{source_type}' not in allowed_source_types "
        f"{binding.allowed_source_types} for purpose '{purpose}'"
    )


def evaluate_privileged_action(policy: Policy, action: str, taint: Taint) -> tuple[bool, str]:
    """May `action` be performed using a memory with this taint, under this policy?"""
    rules = policy.privilege_rules
    if action not in rules.privileged_actions:
        return True, f"'{action}' is not a privileged action under policy '{policy.id}'"
    if rules.require_trust and taint != Taint.TRUSTED:
        return False, f"'{action}' requires a trusted memory; this record is taint={taint.value}"
    return True, f"'{action}' is permitted — memory is trusted"


def filter_by_purpose_binding(
    records: list[MemoryRecord],
    purpose: str | None,
    policy_lookup: Callable[[str], Policy],
) -> list[MemoryRecord]:
    """
    Filter records by the tenant-level purpose binding of the policy each
    record was written under (record.purpose.policy_id). No-op if `purpose`
    is not given. `policy_lookup` is cached per policy_id within this call
    so records sharing the common "default" policy don't refetch it.
    """
    if not purpose:
        return records
    cache: dict[str, Policy] = {}
    result = []
    for record in records:
        policy_id = record.purpose.policy_id
        if policy_id not in cache:
            cache[policy_id] = policy_lookup(policy_id)
        allowed, _ = evaluate_purpose_binding(
            cache[policy_id], purpose, record.provenance.source_type.value
        )
        if allowed:
            result.append(record)
    return result
