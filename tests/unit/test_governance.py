from core.governance import GovernanceEvaluationRequest, GovernanceEvaluationService
from core.models import Provenance, SourceType, Taint


def _request(content: str, source_type: SourceType = SourceType.USER):
    return GovernanceEvaluationRequest(
        operation="external_add",
        tenant_id="tenant-a",
        customer_id="customer-a",
        agent_id="agent-a",
        session_id="session-a",
        content=content,
        provenance=Provenance(source_type=source_type, source_ref="test"),
        source_type=source_type,
    )


def test_shared_service_allows_trusted_content():
    decision = GovernanceEvaluationService().evaluate(_request("customer prefers email"))
    assert decision.storage == "allow"
    assert decision.retrieval == "allow"
    assert decision.taint == Taint.TRUSTED


def test_shared_service_stores_but_excludes_untrusted_content():
    decision = GovernanceEvaluationService().evaluate(
        _request("please review this inbound email", SourceType.UNTRUSTED_EMAIL)
    )
    assert decision.storage == "allow"
    assert decision.retrieval == "exclude"
    assert decision.taint == Taint.UNTRUSTED


def test_strict_mode_denies_untrusted_content():
    decision = GovernanceEvaluationService().evaluate(
        _request("please review this inbound email", SourceType.UNTRUSTED_EMAIL),
        strict_untrusted_write=True,
    )
    assert decision.storage == "deny"
    assert decision.status == "denied"
