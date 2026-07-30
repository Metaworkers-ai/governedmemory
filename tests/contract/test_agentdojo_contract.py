"""Contract tests against the pinned AgentDojo release.

These tests do NOT touch GovernedMemory code. Their only job is to fail
loudly, before any adapter is written, if the installed `agentdojo` package
no longer matches the API shapes the low-level design in
docs/integrations/agentdojo.md depends on:

  - `Function` / `Depends` / `FunctionsRuntime` / `make_function` shapes
    (core/integrations/agentdojo's function-wrapping factory depends on
    these exact fields existing).
  - `ToolsExecutor` executing every tool call in one assistant message
    inside a single `query()` call, with no pipeline element able to run
    between two tool calls in the same batch. This is the fact that ruled
    out a post-`ToolsExecutor` defense element as sufficient for gating
    privileged actions (see the LLD's section 2.2 / "Key design decision").
  - The Banking suite's exact tool set, so the source-type mapping table
    (LLD section 11) and the privileged-action list (LLD section 12) can be
    validated at startup instead of assumed.
  - `AbortAgentError`'s constructor shape.

Run with:
    pip install -r requirements-agentdojo.txt
    pytest tests/contract/ -v

If `agentdojo` is not installed, every test in this module is skipped
(mirrors how tests/integration/ skips when Docker is unavailable) rather
than failing the rest of the suite.
"""

from __future__ import annotations

import importlib.metadata
from typing import Annotated

import pytest

agentdojo = pytest.importorskip("agentdojo")
from agentdojo.functions_runtime import Depends  # noqa: E402 - after importorskip guard

PINNED_VERSION = "0.1.35"

# The exact Banking suite tool set as of the pinned release. Sourced by
# reading agentdojo/default_suites/v1/banking/task_suite.py directly, not
# from AgentDojo's docs (docs/traction-roadmap.md, Workstream A Ticket 1,
# explicitly calls for confirming this against source).
EXPECTED_BANKING_TOOL_NAMES = frozenset(
    {
        "get_iban",
        "send_money",
        "schedule_transaction",
        "update_scheduled_transaction",
        "get_balance",
        "get_most_recent_transactions",
        "get_scheduled_transactions",
        "read_file",
        "get_user_info",
        "update_password",
        "update_user_info",
    }
)

# The subset of the above that mutate money, credentials, scheduled
# payments, or customer state — must match LLD section 12's privileged
# policy exactly.
EXPECTED_PRIVILEGED_TOOL_NAMES = frozenset(
    {
        "send_money",
        "schedule_transaction",
        "update_scheduled_transaction",
        "update_password",
        "update_user_info",
    }
)


def test_pinned_version_matches_installed_package():
    """Fail fast if someone floats the pin without re-validating the contract."""
    installed = importlib.metadata.version("agentdojo")
    assert installed == PINNED_VERSION, (
        f"tests/contract assumes agentdojo=={PINNED_VERSION}, but {installed} is "
        "installed. Re-run this whole contract suite against the new version "
        "before updating requirements-agentdojo.txt or the LLD's version contract."
    )


class _FakeAccount:
    """Module-level fixture: get_type_hints() resolves annotations against
    a function's __globals__ (its defining module), not the locals of
    whatever test method constructs it — so this must live at module scope,
    not inside the test."""


def _read_balance(account: Annotated[_FakeAccount, Depends("bank_account")]) -> float:
    """Reads the account balance.

    :param account: the account.
    """
    return 42.0


class TestFunctionsRuntimeShapes:
    """core/integrations/agentdojo's function-wrapping factory (LLD section 9)
    depends on these exact fields/signatures existing."""

    def test_function_has_expected_fields(self):
        from agentdojo.functions_runtime import Function

        expected_fields = {
            "name",
            "description",
            "parameters",
            "dependencies",
            "run",
            "full_docstring",
            "return_type",
        }
        assert expected_fields.issubset(set(Function.model_fields))

    def test_depends_extracts_from_env_by_attribute_or_callable(self):
        from agentdojo.functions_runtime import Depends

        class FakeEnv:
            bank_account = "the-account"

        by_attr = Depends("bank_account")
        assert by_attr.extract_dep_from_env(FakeEnv()) == "the-account"

        by_callable = Depends(lambda env: env.bank_account)
        assert by_callable.extract_dep_from_env(FakeEnv()) == "the-account"

    def test_make_function_wraps_a_plain_callable(self):
        from agentdojo.functions_runtime import make_function

        fn = make_function(_read_balance)
        assert fn.name == "_read_balance"
        assert "account" in fn.dependencies
        assert fn.dependencies["account"].env_dependency == "bank_account"

    def test_runtime_run_function_signature(self):
        """The hidden-context-dependency trick (LLD section 8, "Context lookup")
        relies on `run_function` resolving dependencies from `env` without
        exposing them as LLM-visible arguments."""
        import inspect

        from agentdojo.functions_runtime import FunctionsRuntime

        sig = inspect.signature(FunctionsRuntime.run_function)
        params = list(sig.parameters)
        assert params == ["self", "env", "function", "kwargs", "raise_on_error"]


class TestToolsExecutorBatching:
    """This is the load-bearing behavioral fact for the whole LLD: a defense
    element placed after `ToolsExecutor` in the pipeline (the
    `transformers_pi_detector` slot) cannot intervene between two tool calls
    that arrive in the same assistant message. Confirming this in code is
    what ruled out "Job 1 as a post-executor detector" as sufficient and
    justified wrapping individual tool functions instead."""

    def test_multiple_tool_calls_in_one_message_all_execute_before_query_returns(self):
        from agentdojo.agent_pipeline.tool_execution import ToolsExecutor
        from agentdojo.functions_runtime import (
            EmptyEnv,
            FunctionCall,
            FunctionsRuntime,
            make_function,
        )

        call_order: list[str] = []

        def first_tool() -> str:
            """A harmless read.

            :return: nothing interesting.
            """
            call_order.append("first_tool")
            return "ok"

        def second_tool() -> str:
            """A privileged action, standing in for e.g. send_money.

            :return: nothing interesting.
            """
            call_order.append("second_tool")
            return "ok"

        runtime = FunctionsRuntime([make_function(first_tool), make_function(second_tool)])
        executor = ToolsExecutor()

        assistant_message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                FunctionCall(function="first_tool", args={}, id="call-1"),
                FunctionCall(function="second_tool", args={}, id="call-2"),
            ],
        }

        # A single query() call is exactly what one pipeline "step" looks
        # like to any element placed after ToolsExecutor. If both tools ran
        # by the time query() returns, no post-executor element — however it
        # is implemented — got a chance to run in between them.
        _, _, _, messages, _ = executor.query(
            "irrelevant", runtime, EmptyEnv(), [assistant_message], {}
        )

        assert call_order == ["first_tool", "second_tool"], (
            "expected both tool calls in the same assistant message to execute "
            "inside a single ToolsExecutor.query() call, confirming a "
            "post-executor defense cannot gate the second call using "
            "information produced by the first"
        )
        # Two tool-result messages appended, one per call, both already
        # executed — nothing left for a downstream element to prevent.
        tool_results = [m for m in messages if m["role"] == "tool"]
        assert len(tool_results) == 2


class TestBankingSuiteShapes:
    """Validates the exact tool set the source-type mapping table (LLD
    section 11) and privileged-action policy (LLD section 12) are built
    against, per docs/traction-roadmap.md's instruction to confirm against
    source rather than assume."""

    def test_banking_tool_names_match_expected_set(self):
        # NOTE: importing agentdojo.default_suites.v1.banking.task_suite
        # directly (e.g. `from ...task_suite import TOOLS`) triggers a real
        # circular-import bug in agentdojo==0.1.35's default_suites package
        # init order (v1_1_1/banking/user_tasks.py imports back from
        # v1/banking/task_suite before the latter finishes initializing).
        # agentdojo.task_suite.load_suites.get_suite() is the package's own
        # public entrypoint and does not hit this path — use it instead of
        # reaching into the submodule.
        from agentdojo.task_suite.load_suites import get_suite

        suite = get_suite("v1.2.2", "banking")
        actual_names = {tool.name for tool in suite.tools}
        assert actual_names == EXPECTED_BANKING_TOOL_NAMES, (
            "Banking suite's tool set has changed since the LLD's source "
            "mapping table and privileged-action policy were written. Update "
            "both before writing adapter code, then update this test's "
            "expected sets to match."
        )

    def test_privileged_tool_subset_matches_lld_policy(self):
        assert EXPECTED_PRIVILEGED_TOOL_NAMES.issubset(EXPECTED_BANKING_TOOL_NAMES)


class TestAbortAgentErrorShape:
    """Job 2's denial path (LLD section 14) explicitly does NOT rely on this
    exception escaping the wrapped tool — but the shape still needs to exist
    and behave as documented for the read-path detector slot and for any
    infrastructure-error fail-closed paths (LLD section 15) that do want a
    hard abort."""

    def test_construction_and_message_list_shape(self):
        from agentdojo.agent_pipeline.errors import AbortAgentError
        from agentdojo.functions_runtime import EmptyEnv

        prior_messages = [{"role": "user", "content": [{"type": "text", "content": "hi"}]}]
        err = AbortAgentError("denied", prior_messages, EmptyEnv())

        assert err.messages[:-1] == prior_messages
        assert err.messages[-1]["role"] == "assistant"
        assert isinstance(err.task_environment, EmptyEnv)


class TestBasePipelineElementContract:
    """Any governed defense element (if one is added later, e.g. for the
    read-path detector) must satisfy this ABC."""

    def test_is_abstract_with_query_method(self):
        import abc

        from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement

        assert issubclass(BasePipelineElement, abc.ABC)
        assert "query" in BasePipelineElement.__abstractmethods__
