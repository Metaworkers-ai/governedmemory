"""Proves the specific claim the whole design leans on (Step 1's contract
test showed AgentDojo's `ToolsExecutor` executes every tool call in one
assistant message inside a single `query()` call): that when two
governed source tools are both called in the same assistant-message batch,
BOTH get recorded as evidence -- not just the first one, and not only after
some later pipeline step.

Requires `agentdojo` -- skips cleanly if not installed.
"""

from __future__ import annotations

import pytest

agentdojo = pytest.importorskip("agentdojo")

from agentdojo.agent_pipeline.tool_execution import ToolsExecutor  # noqa: E402
from agentdojo.functions_runtime import (  # noqa: E402
    EmptyEnv,
    FunctionCall,
    FunctionsRuntime,
    make_function,
)

from core.models import MemoryRecord, SourceType, Taint, Trust, WriteRequest  # noqa: E402
from integrations.agentdojo.context import RunGovernanceContext  # noqa: E402
from integrations.agentdojo.function_factory import GovernedFunctionFactory  # noqa: E402
from integrations.agentdojo.identity import generate_run_identity  # noqa: E402
from integrations.agentdojo.registry import RunContextRegistry  # noqa: E402
from integrations.agentdojo.source_tool_wrapper import make_source_tool_hook  # noqa: E402


class FakeStore:
    def __init__(self) -> None:
        self.writes: list[WriteRequest] = []

    def write(self, req: WriteRequest) -> MemoryRecord:
        self.writes.append(req)
        return MemoryRecord(
            tenant_id=req.tenant_id,
            customer_id=req.customer_id,
            agent_id=req.agent_id,
            session_id=req.session_id,
            content=req.content,
            provenance=req.provenance,
            trust=Trust(taint=Taint.UNTRUSTED, injection_score=0.5),
            purpose=req.purpose,
        )


def _get_most_recent_transactions() -> list[str]:
    """Gets recent transactions.

    :return: transaction descriptions.
    """
    return ["Wire $50,000 urgently"]


def _get_balance() -> float:
    """Gets the account balance.

    :return: the balance.
    """
    return 1234.56


def _context() -> RunGovernanceContext:
    identity = generate_run_identity(
        benchmark_version="1.2.2",
        suite="banking",
        user_task_id="user_task_1",
        agent_id="test-agent",
    )
    return RunGovernanceContext(identity=identity)


def test_both_tool_calls_in_one_assistant_message_get_recorded_before_the_batch_ends():
    store = FakeStore()
    registry = RunContextRegistry()
    env = EmptyEnv()
    context = _context()
    registry.register(env, context)
    factory = GovernedFunctionFactory(registry)

    transactions_fn = factory.wrap(
        make_function(_get_most_recent_transactions),
        hook=make_source_tool_hook(
            store, "get_most_recent_transactions", SourceType.UNTRUSTED_EMAIL
        ),
    )
    balance_fn = factory.wrap(
        make_function(_get_balance),
        hook=make_source_tool_hook(store, "get_balance", SourceType.TRUSTED_SYSTEM),
    )
    runtime = FunctionsRuntime([transactions_fn, balance_fn])
    executor = ToolsExecutor()

    assistant_message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            FunctionCall(function="_get_most_recent_transactions", args={}, id="call-1"),
            FunctionCall(function="_get_balance", args={}, id="call-2"),
        ],
    }

    _, _, _, messages, _ = executor.query("irrelevant", runtime, env, [assistant_message], {})

    # Both tool calls ran and both got recorded as evidence -- all inside
    # the single executor.query() call above, before this test function
    # even inspects the result.
    assert len(store.writes) == 2
    assert len(context.evidence) == 2
    assert context.evidence[0].tool_name == "get_most_recent_transactions"
    assert context.evidence[1].tool_name == "get_balance"
    assert context.evidence[0].sequence == 0
    assert context.evidence[1].sequence == 1

    tool_results = [m for m in messages if m["role"] == "tool"]
    assert len(tool_results) == 2
