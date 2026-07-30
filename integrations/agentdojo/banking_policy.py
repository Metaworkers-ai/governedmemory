"""Upserts the Banking privileged-action policy for one run tenant.

See the reviewed low-level design, section 12 ("Privileged Banking
actions"):

GovernedMemory's shipped `PrivilegeRules` defaults are
`["send_email", "refund", "escalate"]` -- none of those match a Banking
tool name. If a governed run relied on `MemoryStore.get_policy()`'s
synthesized default for an unconfigured tenant (see `store.py`'s
docstring: "an unconfigured tenant behaves exactly as it did before E4"),
`check_privilege()` would evaluate `action="send_money"` against a policy
whose `privileged_actions` doesn't contain `"send_money"` at all --
`evaluate_privileged_action()` returns `(True, "... is not a privileged
action under policy ...")` in that case, meaning the action is allowed
regardless of taint. Every Banking action would be silently ungated.

`ensure_banking_policy()` must therefore run once per attempt, before the
pipeline executes any tool call, so `check_privilege()` has something real
to gate against from the very first privileged call.
"""

from __future__ import annotations

from core.memory_store import MemoryStore
from core.models import Policy, PrivilegeRules
from integrations.agentdojo.banking_mapping import PRIVILEGED_ACTIONS


def ensure_banking_policy(
    store: MemoryStore, tenant_id: str, *, policy_id: str = "default"
) -> Policy:
    """Create (or overwrite) `tenant_id`'s policy so `check_privilege()`
    enforces exactly the Banking privileged-action set with
    `require_trust=True`.

    Call this once per attempt, immediately after
    `integrations.agentdojo.identity.generate_run_identity()` and before
    the agent pipeline runs. `policy_id` must match the `policy_id` every
    `WriteRequest.purpose` in the attempt uses -- `RunIdentity.policy_id`
    defaults to `"default"`, matching this function's default, so the two
    stay in sync as long as neither default is overridden independently.

    Idempotent: upserting the same tenant/policy_id twice with the same
    inputs is a no-op in effect (it just re-writes the same row), so a
    runner can safely call this defensively without checking whether it
    already ran for this tenant.
    """
    policy = Policy(
        id=policy_id,
        tenant_id=tenant_id,
        privilege_rules=PrivilegeRules(
            privileged_actions=list(PRIVILEGED_ACTIONS),
            require_trust=True,
        ),
    )
    return store.upsert_policy(policy)
