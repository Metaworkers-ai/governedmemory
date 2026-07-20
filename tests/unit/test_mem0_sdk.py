from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from metaworkers import GovernedMemory, Source


def _response(mock_urlopen, payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    mock_urlopen.return_value.__enter__.return_value = response


@patch("urllib.request.urlopen")
def test_external_write_evaluation_contract(mock_urlopen):
    _response(mock_urlopen, {"storage": "allow", "correlation_id": "c1"})
    client = GovernedMemory("http://localhost:8000", "key")
    result = client.evaluate_external_write(
        customer_id="u1",
        agent_id="a1",
        session_id="s1",
        content="hello",
        source=Source(type="user", ref="msg"),
        idempotency_key="idempotency-1",
    )
    assert result["storage"] == "allow"
    request = mock_urlopen.call_args[0][0]
    assert request.full_url.endswith("/v1/external-memories/evaluate-write")
    assert json.loads(request.data)["idempotency_key"] == "idempotency-1"


@patch("urllib.request.urlopen")
def test_candidate_evaluation_batches_candidates(mock_urlopen):
    _response(mock_urlopen, {"decisions": []})
    client = GovernedMemory("http://localhost:8000", "key")
    client.evaluate_external_candidates(
        candidates=[{"external_memory_id": "m1"}, {"external_memory_id": "m2"}],
        agent_id="a1",
        session_id="s1",
        compatibility_mode="strict",
    )
    request = mock_urlopen.call_args[0][0]
    assert request.full_url.endswith("/v1/external-memories/evaluate-candidates")
    assert len(json.loads(request.data)["candidates"]) == 2


@patch("urllib.request.urlopen")
def test_retry_binding_uses_recovery_route(mock_urlopen):
    _response(mock_urlopen, {"status": "completed"})
    client = GovernedMemory("http://localhost:8000", "key")
    client.retry_binding(correlation_id="c1", external_memory_ids=["m1"])
    request = mock_urlopen.call_args[0][0]
    assert request.full_url.endswith("/v1/external-memories/retry-binding")
