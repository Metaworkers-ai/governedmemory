"""Typed domain errors shared by the external-memory API and SDK."""

from __future__ import annotations


class ExternalGovernanceError(Exception):
    """A safe, structured error for an external-memory operation."""

    status_code = 422
    code = "external_governance_error"

    def __init__(self, message: str, *, metadata: dict | None = None) -> None:
        self.message = message
        self.metadata = metadata or {}
        super().__init__(message)

    def as_detail(self) -> dict:
        return {"code": self.code, "message": self.message, **self.metadata}


class IdempotencyConflict(ExternalGovernanceError):
    status_code = 409
    code = "idempotency_conflict"


class ExternalBindingConflict(ExternalGovernanceError):
    status_code = 409
    code = "external_binding_conflict"


class ExternalScopeViolation(ExternalGovernanceError):
    status_code = 403
    code = "external_scope_violation"


class ExternalOperationNotFound(ExternalGovernanceError):
    status_code = 404
    code = "external_operation_not_found"


class ExternalOperationFailed(ExternalGovernanceError):
    status_code = 409
    code = "external_operation_failed"


class ExternalWriteClaimError(ExternalGovernanceError):
    status_code = 409
    code = "external_write_claim_error"


class FingerprintConfigurationError(ExternalGovernanceError):
    status_code = 500
    code = "fingerprint_configuration_error"


class ExternalContractViolation(ExternalGovernanceError):
    status_code = 502
    code = "external_contract_violation"


class TenantMismatch(ExternalGovernanceError):
    status_code = 403
    code = "tenant_mismatch"
