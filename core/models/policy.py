"""
Policy model — purpose bindings + privilege rules.

E1 defines the schema. E4 (Policy Engine) implements the evaluator that uses it.
The rbac field is an enterprise stub: defined here, always empty in OSS tier.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PurposeBinding(BaseModel):
    """Maps an agent purpose to which source types and actions it permits."""

    purpose: str  # e.g. "cx_support", "billing_review"
    allowed_source_types: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=lambda: ["read"])


class PrivilegeRules(BaseModel):
    """
    Actions that require the memory to be 'trusted' (not untrusted or quarantined).
    If require_trust=True and the memory is tainted, the privilege gate blocks the action.
    """

    privileged_actions: list[str] = Field(
        default_factory=lambda: ["send_email", "refund", "escalate"]
    )
    require_trust: bool = True


class Policy(BaseModel):
    """
    One policy document. A tenant may have many policies; each memory points to one via policy_id.
    Default policy (id="default") is created automatically by the store on first use.
    """

    id: str
    tenant_id: str
    purpose_bindings: list[PurposeBinding] = Field(default_factory=list)
    privilege_rules: PrivilegeRules = Field(default_factory=PrivilegeRules)
    rbac: list[dict] = Field(default_factory=list)  # enterprise stub — always [] in OSS
