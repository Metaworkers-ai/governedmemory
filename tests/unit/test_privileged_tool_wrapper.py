"""Unit tests for integrations/agentdojo/privileged_tool_wrapper.py.

Requires `agentdojo` -- skips cleanly if it's not installed. Uses a
FakeStore (no Docker needed) but routes every call through
GovernedFunctionFactory.wrap() and a real FunctionsRuntime, exercising the
actual end-to-end path a privileged Banking tool call takes.

The real security behavior of check_privilege() itself (unconfigured
tenant vs. configured policy, taint-based allow/deny) is proven against a
real MemoryStore + Postgres in tests/integration/test_banking_policy.py.
This file proves the *wrapper's* logic: which evidence ids get checked,
what happens on denial vs. allow, sequencing, and fail-closed behavior --
using a FakeStore whose check_privilege() the test fully controls.
"""

from __future__ import annotations

import pytest

agentdojo = pytest.importorskip("agentdojo")

from agentdojo.agent_pipeline.errors import AbortAgentError  # noqa: E402
from agentdojo.functions_runtime import EmptyEnv, FunctionsRuntime, make_function  # noqa: E402

from core.models import (  # noqa: E402
    MemoryRecord,
    SourceType,
    Taint,
    Trust,
    WriteRequest,
)
from integrations.agentdojo.context import EvidenceRef, RunGovernanceContext  # noqa: E402
from integrations.agentdojo.function_factory import GovernedFunctionFactory  # noqa: E402
from integrations.agentdojo.identity import generate_run_identity  # noqa: E402
from integrations.agentdojo.privileged_tool_wrapper import (  # noqa: E402
    NonPrivilegedToolMisuseError,
    PrivilegedActionDenied,
    make_banking_privileged_tool_hook,
    make_privileged_tool_hook,
)
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402


class FakeStore:
    """Records WriteRequests and check_privilege() calls; deny/allow and
    failure behavior are fully controlled by the test via `deny_memory_ids`
    and the two `*_fail_with` attributes."""

    def __init__(self) -> None:
        self.writes: list[WriteRequest] = []
        self.check_calls: list[tuple] = []
        self.deny_memory_ids: set[str] = set()
        self.check_privilege_fail_with: Exception | None = None
        self.write_fail_with: Exception | None = None

    def write(self, req: WriteRequest) -> MemoryRecord:
        if self.write_fail_with is not None:
            raise self.write_fail_with
        record = MemoryRecord(
            id=f"mem-confirmation-{len(self.writes)}",
            tenant_id=req.tenant_id,
            customer_id=req.customer_id,
            agent_id=req.agent_id,
            session_id=req.session_id,
            content=req.content,
            provenance=req.provenance,
            trust=Trust(taint=Taint.TRUSTED, injection_score=0.0),
            purpose=req.purpose,
        )
        self.writes.append(req)
        return record

    def check_privilege(self, memory_id, tenant_id, action, agent_id, session_id) -> bool:
        self.check_calls.append((memory_id, tenant_id, action, agent_id, session_id))
        if self.check_privilege_fail_with is not None:
            raise self.check_privilege_fail_with
        return memory_id not in self.deny_memory_ids


def _context() -> RunGovernanceContext:
    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite="banking",
        user_task_id="user_task_1",
        agent_id="test-agent",
    )
    return RunGovernanceContext(identity=identity)


def _seed_evidence(
    context: RunGovernanceContext, memory_id: str, tool_name: str = "get_balance"
) -> None:
    """Manually append an EvidenceRef with a caller-chosen memory_id, so
    tests can precisely control which evidence ids exist before the
    privileged call -- as if an earlier source-tool wrapper call had
    already run."""
    seq = context.next_sequence()
    context.append_evidence(
        EvidenceRef(
            memory_id=memory_id,
            sequence=seq,
            source_kind="tool_output",
            tool_name=tool_name,
            source_ref=f"agentdojo:banking:{tool_name}:{seq}",
            taint="trusted",
            injection_score=0.01,
            policy_id=context.policy_id,
        )
    )


_send_money_calls: list[tuple] = []


def _send_money_like(amount: float, recipient: str) -> str:
    """Sends money to a recipient.

    :param amount: how much to send.
    :param recipient: who to send it to.
    """
    _send_money_calls.append((amount, recipient))
    return f"sent {amount} to {recipient}"


def _wire(store: FakeStore, hook, context: RunGovernanceContext | None = None):
    registry = RunContextRegistry()
    env = EmptyEnv()
    registry.register(env, context or _context())
    original = make_function(_send_money_like)
    factory = GovernedFunctionFactory(registry)
    cloned = factory.wrap(original, hook=hook)
    runtime = FunctionsRuntime([cloned])
    return runtime, env, registry


@pytest.fixture(autouse=True)
def _reset_send_money_calls():
    _send_money_calls.clear()
    yield
    _send_money_calls.clear()


class TestAllEvidenceAllowed:
    def test_original_tool_runs_and_returns_its_result(self):
        store = FakeStore()
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        result, error = runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}
        )

        assert error is None
        assert result == "sent 10.0 to landlord"
        assert _send_money_calls == [(10.0, "landlord")]

    def test_every_evidence_id_gets_checked(self):
        store = FakeStore()
        context = _context()
        _seed_evidence(context, "mem-1")
        _seed_evidence(context, "mem-2")
        _seed_evidence(context, "mem-3")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}, raise_on_error=True
        )

        checked_ids = [call[0] for call in store.check_calls]
        assert checked_ids == ["mem-1", "mem-2", "mem-3"]

    def test_check_privilege_called_with_correct_identity_and_action(self):
        store = FakeStore()
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}, raise_on_error=True
        )

        memory_id, tenant_id, action, agent_id, session_id = store.check_calls[0]
        assert tenant_id == context.tenant_id
        assert action == "send_money"
        assert agent_id == context.agent_id
        assert session_id == context.session_id

    def test_writes_confirmation_evidence_after_success(self):
        store = FakeStore()
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}, raise_on_error=True
        )

        assert len(store.writes) == 1
        req = store.writes[0]
        assert req.content == "sent 10.0 to landlord"
        assert req.provenance.source_type == SourceType.TRUSTED_SYSTEM
        assert req.provenance.source_ref.startswith("agentdojo:banking:send_money:")
        assert req.tenant_id == context.tenant_id

    def test_appends_evidence_then_allowed_action_in_sequence_order(self):
        store = FakeStore()
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}, raise_on_error=True
        )

        assert len(context.evidence) == 2  # seeded mem-1 + the new confirmation
        assert len(context.actions) == 1
        action = context.actions[0]
        assert action.allowed is True
        assert action.tool_name == "send_money"
        assert action.evidence_ids == ("mem-1",)  # snapshot taken BEFORE the confirmation write
        assert action.denied_memory_ids == ()
        # Evidence write happened before the action record, per the LLD's ordering.
        confirmation_evidence = context.evidence[-1]
        assert confirmation_evidence.sequence < action.sequence


class TestAnyDeniedEvidenceBlocksTheAction:
    def test_original_tool_never_runs_when_any_evidence_is_denied(self):
        store = FakeStore()
        store.deny_memory_ids = {"mem-2"}
        context = _context()
        _seed_evidence(context, "mem-1")
        _seed_evidence(context, "mem-2")  # this one will be denied
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(PrivilegedActionDenied):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert _send_money_calls == []
        assert len(store.writes) == 0

    def test_denial_propagates_as_an_ordinary_tool_error_not_an_abort(self):
        """This is the LLD's 'governance-denied tool error' -- a normal
        AgentDojo tool error the agent can see and react to, distinct from
        AbortAgentError which would end the whole attempt."""
        store = FakeStore()
        store.deny_memory_ids = {"mem-1"}
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        result, error = runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}
        )

        assert error is not None
        assert "PrivilegedActionDenied" in error
        assert "send_money" in error

    def test_denial_checks_every_evidence_id_not_just_until_the_first_denial(self):
        store = FakeStore()
        store.deny_memory_ids = {"mem-1"}  # only the first is denied
        context = _context()
        _seed_evidence(context, "mem-1")
        _seed_evidence(context, "mem-2")
        _seed_evidence(context, "mem-3")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(PrivilegedActionDenied):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert len(store.check_calls) == 3  # all three checked, not short-circuited

    def test_denied_action_event_records_exactly_which_memory_ids_failed(self):
        store = FakeStore()
        store.deny_memory_ids = {"mem-1", "mem-3"}
        context = _context()
        _seed_evidence(context, "mem-1")
        _seed_evidence(context, "mem-2")
        _seed_evidence(context, "mem-3")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(PrivilegedActionDenied):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert len(context.actions) == 1
        action = context.actions[0]
        assert action.allowed is False
        assert set(action.denied_memory_ids) == {"mem-1", "mem-3"}
        assert action.evidence_ids == ("mem-1", "mem-2", "mem-3")

    def test_no_evidence_at_all_denies_by_default(self):
        store = FakeStore()
        context = _context()  # no evidence seeded at all
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(PrivilegedActionDenied):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert _send_money_calls == []
        assert len(store.check_calls) == 0  # nothing to check against
        assert len(context.actions) == 1
        assert context.actions[0].allowed is False


class TestInitialUserInputGatePolicy:
    def _seed_untrusted_user_input(self, context: RunGovernanceContext) -> None:
        seq = context.next_sequence()
        context.append_evidence(
            EvidenceRef(
                memory_id="mem-user",
                sequence=seq,
                source_kind="user_input",
                tool_name=None,
                source_ref="agentdojo:user:user_task_1",
                taint="untrusted",
                injection_score=0.907,
                policy_id=context.policy_id,
            )
        )
        context.processed_initial_input = True

    def test_banking_default_audits_but_does_not_gate_on_initial_prompt(self):
        store = FakeStore()
        store.deny_memory_ids = {"mem-user"}
        context = _context()
        self._seed_untrusted_user_input(context)
        hook = make_banking_privileged_tool_hook(store, "send_money")
        runtime, env, _ = _wire(store, hook, context)

        result, error = runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}
        )

        assert error is None
        assert result == "sent 10.0 to landlord"
        assert store.check_calls == []
        assert context.actions[0].allowed is True
        assert context.actions[0].evidence_ids == ()

    def test_strict_mode_still_checks_and_blocks_initial_prompt(self):
        store = FakeStore()
        store.deny_memory_ids = {"mem-user"}
        context = _context()
        self._seed_untrusted_user_input(context)
        hook = make_banking_privileged_tool_hook(
            store, "send_money", include_user_input_in_gate=True
        )
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(PrivilegedActionDenied):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert [call[0] for call in store.check_calls] == ["mem-user"]
        assert _send_money_calls == []


class TestFailClosedOnInfrastructureErrors:
    def test_prior_infrastructure_error_prevents_any_later_side_effect(self):
        store = FakeStore()
        context = _context()
        context.mark_infrastructure_error("earlier write failed")
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(AbortAgentError):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert _send_money_calls == []
        assert store.check_calls == []

    def test_check_privilege_failure_raises_abort_agent_error(self):
        store = FakeStore()
        store.check_privilege_fail_with = ConnectionError("database unavailable")
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(AbortAgentError):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert _send_money_calls == []
        assert context.has_infrastructure_error is True

    def test_confirmation_write_failure_raises_abort_agent_error(self):
        store = FakeStore()
        store.write_fail_with = ConnectionError("database unavailable")
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_privileged_tool_hook(store, "send_money", SourceType.TRUSTED_SYSTEM)
        runtime, env, _ = _wire(store, hook, context)

        with pytest.raises(AbortAgentError):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        # The original tool DID run in this case (the write failure happens
        # after), which is expected -- only the confirmation recording failed.
        assert _send_money_calls == [(10.0, "landlord")]
        assert context.has_infrastructure_error is True


class TestMakeBankingPrivilegedToolHookConvenience:
    def test_looks_up_source_type_automatically(self):
        store = FakeStore()
        context = _context()
        _seed_evidence(context, "mem-1")
        hook = make_banking_privileged_tool_hook(store, "send_money")
        runtime, env, _ = _wire(store, hook, context)

        runtime.run_function(
            env, "_send_money_like", {"amount": 1.0, "recipient": "x"}, raise_on_error=True
        )

        assert store.writes[0].provenance.source_type == SourceType.TRUSTED_SYSTEM

    def test_refuses_a_non_privileged_tool_name(self):
        store = FakeStore()
        with pytest.raises(NonPrivilegedToolMisuseError):
            make_banking_privileged_tool_hook(store, "get_balance")

    @pytest.mark.parametrize(
        "action",
        [
            "send_money",
            "schedule_transaction",
            "update_scheduled_transaction",
            "update_password",
            "update_user_info",
        ],
    )
    def test_accepts_every_real_privileged_action(self, action):
        store = FakeStore()
        make_banking_privileged_tool_hook(store, action)  # should not raise
