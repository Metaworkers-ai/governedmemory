"""Source/read-tool wrapper: writes a Banking read tool's output to
GovernedMemory as evidence, then returns the original result unchanged.

See the reviewed low-level design, section 9's "Source/read tool flow" and
section 10's "Tool output":

    E->>W: execute tool(args)
    W->>T: run(args)
    T-->>W: raw result
    W->>W: serialize with configured formatter
    W->>G: write(WriteRequest)
    G-->>W: MemoryRecord
    W->>C: append EvidenceRef
    W-->>E: original raw result

This module produces exactly one `GovernedRunHook` per Banking read tool,
meant to be passed to `GovernedFunctionFactory.wrap()` (Step 5). It has no
opinion on cloning, schema preservation, or context lookup -- that's the
factory's job.

Formatter alignment matters: AgentDojo's `ToolsExecutor` formats a tool's
raw result into the text the LLM actually reads (`tool_output_formatter`,
default `tool_result_to_str`) -- but it does so *after* `run_function`
returns, outside the wrapped `Function.run` entirely. If this wrapper
wrote the raw (unformatted) result, or used a different formatter, the
persisted evidence text could diverge from what the LLM sees, undermining
the injection scanner (which scores the text an attacker would actually
reach the LLM through). So this wrapper takes the *same* formatter
callable the runner configured for its `ToolsExecutor` and applies it
itself, independently, before writing -- see `docs/integrations/agentdojo.md`
for the runner-wiring rule that keeps the two in sync.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import FunctionReturnType

from core.memory_store import MemoryStore
from core.models import Provenance, Purpose, SourceType, WriteRequest
from integrations.agentdojo.banking_mapping import (
    PRIVILEGED_ACTIONS,
    SOURCE_TYPE_BY_TOOL,
    UnmappedBankingToolError,
)
from integrations.agentdojo.context import EvidenceRef, RunGovernanceContext
from integrations.agentdojo.function_factory import GovernanceInfrastructureError, GovernedRunHook

ToolOutputFormatter = Callable[[FunctionReturnType], str]


def make_source_tool_hook(
    store: MemoryStore,
    tool_name: str,
    source_type: SourceType,
    *,
    formatter: ToolOutputFormatter = tool_result_to_str,
) -> GovernedRunHook:
    """Build the `GovernedRunHook` for one Banking read/source tool.

    Args:
        store: the `MemoryStore` to write evidence through.
        tool_name: the tool's own name, e.g. `"get_most_recent_transactions"`
            -- used in the evidence `source_ref`, never re-derived from
            anything else, so it always matches what
            `SOURCE_TYPE_BY_TOOL` was keyed on.
        source_type: this tool's `SourceType`, from
            `integrations.agentdojo.banking_mapping.SOURCE_TYPE_BY_TOOL`.
        formatter: must be the exact callable the runner configured for
            AgentDojo's `ToolsExecutor(tool_output_formatter=...)` -- see
            the module docstring for why this has to match.

    The returned hook:
    - Calls `original_run(**kwargs)` first and lets any exception it
      raises propagate completely untouched -- a tool that fails on its
      own terms is not a governance event, and there is no raw result to
      write as evidence in that case.
    - Reserves a sequence number and writes the formatted result as
      evidence *before* returning to the caller, so any tool call made
      later in the same assistant-message batch (see the Step 1 contract
      test's batching proof) sees this evidence already recorded.
    - Raises `GovernanceInfrastructureError` (never touches `AbortAgentError`
      or `agentdojo` directly) if the write itself fails, and marks the
      failure on the context so the attempt is excluded from
      security/utility metrics later.
    - Never modifies the raw result: the LLM sees exactly what the
      original tool produced, governance is a side channel.
    """

    def hook(
        context: RunGovernanceContext, original_run: Callable[..., Any], kwargs: dict[str, Any]
    ) -> Any:
        raw_result = original_run(**kwargs)  # let the tool's own errors propagate untouched
        formatted_result = formatter(raw_result)

        sequence = context.next_sequence()
        source_ref = f"agentdojo:banking:{tool_name}:{sequence}"
        try:
            record = store.write(
                WriteRequest(
                    tenant_id=context.tenant_id,
                    customer_id=context.customer_id,
                    agent_id=context.agent_id,
                    session_id=context.session_id,
                    content=formatted_result,
                    provenance=Provenance(
                        source_type=source_type,
                        source_ref=source_ref,
                    ),
                    purpose=Purpose(policy_id=context.policy_id),
                )
            )
        except Exception as exc:
            context.mark_infrastructure_error(
                f"source-tool wrapper for {tool_name!r} failed to record evidence: {exc}"
            )
            raise GovernanceInfrastructureError(
                f"failed to record {tool_name!r} output as governed evidence: {exc}"
            ) from exc

        context.append_evidence(
            EvidenceRef(
                memory_id=record.id,
                sequence=sequence,
                source_kind="tool_output",
                tool_name=tool_name,
                source_ref=record.provenance.source_ref,
                taint=record.trust.taint.value,
                injection_score=record.trust.injection_score,
                policy_id=record.purpose.policy_id,
                audit_id=record.audit_id,
            )
        )

        return raw_result

    return hook


class PrivilegedToolMisuseError(Exception):
    """Raised when `make_banking_source_tool_hook` is asked to build a
    source/read-tool hook for a tool that's actually privileged
    (`send_money`, `schedule_transaction`, etc.).

    This guards against a specific, serious bug: wrapping a mutating tool
    with the source-tool hook instead of the privileged-tool hook (Step 7)
    would let it run with no `check_privilege()` gate at all -- worse than
    doing nothing, since it would look governed in the benchmark's tool
    list while actually being wide open.
    """


def make_banking_source_tool_hook(
    store: MemoryStore,
    tool_name: str,
    *,
    formatter: ToolOutputFormatter = tool_result_to_str,
) -> GovernedRunHook:
    """Convenience over `make_source_tool_hook`: looks up `tool_name`'s
    `SourceType` from `integrations.agentdojo.banking_mapping.SOURCE_TYPE_BY_TOOL`
    automatically, and refuses to build a hook for a tool in
    `PRIVILEGED_ACTIONS` (use Step 7's privileged-tool wrapper for those
    instead).

    Raises:
        PrivilegedToolMisuseError: if `tool_name` is a privileged action.
        UnmappedBankingToolError: if `tool_name` has no entry in
            `SOURCE_TYPE_BY_TOOL` at all.
    """
    if tool_name in PRIVILEGED_ACTIONS:
        raise PrivilegedToolMisuseError(
            f"{tool_name!r} is a privileged Banking action ({PRIVILEGED_ACTIONS}); "
            "use the privileged-tool wrapper (Step 7), not make_source_tool_hook, "
            "or that action would run completely ungated"
        )
    if tool_name not in SOURCE_TYPE_BY_TOOL:
        raise UnmappedBankingToolError(
            f"no source_type mapping for Banking tool {tool_name!r}. Add it to "
            "SOURCE_TYPE_BY_TOOL in integrations/agentdojo/banking_mapping.py "
            "before wrapping it."
        )
    return make_source_tool_hook(
        store, tool_name, SOURCE_TYPE_BY_TOOL[tool_name], formatter=formatter
    )
