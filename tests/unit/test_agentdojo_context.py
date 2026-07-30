"""Unit tests for integrations/agentdojo/identity.py and context.py.

Pure Python, no Docker, no GovernedMemory database -- these validate the
in-memory bookkeeping objects the AgentDojo integration is built on, per
the reviewed low-level design's section 7 ("Run identity and isolation")
and section 8 ("RunGovernanceContext").
"""

import pytest

from integrations.agentdojo.context import ActionEvent, EvidenceRef, RunGovernanceContext
from integrations.agentdojo.identity import generate_run_identity


class TestGenerateRunIdentity:
    def test_tenant_id_embeds_benchmark_version_suite_and_a_uuid(self):
        identity = generate_run_identity(
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            agent_id="gpt-4o",
        )
        parts = identity.tenant_id.split(":")
        assert parts[0] == "agentdojo"
        assert parts[1] == "1.2.2"
        assert parts[2] == "banking"
        # The run_uuid segment should be a plain uuid4 hex string.
        assert len(parts[3]) == 32
        int(parts[3], 16)  # raises ValueError if not valid hex

    def test_two_calls_never_share_a_tenant(self):
        """LLD section 7: 'Never reuse a tenant across independent task
        attempts.' Even identical inputs must yield distinct tenants."""
        kwargs = dict(
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            agent_id="gpt-4o",
        )
        first = generate_run_identity(**kwargs)
        second = generate_run_identity(**kwargs)
        assert first.tenant_id != second.tenant_id

    def test_customer_id_is_the_user_task_id(self):
        identity = generate_run_identity(
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_7",
            agent_id="gpt-4o",
        )
        assert identity.customer_id == "user_task_7"

    def test_session_id_includes_injection_task_and_attempt(self):
        identity = generate_run_identity(
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            agent_id="gpt-4o",
            injection_task_id="injection_task_5",
            attempt=2,
        )
        assert identity.session_id == "user_task_3:injection_task_5:2"

    def test_session_id_uses_none_placeholder_without_injection_task(self):
        identity = generate_run_identity(
            benchmark_version="1.2.2",
            suite="banking",
            user_task_id="user_task_3",
            agent_id="gpt-4o",
        )
        assert identity.session_id == "user_task_3:none:0"

    def test_default_policy_id_is_default(self):
        identity = generate_run_identity(
            benchmark_version="1.2.2", suite="banking", user_task_id="t", agent_id="a"
        )
        assert identity.policy_id == "default"

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(benchmark_version="1.2.2", suite="", user_task_id="t", agent_id="a"),
            dict(benchmark_version="1.2.2", suite="banking", user_task_id="", agent_id="a"),
            dict(benchmark_version="1.2.2", suite="banking", user_task_id="t", agent_id=""),
        ],
    )
    def test_blank_required_fields_are_rejected(self, kwargs):
        with pytest.raises(ValueError):
            generate_run_identity(**kwargs)

    def test_negative_attempt_is_rejected(self):
        with pytest.raises(ValueError):
            generate_run_identity(
                benchmark_version="1.2.2",
                suite="banking",
                user_task_id="t",
                agent_id="a",
                attempt=-1,
            )


def _make_context(**overrides) -> RunGovernanceContext:
    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite="banking",
        user_task_id="user_task_3",
        agent_id="gpt-4o",
    )
    return RunGovernanceContext(identity=identity, **overrides)


def _evidence(
    sequence: int, memory_id: str = "mem-1", source_kind: str = "tool_output"
) -> EvidenceRef:
    return EvidenceRef(
        memory_id=memory_id,
        sequence=sequence,
        source_kind=source_kind,
        tool_name="get_most_recent_transactions",
        source_ref="agentdojo:banking:get_most_recent_transactions:0",
        taint="untrusted",
        injection_score=0.91,
        policy_id="default",
    )


class TestRunGovernanceContextIdentityPassthrough:
    def test_exposes_identity_fields_directly(self):
        ctx = _make_context()
        assert ctx.tenant_id == ctx.identity.tenant_id
        assert ctx.customer_id == ctx.identity.customer_id
        assert ctx.agent_id == ctx.identity.agent_id
        assert ctx.session_id == ctx.identity.session_id
        assert ctx.policy_id == "default"


class TestRunGovernanceContextSequencing:
    def test_next_sequence_increments_from_zero(self):
        ctx = _make_context()
        assert ctx.next_sequence() == 0
        assert ctx.next_sequence() == 1
        assert ctx.next_sequence() == 2

    def test_append_evidence_in_order_succeeds(self):
        ctx = _make_context()
        seq0 = ctx.next_sequence()
        ctx.append_evidence(_evidence(seq0, "mem-a"))
        seq1 = ctx.next_sequence()
        ctx.append_evidence(_evidence(seq1, "mem-b"))
        assert ctx.ordered_evidence_ids() == ("mem-a", "mem-b")

    def test_can_exclude_initial_user_input_from_gate_snapshot(self):
        ctx = _make_context()
        user_seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(user_seq, "mem-user", "user_input"))
        tool_seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(tool_seq, "mem-tool", "tool_output"))

        assert ctx.ordered_evidence_ids() == ("mem-user", "mem-tool")
        assert ctx.ordered_evidence_ids(include_user_input=False) == ("mem-tool",)

    def test_append_evidence_out_of_order_is_rejected(self):
        ctx = _make_context()
        ctx.next_sequence()  # reserves 0, but we deliberately skip appending it
        out_of_order = _evidence(sequence=1, memory_id="mem-b")
        with pytest.raises(ValueError):
            ctx.append_evidence(out_of_order)

    def test_append_evidence_duplicate_sequence_is_rejected(self):
        ctx = _make_context()
        seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(seq, "mem-a"))
        with pytest.raises(ValueError):
            ctx.append_evidence(_evidence(seq, "mem-b"))  # reusing an already-used sequence

    def test_append_evidence_with_unreserved_sequence_is_rejected(self):
        """A sequence number that was never returned by next_sequence()
        must be rejected outright, not just out-of-order ones."""
        ctx = _make_context()
        with pytest.raises(ValueError):
            ctx.append_evidence(_evidence(0, "mem-a"))

    def test_evidence_and_actions_share_one_sequence_space(self):
        """A privileged tool call that's allowed writes both an
        EvidenceRef (its confirmation output) and an ActionEvent (the
        decision) using two sequence numbers from the same counter --
        appending evidence after an action must not be treated as
        'out of order' just because len(evidence) no longer matches the
        next sequence number."""
        ctx = _make_context()
        evidence_seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(evidence_seq, "mem-a"))

        action_seq = ctx.next_sequence()
        ctx.append_action(
            ActionEvent(
                sequence=action_seq,
                tool_name="send_money",
                evidence_ids=("mem-a",),
                allowed=True,
                denied_memory_ids=(),
                reason="all evidence trusted",
            )
        )

        # A further evidence write (e.g. the privileged tool's own
        # confirmation output) must still succeed even though
        # len(ctx.evidence) == 1 while the next sequence is 2.
        next_evidence_seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(next_evidence_seq, "mem-b"))

        assert ctx.ordered_evidence_ids() == ("mem-a", "mem-b")
        assert [a.sequence for a in ctx.actions] == [action_seq]

    def test_action_sequence_cannot_reuse_an_evidence_sequence(self):
        ctx = _make_context()
        seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(seq, "mem-a"))

        with pytest.raises(ValueError):
            ctx.append_action(
                ActionEvent(
                    sequence=seq,  # already used by the evidence above
                    tool_name="send_money",
                    evidence_ids=("mem-a",),
                    allowed=False,
                    denied_memory_ids=("mem-a",),
                    reason="untrusted",
                )
            )


class TestRunGovernanceContextActionsAndErrors:
    def test_append_action_records_it(self):
        ctx = _make_context()
        evidence_seq = ctx.next_sequence()
        ctx.append_evidence(_evidence(evidence_seq, "mem-a"))
        action_seq = ctx.next_sequence()
        action = ActionEvent(
            sequence=action_seq,
            tool_name="send_money",
            evidence_ids=("mem-a",),
            allowed=False,
            denied_memory_ids=("mem-a",),
            reason="untrusted evidence",
        )
        ctx.append_action(action)
        assert ctx.actions == [action]

    def test_infrastructure_error_tracking(self):
        ctx = _make_context()
        assert ctx.has_infrastructure_error is False
        ctx.mark_infrastructure_error("database unavailable during write")
        assert ctx.has_infrastructure_error is True
        assert ctx.infrastructure_errors == ["database unavailable during write"]

    def test_processed_initial_input_defaults_false(self):
        assert _make_context().processed_initial_input is False
