"""GovernedRunInitializer: writes the AgentDojo task prompt once as trusted
evidence, before the LLM ever sees it.

See the reviewed low-level design, section 10 ("Evidence ingestion" ->
"Initial user input") and section 6 ("Pipeline construction"), which places
this element here:

    SystemMessage -> InitQuery -> GovernedRunInitializer -> LLM -> ToolsExecutionLoop(...)

Persisting the initial prompt as trusted evidence means a benign task
already has at least one trusted evidence record on the books before any
direct privileged action. Without this, a task whose very first agent
action is a privileged call -- no prior tool output at all -- would have an
empty evidence snapshot for the all-evidence gate (Step 7) to evaluate,
which would either wrongly deny a legitimate action or (worse) wrongly
allow one, depending on how an empty snapshot is treated. This element
exists so that case never comes up: real GovernedMemory evidence always
exists before the pipeline reaches the LLM.
"""

from __future__ import annotations

import time
from typing import Any

from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.agent_pipeline.errors import AbortAgentError
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime

from core.memory_store import MemoryStore
from core.models import Provenance, Purpose, SourceType, WriteRequest
from integrations.agentdojo.context import EvidenceRef
from integrations.agentdojo.registry import RegistryMissError, RunContextRegistry, default_registry


class GovernedRunInitializer(BasePipelineElement):
    """Writes `query` (the AgentDojo task prompt) to GovernedMemory as
    trusted evidence exactly once per attempt, then passes the pipeline
    state through unchanged -- this element never rewrites `query`,
    `runtime`, `env`, `messages`, or `extra_args`.

    Idempotent within an attempt via
    `RunGovernanceContext.processed_initial_input`: if this element is ever
    invoked twice for the same environment, the second call is a no-op
    rather than a duplicate write. (Normal AgentDojo pipelines only place
    one initializer-like element before the LLM, so this should not happen
    in practice -- it's a safety net, not something relied on.)

    Fails closed: a missing context registration or a failed write both
    raise `AbortAgentError` rather than letting the pipeline continue with
    the attempt's very first piece of evidence silently missing.
    """

    name = "governed_run_initializer"

    def __init__(self, store: MemoryStore, registry: RunContextRegistry = default_registry) -> None:
        self.store = store
        self.registry = registry

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages=(),
        extra_args: dict[str, Any] | None = None,
    ):
        extra_args = extra_args if extra_args is not None else {}

        try:
            context = self.registry.get(env)
        except RegistryMissError as exc:
            raise AbortAgentError(
                f"GovernedRunInitializer: {exc}",
                list(messages),
                env,
            ) from exc

        if context.processed_initial_input:
            return query, runtime, env, messages, extra_args

        try:
            write_started = time.perf_counter()
            record = self.store.write(
                WriteRequest(
                    tenant_id=context.tenant_id,
                    customer_id=context.customer_id,
                    agent_id=context.agent_id,
                    session_id=context.session_id,
                    content=query,
                    provenance=Provenance(
                        source_type=SourceType.USER,
                        source_ref=f"agentdojo:user:{context.customer_id}",
                    ),
                    purpose=Purpose(policy_id=context.policy_id),
                )
            )
            write_latency_ms = (time.perf_counter() - write_started) * 1000
        except Exception as exc:
            # An infrastructure failure, not a governance decision -- the
            # attempt cannot be trusted to have any evidence at all from
            # this point on, so stop it rather than let the LLM proceed as
            # if nothing happened. See the LLD's failure-semantics table:
            # attempts with any infrastructure error are excluded from
            # security/utility metrics, never counted as a clean pass.
            context.mark_infrastructure_error(f"GovernedRunInitializer write failed: {exc}")
            raise AbortAgentError(
                f"GovernedRunInitializer: failed to write initial user input: {exc}",
                list(messages),
                env,
            ) from exc

        sequence = context.next_sequence()
        context.append_evidence(
            EvidenceRef(
                memory_id=record.id,
                sequence=sequence,
                source_kind="user_input",
                tool_name=None,
                source_ref=record.provenance.source_ref,
                taint=record.trust.taint.value,
                injection_score=record.trust.injection_score,
                policy_id=record.purpose.policy_id,
                audit_id=record.audit_id,
                write_latency_ms=write_latency_ms,
            )
        )
        context.processed_initial_input = True

        return query, runtime, env, messages, extra_args
