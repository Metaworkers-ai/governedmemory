"""In-memory governance bookkeeping for one AgentDojo task attempt.

See the reviewed low-level design, section 8 ("RunGovernanceContext"). This
module is pure bookkeeping: it holds ordered references to memories already
written via `MemoryStore.write()` and to privileged-action decisions already
made via `MemoryStore.check_privilege()`. It does not itself call
GovernedMemory -- the tool wrappers built in a later implementation step do
that, and append the results here so later wrappers (e.g. the privileged-
action gate) can see everything written earlier in the same attempt without
ever querying the database for "the latest row" (a lookup the design
explicitly rules out; see the LLD's memory-resolution rule in section 13).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from integrations.agentdojo.identity import RunIdentity


@dataclass(frozen=True)
class EvidenceRef:
    """One piece of evidence written to GovernedMemory during this attempt.

    Populated by a tool wrapper immediately after a successful
    `MemoryStore.write()` call -- never speculatively, never before the
    write actually happens.
    """

    memory_id: str
    sequence: int
    source_kind: str  # "user_input" | "tool_output"
    tool_name: str | None
    source_ref: str
    taint: str
    injection_score: float
    policy_id: str
    audit_id: str | None = None
    write_latency_ms: float | None = None
    """Wall-clock time spent inside the MemoryStore.write() call that
    produced this record, in milliseconds. Populated by the writer
    (GovernedRunInitializer / source-tool wrapper / privileged-tool
    wrapper), never estimated after the fact. Needed for the LLD section
    16 benchmark metric `write_latency_ms`; None only if the caller
    predates this field (kept optional for backward compatibility)."""


@dataclass(frozen=True)
class ActionEvent:
    """One privileged-action gating decision made during this attempt.

    Populated by a privileged-tool wrapper after it has evaluated
    `check_privilege()` against every evidence id selected by the configured
    gate policy. `evidence_ids` is the full snapshot that was checked, not
    just the ones that failed.
    """

    sequence: int
    tool_name: str
    evidence_ids: tuple[str, ...]
    allowed: bool
    denied_memory_ids: tuple[str, ...]
    reason: str
    gate_latency_ms: float | None = None
    """Wall-clock time spent evaluating check_privilege() across every
    selected evidence id in this decision (the whole gate loop, not a
    single call), in milliseconds. Needed for the LLD section 16
    benchmark metric `gate_latency_ms`."""


@dataclass
class RunGovernanceContext:
    """Ordered evidence + action history for exactly one task attempt.

    One instance per attempt. Never shared across attempts, never reused
    after an attempt completes -- see RunContextRegistry (registry.py) for
    how instances are looked up by wrapped tools and cleaned up afterward.
    """

    identity: RunIdentity
    evidence: list[EvidenceRef] = field(default_factory=list)
    actions: list[ActionEvent] = field(default_factory=list)
    processed_initial_input: bool = False
    infrastructure_errors: list[str] = field(default_factory=list)
    _next_sequence: int = field(default=0, repr=False)

    # -- identity passthrough, so callers don't need `context.identity.x` --

    @property
    def tenant_id(self) -> str:
        return self.identity.tenant_id

    @property
    def customer_id(self) -> str:
        return self.identity.customer_id

    @property
    def agent_id(self) -> str:
        return self.identity.agent_id

    @property
    def session_id(self) -> str:
        return self.identity.session_id

    @property
    def policy_id(self) -> str:
        return self.identity.policy_id

    # -- sequencing --

    def next_sequence(self) -> int:
        """Reserve the next sequence number.

        Call exactly once per evidence write or action event, in the order
        those things actually happen. Sequence order is what "ordered
        evidence" and "most recently written" mean everywhere else in this
        design -- assigning sequence numbers out of order, or reusing one,
        would silently corrupt the evidence gate in a later step.
        """
        seq = self._next_sequence
        self._next_sequence += 1
        return seq

    # -- appenders --

    def append_evidence(self, ref: EvidenceRef) -> None:
        """Record one piece of evidence. `ref.sequence` must have been
        reserved by an earlier `next_sequence()` call and not already used
        by any evidence or action entry in this context -- using an
        unreserved or already-used sequence indicates a caller bug (e.g.
        constructing an EvidenceRef without calling next_sequence() first,
        or two wrappers racing on the same context) and is rejected rather
        than silently accepted."""
        self._check_sequence_available(ref.sequence)
        self.evidence.append(ref)

    def append_action(self, action: ActionEvent) -> None:
        """Record one privileged-action decision. Same sequence rules as
        append_evidence -- see there. Evidence and actions share one
        sequence space (see next_sequence()'s docstring), since a
        privileged tool call that's allowed writes both an EvidenceRef
        (its confirmation output) and an ActionEvent (the decision) in the
        same step; sequence order across both lists together is what
        reconstructs "what happened when" for one attempt."""
        self._check_sequence_available(action.sequence)
        self.actions.append(action)

    def _check_sequence_available(self, sequence: int) -> None:
        if sequence < 0 or sequence >= self._next_sequence:
            raise ValueError(
                f"sequence {sequence} was never reserved via next_sequence() "
                f"(this attempt has issued sequences 0..{self._next_sequence - 1}); "
                f"tenant={self.tenant_id!r}"
            )
        if any(e.sequence == sequence for e in self.evidence) or any(
            a.sequence == sequence for a in self.actions
        ):
            raise ValueError(
                f"sequence {sequence} has already been used by an evidence "
                f"or action entry (tenant={self.tenant_id!r})"
            )

    # -- readers --

    def ordered_evidence_ids(self, *, include_user_input: bool = True) -> tuple[str, ...]:
        """Snapshot of every evidence memory_id written so far, in sequence
        order. `include_user_input=False` implements AgentDojo's
        tool-output-only gate while retaining the initial message for audit;
        strict comparison mode leaves it True. This is never a "most recent"
        or semantic lookup. Sorted by sequence explicitly rather than relying
        on append order, since evidence and actions can interleave."""
        return tuple(
            e.memory_id
            for e in sorted(self.evidence, key=lambda e: e.sequence)
            if include_user_input or e.source_kind != "user_input"
        )

    def write_latencies_ms(self) -> tuple[float, ...]:
        """Every recorded write_latency_ms across this attempt's evidence,
        in sequence order, excluding any entries where it wasn't captured
        (None). Used to compute the LLD section 16 `write_latency_ms`
        benchmark metric -- aggregation (mean/median/etc.) is the caller's
        choice, this just returns the raw per-write samples."""
        return tuple(e.write_latency_ms for e in self.evidence if e.write_latency_ms is not None)

    def gate_latencies_ms(self) -> tuple[float, ...]:
        """Every recorded gate_latency_ms across this attempt's actions, in
        sequence order, excluding any entries where it wasn't captured.
        Used to compute the LLD section 16 `gate_latency_ms` benchmark
        metric."""
        return tuple(a.gate_latency_ms for a in self.actions if a.gate_latency_ms is not None)

    @property
    def has_infrastructure_error(self) -> bool:
        return len(self.infrastructure_errors) > 0

    def mark_infrastructure_error(self, message: str) -> None:
        """Record an infrastructure failure for this attempt (e.g. a write
        that could not be governed). Per the LLD's failure-semantics table,
        an attempt with any infrastructure error must be excluded from
        security/utility metrics rather than counted as a successful
        defense or a valid benign run."""
        self.infrastructure_errors.append(message)
