"""
Unit tests for the thin SDK client (sdk/python/metaworkers/client.py).

Mocks urllib.request.urlopen -- no real network call, no server, no
Docker. Verifies the client builds correct requests and correctly parses
both successful responses and HTTP errors. End-to-end behavior against a
real running server is covered separately in
tests/integration/test_sdk_client_e2e.py.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from metaworkers import GovernedMemory, GovernedMemoryError, Source


def _mock_json_response(urlopen_mock, payload) -> None:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    urlopen_mock.return_value.__enter__.return_value = resp


@pytest.fixture()
def client():
    return GovernedMemory(base_url="http://localhost:8000", api_key="test-key")


class TestRequestConstruction:
    @patch("urllib.request.urlopen")
    def test_write_sends_bearer_auth_header(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"id": "mem-1"})
        client.write(
            customer_id="c1",
            agent_id="a1",
            session_id="s1",
            content="hi",
            source=Source(type="user", ref="msg-1"),
        )
        sent_req = mock_urlopen.call_args[0][0]
        assert sent_req.get_header("Authorization") == "Bearer test-key"

    @patch("urllib.request.urlopen")
    def test_write_posts_to_v1_memory_with_correct_body(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"id": "mem-1"})
        client.write(
            customer_id="c1",
            agent_id="a1",
            session_id="s1",
            content="hi there",
            source=Source(type="user", ref="msg-1", confidence=0.8),
            purpose=["cx_support"],
        )
        sent_req = mock_urlopen.call_args[0][0]
        assert sent_req.full_url == "http://localhost:8000/v1/memory"
        assert sent_req.get_method() == "POST"
        body = json.loads(sent_req.data)
        assert body["content"] == "hi there"
        assert body["provenance"] == {
            "source_type": "user",
            "source_ref": "msg-1",
            "confidence": 0.8,
        }
        assert body["purpose"] == {"allowed_purposes": ["cx_support"]}

    @patch("urllib.request.urlopen")
    def test_write_omits_purpose_key_when_not_given(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"id": "mem-1"})
        client.write(
            customer_id="c1",
            agent_id="a1",
            session_id="s1",
            content="hi",
            source=Source(type="user", ref="msg-1"),
        )
        body = json.loads(mock_urlopen.call_args[0][0].data)
        assert "purpose" not in body

    @patch("urllib.request.urlopen")
    def test_retrieve_posts_to_v1_retrieve(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, [])
        client.retrieve(query="refund policy", agent_id="a1", session_id="s1", k=3)
        sent_req = mock_urlopen.call_args[0][0]
        assert sent_req.full_url == "http://localhost:8000/v1/retrieve"
        body = json.loads(sent_req.data)
        assert body == {
            "query": "refund policy",
            "agent_id": "a1",
            "session_id": "s1",
            "purpose": None,
            "k": 3,
            "include_untrusted": False,
        }

    @patch("urllib.request.urlopen")
    def test_delete_sends_cascade_as_lowercase_query_param(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"success": True})
        client.delete("mem-1", cascade=True)
        sent_req = mock_urlopen.call_args[0][0]
        assert sent_req.full_url == "http://localhost:8000/v1/memory/mem-1?cascade=true"
        assert sent_req.get_method() == "DELETE"

    @patch("urllib.request.urlopen")
    def test_audit_sends_limit_as_query_param(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, [])
        client.audit(limit=25)
        sent_req = mock_urlopen.call_args[0][0]
        assert sent_req.full_url == "http://localhost:8000/v1/audit?limit=25"
        assert sent_req.get_method() == "GET"


class TestResponseParsing:
    @patch("urllib.request.urlopen")
    def test_write_returns_parsed_json(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"id": "mem-1", "content": "hi"})
        record = client.write(
            customer_id="c1",
            agent_id="a1",
            session_id="s1",
            content="hi",
            source=Source(type="user", ref="msg-1"),
        )
        assert record == {"id": "mem-1", "content": "hi"}

    @patch("urllib.request.urlopen")
    def test_quarantine_returns_bool_from_success_field(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"success": True})
        assert client.quarantine("mem-1") is True

    @patch("urllib.request.urlopen")
    def test_delete_returns_bool_from_success_field(self, mock_urlopen, client):
        _mock_json_response(mock_urlopen, {"success": True})
        assert client.delete("mem-1") is True


class TestErrorHandling:
    @patch("urllib.request.urlopen")
    def test_http_error_raises_governedmemoryerror_with_status_and_detail(
        self, mock_urlopen, client
    ):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:8000/v1/memory",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(json.dumps({"detail": "invalid API key"}).encode()),
        )
        with pytest.raises(GovernedMemoryError) as exc_info:
            client.write(
                customer_id="c1",
                agent_id="a1",
                session_id="s1",
                content="hi",
                source=Source(type="user", ref="msg-1"),
            )
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "invalid API key"

    @patch("urllib.request.urlopen")
    def test_http_error_falls_back_to_reason_when_body_is_not_json(self, mock_urlopen, client):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:8000/v1/audit",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b"not json"),
        )
        with pytest.raises(GovernedMemoryError) as exc_info:
            client.audit()
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal Server Error"

    @patch("urllib.request.urlopen")
    def test_delete_cascade_not_implemented_raises_501(self, mock_urlopen, client):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:8000/v1/memory/mem-1",
            code=501,
            msg="Not Implemented",
            hdrs=None,
            fp=io.BytesIO(json.dumps({"detail": "cascade purge needs E6"}).encode()),
        )
        with pytest.raises(GovernedMemoryError) as exc_info:
            client.delete("mem-1", cascade=True)
        assert exc_info.value.status_code == 501
