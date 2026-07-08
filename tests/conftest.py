"""
Shared pytest fixtures for the governed memory test suite.

UNIT TESTS (tests/unit/)
  - No Docker required
  - Use NullEmbeddingProvider (zero vectors, instant)
  - Pure Python — validate models, logic, invariants

INTEGRATION TESTS (tests/integration/)
  - Requires Docker (starts a real Postgres+pgvector container automatically)
  - Uses testcontainers-python to spin up and tear down Postgres per test session
  - Tests the full write→read→search→delete path against a real DB
  - If Docker is not available, integration tests are skipped automatically

HOW TO RUN
  Unit only (fast, no Docker):
    pytest tests/unit/ -v

  Integration only:
    pytest tests/integration/ -v

  Full suite with coverage:
    pytest -v --cov=core --cov-report=term-missing

  Or via Makefile:
    make test-unit
    make test-integration
    make test
"""

import pytest

from core.memory_store.embeddings import NullEmbeddingProvider

# ---- Shared fixtures available to ALL tests ----


@pytest.fixture(scope="session")
def null_embedder():
    """768-dim zero-vector embedder. No model download needed."""
    return NullEmbeddingProvider(dimensions=768)


@pytest.fixture(scope="session")
def sample_tenant_id():
    return "tenant-acme-corp"


@pytest.fixture(scope="session")
def sample_customer_id():
    return "cust-jane-001"
