"""Privileged-tool wrapper: gates a Banking privileged action behind
`MemoryStore.check_privilege()`, evaluated against the configured evidence
set before the original tool is ever allowed to run.

See the reviewed low-level design, section 9's "Privileged tool flow" and
section 13's all-evidence gating rule:

    E->>W: execute privileged tool(args)
    W->>C: snapshot ordered evidence IDs
    loop Every evidence ID
        W->>G: check_privilege(memory_id, action=tool_name)
        G-->>W: allow or deny
    end
    alt Any denial
        W->>C: record denied ActionEvent
        W-->>E: governance-denied tool error
    else All allow
        W->>T: run(args)
        T-->>W: raw result
        W->>G: persist successful tool output
        W->>C: append EvidenceRef and allowed ActionEvent
        W-->>E: original raw result
    end

"The original privileged function is never invoked on denial" -- this
module raises before ever calling `original_run` in that case.

The AgentDojo Banking default includes every tool-output evidence id, not
only the most recent or most relevant one. The benchmark-authored initial
task remains persisted and audited but serves as the authorization anchor.
Strict comparison mode includes that initial message in the gate as well.
"""

from __future__ import annotations

import time
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
from integrations.agentdojo.context import ActionEvent, EvidenceRef, RunGovernanceContext
from integrations.agentdojo.function_factory import GovernanceInfrastructureError, GovernedRunHook

ToolOutputFormatter = Callable[[FunctionReturnType], str]


class PrivilegedActionDenied(Exception):
    """Raised when `check_privilege()` denies this call (or when no
    evidence exists yet to evaluate at all).

    This propagates as an ordinary AgentDojo tool error -- caught by
    `FunctionsRuntime.run_function`'s own `except Exception` and turned
    into `(result, error_string)` for `ToolsExecutor` to surface to the
    LLM as this tool call's error -- NOT as `agentdojo`'s `AbortAgentError`.
    A denial is a *successful* governance decision, not an infrastructure
    failure: the attempt should continue (the agent may recover, try
    something else, or simply fail the injected task while completing the
    benign one), not abort outright. Contrast with
    `GovernanceInfrastructureError`, which the factory converts into
    `AbortAgentError` because a database failure genuinely can't be
    reasoned about as a governance decision at all.

    The benchmark runner (a later step) reads `context.actions` to
    determine whether an attack was blocked; it does not need to inspect
    this exception type to know that.
    """


class NonPrivilegedToolMisuseError(Exception):
    """Raised by `make_banking_privileged_tool_hook` when asked to build a
    privileged-tool hook for a tool that isn't one of the five Banking
    privileged actions.

    Mirror image of `source_tool_wrapper.PrivilegedToolMisuseError`: that
    one stops a mutating tool from being wrapped as if it were a read
    tool (leaving it ungated); this one stops a read tool from being
    wrapped as if it were privileged (harmless in practice, since
    `check_privilege()` would simply find the action isn't in the policy's
    `privileged_actions` and allow it -- but almost certainly a caller
    bug, so it's rejected rather than silently tolerated).
    """


def make_privileged_tool_hook(
    store: MemoryStore,
    tool_name: str,
    source_type: SourceType,
    *,
    formatter: ToolOutputFormatter = tool_result_to_str,
    include_user_input_in_gate: bool = True,
) -> GovernedRunHook:
    """Build the `GovernedRunHook` for one Banking privileged action.

    Args:
        store: the `MemoryStore` to call `check_privilege()` and `write()`
            through.
        tool_name: the tool's own name, e.g. `"send_money"` -- must be one
            of `integrations.agentdojo.banking_mapping.PRIVILEGED_ACTIONS`
            for the resulting gate to mean anything (see
            `make_banking_privileged_tool_hook` for a guarded convenience).
        source_type: the `SourceType` to record the tool's own confirmation
            output under, once it's allowed to run -- from
            `SOURCE_TYPE_BY_TOOL` (all five privileged actions map to
            `TRUSTED_SYSTEM`, since a confirmation is the result of an
            already-authorized internal operation).
        formatter: must match the callable configured for AgentDojo's
            `ToolsExecutor(tool_output_formatter=...)`, same reasoning as
            the source-tool wrapper.
        include_user_input_in_gate: when False, the initial benchmark task
            remains scanned, persisted, and audited but is not passed to
            `check_privilege()`. Every tool output remains gated.

    The returned hook:
    - Snapshots the configured evidence set written so far in the attempt
      (`context.ordered_evidence_ids(...)`), *before* deciding anything.
      AgentDojo Banking defaults to tool outputs only; strict comparison
      runs can include the benchmark-authored initial user message.
    - Denies outright, with no `check_privilege()` calls at all, if that
      snapshot is empty -- normally impossible once
      `GovernedRunInitializer` has run, but a defensive fail-closed default
      rather than an ambiguous "nothing to check, so allow."
    - Calls `check_privilege()` once per evidence id -- every one, not just
      until the first denial -- so `ActionEvent.denied_memory_ids` records
      the complete set that failed, not just the first.
    - Denies (raises `PrivilegedActionDenied`, records a denied
      `ActionEvent`, never calls `original_run`) if *any* evidence id was
      denied.
    - Otherwise runs the original tool, writes its formatted output as new
      evidence, and records an allowed `ActionEvent` -- in that order, so
      the new evidence's sequence number is lower than the action's,
      matching the interleaving the Step 6 bug fix supports.
    - Raises `GovernanceInfrastructureError` (never `agentdojo` types
      directly) if `check_privilege()` or the confirmation `write()` fails
      for reasons unrelated to a governance decision.
    """

    def hook(
        context: RunGovernanceContext, original_run: Callable[..., Any], kwargs: dict[str, Any]
    ) -> Any:
        if context.has_infrastructure_error:
            raise GovernanceInfrastructureError(
                f"refusing {tool_name!r}: this attempt already has a governance "
                "infrastructure error"
            )
        evidence_ids = context.ordered_evidence_ids(include_user_input=include_user_input_in_gate)

        if not evidence_ids:
            # AgentDojo's benchmark-authored opening task is first-party
            # intent, not the attacker-reachable channel. In tool-output-only
            # mode it is still scanned, persisted, and audited, but it acts as
            # the run's trusted authorization anchor rather than being sent
            # through check_privilege(). This permits direct legitimate
            # actions while keeping every tool output fail-closed.
            if not include_user_input_in_gate and context.processed_initial_input:
                raw_result = original_run(**kwargs)
                return _record_allowed_result(
                    context,
                    original_run_result=raw_result,
                    evidence_ids=(),
                    gate_latency_ms=0.0,
                )
            sequence = context.next_sequence()
            context.append_action(
                ActionEvent(
                    sequence=sequence,
                    tool_name=tool_name,
                    evidence_ids=(),
                    allowed=False,
                    denied_memory_ids=(),
                    reason="no evidence recorded for this attempt yet; denying by default",
                )
            )
            raise PrivilegedActionDenied(
                f"'{tool_name}' was blocked: no governed evidence exists yet for this attempt"
            )

        denied_memory_ids: list[str] = []
        gate_started = time.perf_counter()
        for memory_id in evidence_ids:
            try:
                allowed = store.check_privilege(
                    memory_id,
                    context.tenant_id,
                    action=tool_name,
                    agent_id=context.agent_id,
                    session_id=context.session_id,
                )
            except Exception as exc:
                context.mark_infrastructure_error(
                    f"privileged-tool wrapper for {tool_name!r} failed check_privilege "
                    f"against {memory_id!r}: {exc}"
                )
                raise GovernanceInfrastructureError(
                    f"check_privilege failed for {tool_name!r} against {memory_id!r}: {exc}"
                ) from exc
            if not allowed:
                denied_memory_ids.append(memory_id)
        gate_latency_ms = (time.perf_counter() - gate_started) * 1000

        if denied_memory_ids:
            sequence = context.next_sequence()
            context.append_action(
                ActionEvent(
                    sequence=sequence,
                    tool_name=tool_name,
                    evidence_ids=evidence_ids,
                    allowed=False,
                    denied_memory_ids=tuple(denied_memory_ids),
                    reason=(
                        f"check_privilege denied against {len(denied_memory_ids)} of "
                        f"{len(evidence_ids)} evidence record(s)"
                    ),
                    gate_latency_ms=gate_latency_ms,
                )
            )
            raise PrivilegedActionDenied(
                f"'{tool_name}' was blocked by governed-memory policy: denied against "
                f"{len(denied_memory_ids)} of {len(evidence_ids)} evidence record(s)"
            )

        # Every evidence id allowed this action -- run the original tool.
        raw_result = original_run(**kwargs)
        return _record_allowed_result(
            context,
            original_run_result=raw_result,
            evidence_ids=evidence_ids,
            gate_latency_ms=gate_latency_ms,
        )

    def _record_allowed_result(
        context: RunGovernanceContext,
        *,
        original_run_result: Any,
        evidence_ids: tuple[str, ...],
        gate_latency_ms: float,
    ) -> Any:
        formatted_result = formatter(original_run_result)
        write_sequence = context.next_sequence()
        source_ref = f"agentdojo:banking:{tool_name}:{write_sequence}"
        try:
            write_started = time.perf_counter()
            record = store.write(
                WriteRequest(
                    tenant_id=context.tenant_id,
                    customer_id=context.customer_id,
                    agent_id=context.agent_id,
                    session_id=context.session_id,
                    content=formatted_result,
                    provenance=Provenance(source_type=source_type, source_ref=source_ref),
                    purpose=Purpose(policy_id=context.policy_id),
                )
            )
            write_latency_ms = (time.perf_counter() - write_started) * 1000
        except Exception as exc:
            context.mark_infrastructure_error(
                f"privileged-tool wrapper for {tool_name!r} failed to record confirmation "
                f"evidence: {exc}"
            )
            raise GovernanceInfrastructureError(
                f"failed to record {tool_name!r} confirmation output as evidence: {exc}"
            ) from exc

        context.append_evidence(
            EvidenceRef(
                memory_id=record.id,
                sequence=write_sequence,
                source_kind="tool_output",
                tool_name=tool_name,
                source_ref=record.provenance.source_ref,
                taint=record.trust.taint.value,
                injection_score=record.trust.injection_score,
                policy_id=record.purpose.policy_id,
                audit_id=record.audit_id,
                write_latency_ms=write_latency_ms,
            )
        )

        action_sequence = context.next_sequence()
        context.append_action(
            ActionEvent(
                sequence=action_sequence,
                tool_name=tool_name,
                evidence_ids=evidence_ids,
                allowed=True,
                denied_memory_ids=(),
                reason=f"all {len(evidence_ids)} evidence record(s) allowed",
                gate_latency_ms=gate_latency_ms,
            )
        )

        return original_run_result

    return hook


def make_banking_privileged_tool_hook(
    store: MemoryStore,
    tool_name: str,
    *,
    formatter: ToolOutputFormatter = tool_result_to_str,
    include_user_input_in_gate: bool = False,
) -> GovernedRunHook:
    """Convenience over `make_privileged_tool_hook`: looks up `tool_name`'s
    `SourceType` automatically, and refuses to build a hook for a tool
    that isn't one of the five Banking privileged actions.

    Raises:
        NonPrivilegedToolMisuseError: if `tool_name` is not in
            `PRIVILEGED_ACTIONS`.
        UnmappedBankingToolError: if `tool_name` has no entry in
            `SOURCE_TYPE_BY_TOOL` at all.
    """
    if tool_name not in PRIVILEGED_ACTIONS:
        raise NonPrivilegedToolMisuseError(
            f"{tool_name!r} is not one of the Banking privileged actions "
            f"{PRIVILEGED_ACTIONS}; use the source-tool wrapper for read "
            "tools instead"
        )
    if tool_name not in SOURCE_TYPE_BY_TOOL:
        raise UnmappedBankingToolError(
            f"no source_type mapping for Banking tool {tool_name!r}. Add it to "
            "SOURCE_TYPE_BY_TOOL in integrations/agentdojo/banking_mapping.py "
            "before wrapping it."
        )
    return make_privileged_tool_hook(
        store,
        tool_name,
        SOURCE_TYPE_BY_TOOL[tool_name],
        formatter=formatter,
        include_user_input_in_gate=include_user_input_in_gate,
    )
