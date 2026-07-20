import pytest

from core.errors import FingerprintConfigurationError
from core.memory_store import MemoryStore


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
