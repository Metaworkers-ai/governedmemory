import hashlib

import pytest

from core.errors import FingerprintConfigurationError
from core.governance import GovernanceEvaluationRequest
from core.memory_store import MemoryStore
from core.models.memory_record import Provenance, SourceType


def test_fingerprints_require_secret_when_enabled(monkeypatch):
    monkeypatch.setenv("GOVERNEDMEMORY_FINGERPRINTS_ENABLED", "true")
    monkeypatch.delenv("GOVERNEDMEMORY_FINGERPRINT_SECRET", raising=False)
    with pytest.raises(FingerprintConfigurationError):
        MemoryStore._content_fingerprint("tenant-a", "secret content")


def test_fingerprint_key_is_tenant_specific(monkeypatch):
    monkeypatch.setenv("GOVERNEDMEMORY_FINGERPRINTS_ENABLED", "true")
    monkeypatch.setenv("GOVERNEDMEMORY_FINGERPRINT_SECRET", "root-secret")
    assert MemoryStore._content_fingerprint("tenant-a", "same") != MemoryStore._content_fingerprint(
        "tenant-b", "same"
    )


def test_operation_signature_requires_server_secret(monkeypatch):
    monkeypatch.delenv("GOVERNEDMEMORY_OPERATION_SECRET", raising=False)
    monkeypatch.delenv("GOVERNEDMEMORY_FINGERPRINT_SECRET", raising=False)
    with pytest.raises(FingerprintConfigurationError):
        MemoryStore._keyed_content_signature("tenant-a", "secret content")


def test_operation_context_uses_keyed_signature_and_all_decision_inputs(monkeypatch):
    monkeypatch.setenv("GOVERNEDMEMORY_OPERATION_SECRET", "operation-root-secret")
    request = GovernanceEvaluationRequest(
        operation="external_add",
        tenant_id="tenant-a",
        customer_id="customer-a",
        agent_id="agent-a",
        session_id="session-a",
        content="customer prefers email",
        provenance=Provenance(
            source_type=SourceType.USER,
            source_ref="message-a",
        ),
        source_type=SourceType.USER,
    )

    permissive = MemoryStore._operation_context(
        request,
        strict_untrusted_write=False,
    )
    strict = MemoryStore._operation_context(
        request,
        strict_untrusted_write=True,
    )

    assert "content_digest" not in permissive
    assert permissive["content_signature"] != hashlib.sha256(b"customer prefers email").hexdigest()
    assert permissive["strict_untrusted_write"] is False
    assert strict["strict_untrusted_write"] is True
    assert permissive != strict
