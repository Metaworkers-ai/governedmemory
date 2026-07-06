"""
Privilege gate for the Retrieval Engine (E3).

Read-path enforcement of the trust/purpose model E1/E2 only established at
write time. Before this, `quarantine()`'s own docstring claimed a quarantined
record was "blocked by the privilege gate on retrieval" — but no such gate
existed; vector_search/lexical_search returned untrusted and quarantined
records exactly like trusted ones, and `allowed_purposes` was stored but
never checked. This module is that gate.

Two independent checks, both must pass:
  - Taint: only `trusted` records pass by default. `include_untrusted=True`
    (a deliberate, named opt-in — e.g. a governance/audit dashboard that
    wants to see everything) skips this check entirely.
  - Purpose: if the caller supplies a `purpose` and the record has a
    non-empty `allowed_purposes`, the purpose must be in that list. An
    empty `allowed_purposes` means the write never restricted its use —
    open to any purpose, mirroring the same "empty = open" convention
    Access.acl already uses.
"""

from __future__ import annotations

from core.models import MemoryRecord, Taint


def apply_privilege_gate(
    records: list[MemoryRecord],
    purpose: str | None = None,
    include_untrusted: bool = False,
) -> list[MemoryRecord]:
    """Filter records by taint and purpose binding. Preserves input order."""
    result = []
    for record in records:
        if not include_untrusted and record.trust.taint != Taint.TRUSTED:
            continue
        if (
            purpose
            and record.purpose.allowed_purposes
            and purpose not in record.purpose.allowed_purposes
        ):
            continue
        result.append(record)
    return result
