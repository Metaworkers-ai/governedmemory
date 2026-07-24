"""Unit tests for integrations/agentdojo/registry.py.

Covers the LLD's unit-test list (section 18) items that concern the
registry directly:

- Missing context fails closed.
- Independent environments cannot see one another's contexts.
- Concurrent task runs do not cross-contaminate evidence.
- Cleanup runs after success and exceptions.
"""

import threading

import pytest

from integrations.agentdojo.context import RunGovernanceContext
from integrations.agentdojo.identity import generate_run_identity
from integrations.agentdojo.registry import (
    RegistryCollisionError,
    RegistryMissError,
    RunContextRegistry,
)


class FakeEnvironment:
    """Stand-in for an AgentDojo TaskEnvironment instance. Only identity
    matters to the registry, so a bare object is enough."""


def _make_context(user_task_id: str = "user_task_1") -> RunGovernanceContext:
    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite="banking",
        user_task_id=user_task_id,
        agent_id="gpt-4o",
    )
    return RunGovernanceContext(identity=identity)


class TestRegisterGetUnregister:
    def test_get_after_register_returns_the_same_context(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()
        context = _make_context()

        registry.register(env, context)
        assert registry.get(env) is context

    def test_get_without_registration_fails_closed(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()

        with pytest.raises(RegistryMissError):
            registry.get(env)

    def test_get_after_unregister_fails_closed(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()
        registry.register(env, _make_context())

        registry.unregister(env)

        with pytest.raises(RegistryMissError):
            registry.get(env)

    def test_unregister_is_idempotent(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()
        # Unregistering something never registered must not raise.
        registry.unregister(env)
        registry.unregister(env)

    def test_double_registration_on_same_environment_collides(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()
        registry.register(env, _make_context("first"))

        with pytest.raises(RegistryCollisionError):
            registry.register(env, _make_context("second"))

    def test_register_after_unregister_succeeds(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()
        registry.register(env, _make_context("first"))
        registry.unregister(env)

        second = _make_context("second")
        registry.register(env, second)  # should not raise
        assert registry.get(env) is second


class TestIndependentEnvironmentsAreIsolated:
    def test_two_environments_have_separate_contexts(self):
        registry = RunContextRegistry()
        env_a, env_b = FakeEnvironment(), FakeEnvironment()
        ctx_a, ctx_b = _make_context("task_a"), _make_context("task_b")

        registry.register(env_a, ctx_a)
        registry.register(env_b, ctx_b)

        assert registry.get(env_a) is ctx_a
        assert registry.get(env_b) is ctx_b
        assert registry.get(env_a).tenant_id != registry.get(env_b).tenant_id


class TestRunContextManager:
    def test_run_registers_and_cleans_up_on_success(self):
        registry = RunContextRegistry()
        env = FakeEnvironment()
        context = _make_context()

        with registry.run(env, context) as ctx:
            assert ctx is context
            assert registry.get(env) is context

        with pytest.raises(RegistryMissError):
            registry.get(env)

    def test_run_cleans_up_on_exception(self):
        """LLD section 7: cleanup must happen 'including exceptional exits.'"""
        registry = RunContextRegistry()
        env = FakeEnvironment()
        context = _make_context()

        with pytest.raises(RuntimeError):
            with registry.run(env, context):
                raise RuntimeError("simulated tool-execution failure")

        with pytest.raises(RegistryMissError):
            registry.get(env)


class TestConcurrentRegistrations:
    def test_many_threads_registering_distinct_environments_do_not_cross_contaminate(self):
        """LLD section 18: 'Concurrent task runs do not cross-contaminate
        evidence.' Each thread registers its own environment/context pair
        and immediately re-reads it back; any lock bug that let one
        thread's context leak into another's slot would surface as a
        mismatch here."""
        registry = RunContextRegistry()
        n_threads = 32
        mismatches: list[str] = []
        barrier = threading.Barrier(n_threads)

        def worker(index: int) -> None:
            env = FakeEnvironment()
            context = _make_context(f"task_{index}")
            barrier.wait()  # maximize actual concurrent access to the lock
            registry.register(env, context)
            read_back = registry.get(env)
            if read_back is not context or read_back.customer_id != f"task_{index}":
                mismatches.append(f"thread {index} saw {read_back.customer_id!r}")
            registry.unregister(env)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert mismatches == []
        assert len(registry) == 0

    def test_registry_len_reflects_live_registrations(self):
        registry = RunContextRegistry()
        envs = [FakeEnvironment() for _ in range(5)]
        for i, env in enumerate(envs):
            registry.register(env, _make_context(f"task_{i}"))
        assert len(registry) == 5

        registry.unregister(envs[0])
        assert len(registry) == 4
