"""Unit tests for integrations/agentdojo/function_factory.py.

Requires `agentdojo` (GovernedFunctionFactory clones its Function objects
and raises its AbortAgentError) -- skips cleanly if it's not installed,
same pattern as tests/contract/.

Deliberately routes calls through AgentDojo's own real
`FunctionsRuntime.run_function`, not just direct calls into the wrapped
`Function.run` -- the whole point of this factory is that it works inside
AgentDojo's actual dependency-resolution and schema-validation path, and a
test that bypassed `run_function` could pass while still being wrong about
how AgentDojo really calls a wrapped tool.
"""

from __future__ import annotations

from typing import Annotated

import pytest

agentdojo = pytest.importorskip("agentdojo")

from agentdojo.agent_pipeline.errors import AbortAgentError  # noqa: E402
from agentdojo.functions_runtime import (  # noqa: E402
    Depends,
    FunctionsRuntime,
    TaskEnvironment,
    make_function,
)
from pydantic import BaseModel  # noqa: E402

from integrations.agentdojo.context import RunGovernanceContext  # noqa: E402
from integrations.agentdojo.function_factory import (  # noqa: E402
    HIDDEN_ENV_DEPENDENCY_NAME,
    GovernanceInfrastructureError,
    GovernedFunctionFactory,
    HiddenDependencyCollisionError,
)
from integrations.agentdojo.identity import generate_run_identity  # noqa: E402
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402


class _Account(BaseModel):
    balance: float = 100.0


class _BankEnv(TaskEnvironment):
    bank_account: _Account = _Account()


def _send_money_like(
    account: Annotated[_Account, Depends("bank_account")],
    amount: float,
    recipient: str,
) -> str:
    """Sends money to a recipient.

    :param amount: how much to send.
    :param recipient: who to send it to.
    """
    account.balance -= amount
    return f"sent {amount} to {recipient}, new balance {account.balance}"


def _no_dependency_tool(note: str) -> str:
    """A tool with no dependencies of its own.

    :param note: a note to echo back.
    """
    return f"noted: {note}"


def _context() -> RunGovernanceContext:
    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite="banking",
        user_task_id="user_task_1",
        agent_id="test-agent",
    )
    return RunGovernanceContext(identity=identity)


def _recording_hook(recorded: list):
    def hook(context, original_run, kwargs):
        recorded.append((context, dict(kwargs)))
        return original_run(**kwargs)

    return hook


class TestSchemaPreservation:
    def test_clone_preserves_name_description_return_type_and_docstring(self):
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(RunContextRegistry())

        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))

        assert cloned.name == original.name
        assert cloned.description == original.description
        assert cloned.return_type == original.return_type
        assert cloned.full_docstring == original.full_docstring

    def test_clone_reuses_the_exact_same_parameters_schema_object(self):
        """The public schema must be untouched -- reusing the same object
        (not even a rebuilt equal one) is the strongest guarantee that
        nothing was added or dropped."""
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(RunContextRegistry())

        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))

        assert cloned.parameters is original.parameters

    def test_hidden_dependency_does_not_appear_in_parameters_schema(self):
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(RunContextRegistry())

        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))

        assert HIDDEN_ENV_DEPENDENCY_NAME not in cloned.parameters.model_fields
        assert set(cloned.parameters.model_fields) == {"amount", "recipient"}

    def test_clone_preserves_original_dependencies_plus_the_hidden_one(self):
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(RunContextRegistry())

        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))

        assert set(cloned.dependencies) == {"account", HIDDEN_ENV_DEPENDENCY_NAME}
        assert cloned.dependencies["account"] is original.dependencies["account"]

    def test_wrapping_does_not_mutate_the_original_function(self):
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(RunContextRegistry())

        factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))

        assert HIDDEN_ENV_DEPENDENCY_NAME not in original.dependencies
        assert set(original.dependencies) == {"account"}

    def test_tool_with_no_original_dependencies_gets_only_the_hidden_one(self):
        original = make_function(_no_dependency_tool)
        factory = GovernedFunctionFactory(RunContextRegistry())

        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))

        assert set(cloned.dependencies) == {HIDDEN_ENV_DEPENDENCY_NAME}
        assert set(cloned.parameters.model_fields) == {"note"}


class TestEndToEndThroughRealRuntime:
    def test_hook_is_invoked_with_resolved_context_and_explicit_kwargs(self):
        registry = RunContextRegistry()
        env = _BankEnv()
        context = _context()
        registry.register(env, context)

        recorded: list = []
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(registry)
        cloned = factory.wrap(original, hook=_recording_hook(recorded))
        runtime = FunctionsRuntime([cloned])

        result, error = runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}
        )

        assert error is None
        assert result == "sent 10.0 to landlord, new balance 90.0"
        assert len(recorded) == 1
        recorded_context, recorded_kwargs = recorded[0]
        assert recorded_context is context
        assert HIDDEN_ENV_DEPENDENCY_NAME not in recorded_kwargs
        assert recorded_kwargs["amount"] == 10.0
        assert recorded_kwargs["recipient"] == "landlord"
        assert recorded_kwargs["account"] is env.bank_account

    def test_original_dependency_resolution_still_works_through_the_clone(self):
        """account is resolved via Depends('bank_account') exactly as it
        would be for the unwrapped tool -- the factory doesn't interfere
        with the original's own dependency wiring."""
        registry = RunContextRegistry()
        env = _BankEnv()
        registry.register(env, _context())

        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(registry)
        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))
        runtime = FunctionsRuntime([cloned])

        runtime.run_function(
            env,
            "_send_money_like",
            {"amount": 25.0, "recipient": "utility co"},
            raise_on_error=True,
        )

        assert env.bank_account.balance == 75.0

    def test_missing_registration_raises_abort_agent_error_and_original_never_runs(self):
        registry = RunContextRegistry()  # nothing registered
        env = _BankEnv()

        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(registry)
        cloned = factory.wrap(original, hook=lambda ctx, run, kwargs: run(**kwargs))
        runtime = FunctionsRuntime([cloned])

        with pytest.raises(AbortAgentError):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert env.bank_account.balance == 100.0, (
            "the original tool must never run when context lookup fails"
        )

    def test_hook_can_deny_without_ever_calling_original_run(self):
        """This is what a privileged-tool wrapper (Step 7) will do on
        denial: the factory itself has no opinion, but the hook contract
        must actually support never invoking original_run."""
        registry = RunContextRegistry()
        env = _BankEnv()
        registry.register(env, _context())

        def denying_hook(context, original_run, kwargs):
            return "DENIED: governance policy blocked this action"

        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(registry)
        cloned = factory.wrap(original, hook=denying_hook)
        runtime = FunctionsRuntime([cloned])

        result, error = runtime.run_function(
            env, "_send_money_like", {"amount": 10.0, "recipient": "landlord"}
        )

        assert error is None
        assert result == "DENIED: governance policy blocked this action"
        assert env.bank_account.balance == 100.0, "original tool must not run when the hook denies"

    def test_hook_raising_governance_infrastructure_error_becomes_abort_agent_error(self):
        """A hook (source-tool or privileged-tool wrapper) signals an
        infrastructure failure via GovernanceInfrastructureError without
        ever needing to import agentdojo or hold a reference to env --
        the factory converts it here, using the env it already resolved."""
        registry = RunContextRegistry()
        env = _BankEnv()
        registry.register(env, _context())

        def failing_hook(context, original_run, kwargs):
            raise GovernanceInfrastructureError("database unavailable")

        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(registry)
        cloned = factory.wrap(original, hook=failing_hook)
        runtime = FunctionsRuntime([cloned])

        with pytest.raises(AbortAgentError):
            runtime.run_function(
                env,
                "_send_money_like",
                {"amount": 10.0, "recipient": "landlord"},
                raise_on_error=True,
            )

        assert env.bank_account.balance == 100.0, "original tool must not run when the hook raises"

    def test_two_environments_are_isolated(self):
        registry = RunContextRegistry()
        env_a, env_b = _BankEnv(), _BankEnv()
        context_a, context_b = _context(), _context()
        registry.register(env_a, context_a)
        registry.register(env_b, context_b)

        recorded: list = []
        original = make_function(_send_money_like)
        factory = GovernedFunctionFactory(registry)
        cloned = factory.wrap(original, hook=_recording_hook(recorded))
        runtime = FunctionsRuntime([cloned])

        runtime.run_function(
            env_a, "_send_money_like", {"amount": 5.0, "recipient": "x"}, raise_on_error=True
        )
        runtime.run_function(
            env_b, "_send_money_like", {"amount": 7.0, "recipient": "y"}, raise_on_error=True
        )

        assert recorded[0][0] is context_a
        assert recorded[1][0] is context_b
        assert env_a.bank_account.balance == 95.0
        assert env_b.bank_account.balance == 93.0


class TestCollisionGuard:
    def test_refuses_to_wrap_a_function_that_already_uses_the_hidden_dependency_name(self):
        from agentdojo.functions_runtime import Function

        conflicting = Function(
            name="already_uses_hidden_name",
            description="A contrived function for the collision test.",
            parameters=make_function(_no_dependency_tool).parameters,
            dependencies={HIDDEN_ENV_DEPENDENCY_NAME: Depends("bank_account")},
            run=lambda **kwargs: "unreachable",
            full_docstring="A contrived function for the collision test.",
            return_type=str,
        )
        factory = GovernedFunctionFactory(RunContextRegistry())

        with pytest.raises(HiddenDependencyCollisionError):
            factory.wrap(conflicting, hook=lambda ctx, run, kwargs: run(**kwargs))


class TestWrapAll:
    def test_wraps_every_function_using_the_provided_hook_selector(self):
        registry = RunContextRegistry()
        env = _BankEnv()
        registry.register(env, _context())

        money_original = make_function(_send_money_like)
        note_original = make_function(_no_dependency_tool)
        factory = GovernedFunctionFactory(registry)

        def hook_for(fn):
            if fn.name == "_send_money_like":
                return lambda ctx, run, kwargs: "gated:" + str(run(**kwargs))
            return lambda ctx, run, kwargs: run(**kwargs)

        wrapped = factory.wrap_all(
            {"_send_money_like": money_original, "_no_dependency_tool": note_original},
            hook_for,
        )
        runtime = FunctionsRuntime(list(wrapped.values()))

        money_result, _ = runtime.run_function(
            env, "_send_money_like", {"amount": 1.0, "recipient": "z"}
        )
        note_result, _ = runtime.run_function(env, "_no_dependency_tool", {"note": "hi"})

        assert money_result.startswith("gated:")
        assert note_result == "noted: hi"
