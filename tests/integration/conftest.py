"""
Shared fixtures for tests/integration/ — a real Postgres+pgvector container
via testcontainers-python, one per test session.

test_memory_store.py defines its own copies of these same fixtures (a
test file's local fixture takes precedence over a conftest one of the same
name), so this file only actually backs newer integration test modules
(e.g. test_api.py) without touching or risking that one.

If Docker isn't available, postgres_dsn skips (not fails) so the whole
session, including anything depending on it, is skipped cleanly.
"""

from __future__ import annotations

import pytest

from core.memory_store import MemoryStore, NullEmbeddingProvider, init_db

POSTGRES_IMAGE = "pgvector/pgvector:pg16"  # official image with pgvector pre-installed


@pytest.fixture(scope="session")
def postgres_dsn():
    """Spin up a Postgres+pgvector container for the test session."""
    try:
        import docker as _docker

        _docker.from_env().ping()  # actually connect to the daemon
        from testcontainers.postgres import PostgresContainer
    except Exception as e:
        pytest.skip(f"Docker not available -- skipping integration tests: {e}")

    with PostgresContainer(POSTGRES_IMAGE) as pg:
        url = pg.get_connection_url()
        dsn = url.replace("postgresql+psycopg2://", "postgresql://")
        # Verify pgvector is actually available in this image before running any tests
        import psycopg2

        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.close()
        except Exception as e:
            pytest.skip(f"vector extension not available in {POSTGRES_IMAGE}: {e}")
        yield dsn


@pytest.fixture(scope="session")
def migrated_store(postgres_dsn):
    """Create all tables, return a store backed by the test DB."""
    init_db(postgres_dsn)
    return MemoryStore(postgres_dsn, NullEmbeddingProvider(768))


@pytest.fixture(scope="session")
def migrated_dsn(postgres_dsn):
    """DSN after tables are created — for tests that need raw DB access."""
    init_db(postgres_dsn)
    return postgres_dsn
