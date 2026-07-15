"""
Direct tests for api/auth.py's key-resolution logic.

Lives under tests/integration/ (not tests/unit/) because it imports
fastapi, which requirements-dev.txt deliberately doesn't pull in -- see
requirements-api.txt. These tests call _load_key_map()/require_tenant()
directly rather than going through a live app + TestClient, so unlike the
rest of this directory they need neither Docker nor a database; they
exist here purely to piggyback on the CI job that already installs
fastapi (test-integration).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import _load_key_map, require_tenant


def _creds(token: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


class TestLoadKeyMap:
    def test_parses_multiple_tenant_key_pairs(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:key1,t2:key2")
        assert _load_key_map() == {"key1": "t1", "key2": "t2"}

    def test_empty_env_var_yields_empty_map(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "")
        assert _load_key_map() == {}

    def test_unset_env_var_yields_empty_map(self, monkeypatch):
        monkeypatch.delenv("GOVERNEDMEMORY_API_KEYS", raising=False)
        assert _load_key_map() == {}

    def test_tolerates_surrounding_whitespace_around_pairs(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", " t1:key1 , t2:key2 ")
        assert _load_key_map() == {"key1": "t1", "key2": "t2"}

    def test_malformed_pair_with_no_colon_is_silently_skipped(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "not-a-valid-pair,t1:key1")
        assert _load_key_map() == {"key1": "t1"}

    def test_two_tenants_configured_with_the_same_key_last_one_wins(self, monkeypatch):
        """Not validated anywhere -- a config mistake silently lets one
        tenant's key resolve to a different tenant than the operator
        intended, rather than erroring. Documenting the actual behavior."""
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:shared-key,t2:shared-key")
        assert _load_key_map() == {"shared-key": "t2"}

    def test_key_comparison_is_case_sensitive(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:MyKey")
        key_map = _load_key_map()
        assert "MyKey" in key_map
        assert "mykey" not in key_map


class TestRequireTenant:
    def test_missing_credentials_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            require_tenant(credentials=None)
        assert exc_info.value.status_code == 401

    def test_valid_key_resolves_to_its_tenant(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:key1")
        assert require_tenant(credentials=_creds("key1")) == "t1"

    def test_unknown_key_raises_401(self, monkeypatch):
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:key1")
        with pytest.raises(HTTPException) as exc_info:
            require_tenant(credentials=_creds("not-key1"))
        assert exc_info.value.status_code == 401

    def test_empty_string_key_never_matches(self, monkeypatch):
        """_load_key_map()'s `if tenant_id and key` guard means an empty
        key in the env var is never stored, so presenting an empty
        credential must still 401 rather than matching a falsy entry."""
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:")
        with pytest.raises(HTTPException) as exc_info:
            require_tenant(credentials=_creds(""))
        assert exc_info.value.status_code == 401

    def test_non_bearer_scheme_is_still_read_from_credentials_field(self, monkeypatch):
        """HTTPBearer's own parsing is what would normally reject a
        non-Bearer scheme (e.g. `Basic ...`) before this dependency ever
        runs -- require_tenant() itself only ever sees `.credentials`, so
        it resolves whatever token it's handed regardless of scheme."""
        monkeypatch.setenv("GOVERNEDMEMORY_API_KEYS", "t1:key1")
        assert require_tenant(credentials=_creds("key1", scheme="Basic")) == "t1"
