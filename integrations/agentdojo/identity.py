"""Run identity generation for one GovernedMemory-governed AgentDojo task attempt.

See docs/integrations/agentdojo.md and the reviewed low-level design's
section 7 ("Run identity and isolation") for the rules this encodes:

- Every evaluated task attempt gets its own tenant. AgentDojo has no native
  concept of tenant_id, and without one, evidence from independent task
  attempts in the same benchmark sweep could bleed into each other.
- `run_uuid` is generated once, before pipeline construction, and reused for
  every write and every check_privilege() call across the whole attempt.
- A tenant is never reused across independent attempts, including retries
  of the same (user_task_id, injection_task_id) pair.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RunIdentity:
    """GovernedMemory tenancy fields for exactly one AgentDojo task attempt.

    Every MemoryStore.write() and check_privilege() call made during this
    attempt must use these exact values. RunGovernanceContext (context.py)
    carries one of these alongside the attempt's evidence and action
    history so wrapped tools never have to re-derive it mid-run.
    """

    tenant_id: str
    customer_id: str
    agent_id: str
    session_id: str
    policy_id: str = "default"


def generate_run_identity(
    *,
    benchmark_version: str,
    suite: str,
    user_task_id: str,
    agent_id: str,
    injection_task_id: str | None = None,
    attempt: int = 0,
) -> RunIdentity:
    """Build a fresh, isolated RunIdentity for one task attempt.

    Call this exactly once per attempt, before constructing the agent
    pipeline -- not lazily inside a tool call -- so a single run_uuid stays
    fixed for the attempt's entire lifetime, per the LLD's rule "Generate
    run_uuid before pipeline construction."

    Args:
        benchmark_version: e.g. "1.2.2". Recorded in tenant_id so results
            from different pinned AgentDojo releases can never collide.
        suite: AgentDojo suite name, e.g. "banking".
        user_task_id: AgentDojo's own task identifier; becomes customer_id.
        agent_id: stable model/pipeline identifier (e.g. "gpt-4o-2024-08-06"
            or a pipeline config name) -- NOT derived from anything in the
            task environment, since it should stay comparable across tasks.
        injection_task_id: AgentDojo's injection task identifier, if this
            attempt is a security (not utility-only) run. None for a benign
            run with no injection task.
        attempt: retry counter, starting at 0, for when the same
            (user_task_id, injection_task_id) pair is run more than once.

    Raises:
        ValueError: if any required identifier is blank -- fail before
            registering a context, not partway through a run.
    """
    if not suite.strip():
        raise ValueError("suite must not be empty")
    if not user_task_id.strip():
        raise ValueError("user_task_id must not be empty")
    if not agent_id.strip():
        raise ValueError("agent_id must not be empty")
    if attempt < 0:
        raise ValueError("attempt must be >= 0")

    run_uuid = uuid.uuid4().hex
    tenant_id = f"agentdojo:{benchmark_version}:{suite}:{run_uuid}"
    session_id = f"{user_task_id}:{injection_task_id or 'none'}:{attempt}"

    return RunIdentity(
        tenant_id=tenant_id,
        customer_id=user_task_id,
        agent_id=agent_id,
        session_id=session_id,
        policy_id="default",
    )
