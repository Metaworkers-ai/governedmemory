"""Unit tests for integrations/agentdojo/run_initializer.py.

Requires `agentdojo` (GovernedRunInitializer subclasses its
BasePipelineElement and raises its AbortAgentError) -- skips cleanly if
it's not installed, same pattern as tests/contract/.

Uses a FakeStore rather than a real MemoryStore/Postgres: this module's own
logic (idempotency, context lookup, evidence bookkeeping, fail-closed
behavior) doesn't depend on real persistence, and is fully exercised
without Docker. What a real write() actually does with this content
(taint scoring etc.) is already covered by core/'s own test suite.
"""

from __future__ import annotations

import pytest

agentdojo = pytest.importorskip("agentdojo")

from agentdojo.agent_pipeline.errors import AbortAgentError  # noqa: E402
from agentdojo.functions_runtime import EmptyEnv, FunctionsRuntime  # noqa: E402

from core.models import (  # noqa: E402
    MemoryRecord,
    SourceType,
    Taint,
    Trust,
    WriteRequest,
)
from integrations.agentdojo.context import RunGovernanceContext  # noqa: E402
from integrations.agentdojo.identity import generate_run_identity  # noqa: E402
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402
from integrations.agentdojo.run_initializer import GovernedRunInitializer  # noqa: E402


class FakeStore:
    """Records WriteRequests and returns a real MemoryRecord built from
    each one, mirroring MemoryStore.write()'s contract without touching a
    database."""

    def __init__(self, *, taint: Taint = Taint.TRUSTED, injection_score: float = 0.01) -> None:
        self.writes: list[WriteRequest] = []
        self._taint = taint
        self._injection_score = injection_score
        self.fail_with: Exception | None = None

    def write(self, req: WriteRequest) -> MemoryRecord:
        if self.fail_with is not None:
            raise self.fail_with
        self.writes.append(req)
        return MemoryRecord(
            tenant_id=req.tenant_id,
            customer_id=req.customer_id,
            agent_id=req.agent_id,
            session_id=req.session_id,
            content=req.content,
            provenance=req.provenance,
            trust=Trust(taint=self._taint, injection_score=self._injection_score),
            purpose=req.purpose,
        )


def _context() -> RunGovernanceContext:
    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite="banking",
        user_task_id="user_task_1",
        agent_id="test-agent",
    )
    return RunGovernanceContext(identity=identity)


def _wire(store: FakeStore, context: RunGovernanceContext):
    """Build a GovernedRunInitializer + registry with `context` registered
    against a fresh fake environment, and return (initializer, env,
    registry)."""
    registry = RunContextRegistry()
    env = EmptyEnv()
    registry.register(env, context)
    initializer = GovernedRunInitializer(store, registry=registry)
    return initializer, env, registry


class TestWritesInitialPromptOnce:
    def test_writes_exactly_one_write_request(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)

        initializer.query("please transfer $50 to my landlord", FunctionsRuntime([]), env)

        assert len(store.writes) == 1

    def test_write_uses_user_source_type_and_context_identity(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)

        initializer.query("please transfer $50 to my landlord", FunctionsRuntime([]), env)

        req = store.writes[0]
        assert req.content == "please transfer $50 to my landlord"
        assert req.provenance.source_type == SourceType.USER
        assert req.provenance.source_ref == f"agentdojo:user:{context.customer_id}"
        assert req.tenant_id == context.tenant_id
        assert req.customer_id == context.customer_id
        assert req.agent_id == context.agent_id
        assert req.session_id == context.session_id
        assert req.purpose.policy_id == context.policy_id

    def test_second_call_on_same_environment_does_not_write_again(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)

        initializer.query("first call", FunctionsRuntime([]), env)
        initializer.query("second call", FunctionsRuntime([]), env)

        assert len(store.writes) == 1
        assert store.writes[0].content == "first call"

    def test_marks_processed_initial_input(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)

        assert context.processed_initial_input is False
        initializer.query("hello", FunctionsRuntime([]), env)
        assert context.processed_initial_input is True


class TestEvidenceBookkeeping:
    def test_appends_exactly_one_evidence_ref(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)

        initializer.query("hello", FunctionsRuntime([]), env)

        assert len(context.evidence) == 1

    def test_evidence_ref_fields_match_the_written_record(self):
        store = FakeStore(taint=Taint.TRUSTED, injection_score=0.03)
        context = _context()
        initializer, env, _ = _wire(store, context)

        initializer.query("hello", FunctionsRuntime([]), env)

        ref = context.evidence[0]
        assert ref.source_kind == "user_input"
        assert ref.tool_name is None
        assert ref.sequence == 0
        assert ref.taint == "trusted"
        assert ref.injection_score == 0.03
        assert ref.policy_id == context.policy_id
        assert ref.source_ref == f"agentdojo:user:{context.customer_id}"

    def test_ordered_evidence_ids_includes_the_initial_write(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)

        initializer.query("hello", FunctionsRuntime([]), env)

        assert len(context.ordered_evidence_ids()) == 1


class TestPassthrough:
    def test_returns_query_runtime_env_messages_extra_args_unchanged(self):
        store = FakeStore()
        context = _context()
        initializer, env, _ = _wire(store, context)
        runtime = FunctionsRuntime([])
        messages = [{"role": "user", "content": "hello"}]
        extra_args = {"some": "value"}

        result_query, result_runtime, result_env, result_messages, result_extra = initializer.query(
            "hello", runtime, env, messages, extra_args
        )

        assert result_query == "hello"
        assert result_runtime is runtime
        assert result_env is env
        assert result_messages is messages
        assert result_extra is extra_args


class TestFailClosed:
    def test_missing_context_registration_raises_abort_agent_error(self):
        store = FakeStore()
        registry = RunContextRegistry()  # nothing registered
        initializer = GovernedRunInitializer(store, registry=registry)
        env = EmptyEnv()

        with pytest.raises(AbortAgentError):
            initializer.query("hello", FunctionsRuntime([]), env)

        assert len(store.writes) == 0

    def test_write_failure_raises_abort_agent_error(self):
        store = FakeStore()
        store.fail_with = ConnectionError("database unavailable")
        context = _context()
        initializer, env, _ = _wire(store, context)

        with pytest.raises(AbortAgentError):
            initializer.query("hello", FunctionsRuntime([]), env)

    def test_write_failure_marks_infrastructure_error_on_context(self):
        store = FakeStore()
        store.fail_with = ConnectionError("database unavailable")
        context = _context()
        initializer, env, _ = _wire(store, context)

        with pytest.raises(AbortAgentError):
            initializer.query("hello", FunctionsRuntime([]), env)

        assert context.has_infrastructure_error is True

    def test_write_failure_does_not_mark_processed(self):
        """A failed write must not be treated as if evidence exists --
        otherwise a retry-within-attempt (if one were ever added) would
        skip writing evidence that was never actually persisted."""
        store = FakeStore()
        store.fail_with = ConnectionError("database unavailable")
        context = _context()
        initializer, env, _ = _wire(store, context)

        with pytest.raises(AbortAgentError):
            initializer.query("hello", FunctionsRuntime([]), env)

        assert context.processed_initial_input is False
        assert len(context.evidence) == 0


class TestTwoEnvironmentsAreIndependent:
    def test_writes_for_one_environment_do_not_affect_another(self):
        store = FakeStore()
        registry = RunContextRegistry()
        context_a = _context()
        context_b = _context()
        env_a, env_b = EmptyEnv(), EmptyEnv()
        registry.register(env_a, context_a)
        registry.register(env_b, context_b)
        initializer = GovernedRunInitializer(store, registry=registry)

        initializer.query("task for a", FunctionsRuntime([]), env_a)

        assert context_a.processed_initial_input is True
        assert context_b.processed_initial_input is False
        assert len(store.writes) == 1
