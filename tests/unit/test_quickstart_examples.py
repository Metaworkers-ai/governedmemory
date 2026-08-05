from __future__ import annotations

from pathlib import Path

import pytest

from api.schemas import RetrieveBody, WriteBody
from examples.python_sdk.quickstart import ExampleValidationError, validate_flow
from scripts.check_docs_links import check
from scripts.smoke_quickstart import build_synthetic_payloads, run_smoke


class FakeQuickstartAPI:
    def __init__(self, include_suspicious: bool = False) -> None:
        self.include_suspicious = include_suspicious

    def request(self, url, method, _headers, body, _timeout):
        path = url.split("http://api", 1)[-1]
        if path == "/healthz":
            return {"status": "ok"}
        if path == "/v1/memory":
            suspicious = body["provenance"]["source_type"] == "untrusted_email"
            return {
                "id": "suspicious-id" if suspicious else "benign-id",
                "trust": {"taint": "untrusted" if suspicious else "trusted"},
                "audit_id": "suspicious-audit" if suspicious else "benign-audit",
            }
        if path == "/v1/retrieve":
            records = [{"id": "benign-id"}]
            if self.include_suspicious:
                records.append({"id": "suspicious-id"})
            return records
        if path.startswith("/v1/audit"):
            return [
                {"id": "benign-audit", "op": "write"},
                {"id": "suspicious-audit", "op": "write"},
                {"id": "retrieve-audit", "op": "retrieve"},
            ]
        raise AssertionError(f"unexpected request: {method} {path}")


def test_smoke_success_uses_synthetic_payloads_and_checks_audit(capsys):
    fake = FakeQuickstartAPI()
    run_smoke(
        api_url="http://api",
        web_url="http://web",
        request_fn=fake.request,
        status_fn=lambda _url, _timeout: 200,
    )

    output = capsys.readouterr().out
    assert "PASS health" in output
    assert "PASS audit events" in output
    assert "SYSTEM OVERRIDE" not in output


def test_smoke_fails_when_governed_retrieval_leaks_suspicious_record():
    fake = FakeQuickstartAPI(include_suspicious=True)
    with pytest.raises(RuntimeError, match="returned the suspicious record"):
        run_smoke(
            api_url="http://api",
            web_url="http://web",
            request_fn=fake.request,
            status_fn=lambda _url, _timeout: 200,
        )


def test_smoke_payloads_match_rest_contract():
    _marker, benign, suspicious, retrieve = build_synthetic_payloads()
    for body in (benign, suspicious):
        assert {"customer_id", "agent_id", "session_id", "content", "provenance"} <= body.keys()
        assert body["provenance"]["source_type"] in {"user", "untrusted_email"}
        assert WriteBody.model_validate(body).customer_id == body["customer_id"]
    assert {"query", "agent_id", "session_id", "k"} <= retrieve.keys()
    assert RetrieveBody.model_validate(retrieve).k == 10


def test_python_example_validation_rejects_unsafe_contract_breaks():
    benign = {"id": "benign", "trust": {"taint": "trusted"}}
    suspicious = {"id": "suspicious", "trust": {"taint": "untrusted"}}
    validate_flow(benign, suspicious, [{"id": "benign"}])

    with pytest.raises(ExampleValidationError, match="benign memory"):
        validate_flow({"id": "benign", "trust": {"taint": "untrusted"}}, suspicious, [])
    with pytest.raises(ExampleValidationError, match="suspicious memory"):
        validate_flow(benign, {"id": "suspicious", "trust": {"taint": "trusted"}}, [])
    with pytest.raises(ExampleValidationError, match="returned the suspicious"):
        validate_flow(benign, suspicious, [{"id": "suspicious"}])


def test_docs_checker_accepts_existing_link_and_reports_missing(tmp_path: Path):
    (tmp_path / "target.md").write_text("# Target\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("[ok](target.md)\n", encoding="utf-8")
    assert check(tmp_path) == []

    (tmp_path / "README.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    errors = check(tmp_path)
    assert len(errors) == 1
    assert "missing.md" in errors[0]


def test_rest_example_declares_complete_flow():
    script = Path("examples/rest/curl.sh").read_text(encoding="utf-8")
    for route in ("/healthz", "/v1/memory", "/v1/retrieve", "/v1/audit"):
        assert route in script
    assert 'API_URL="${API_URL:-http://localhost:8000}"' in script
    assert 'API_KEY="${API_KEY:-demo-key}"' in script
    assert "suspicious record" in script
