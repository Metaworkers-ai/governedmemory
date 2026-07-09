"""Shared FastAPI dependencies -- primarily the MemoryStore singleton built
at startup (see api/main.py's lifespan). MemoryStore opens its own
connection per call, so one instance safely serves concurrent requests."""

from __future__ import annotations

from fastapi import Request

from core.memory_store import MemoryStore


def get_store(request: Request) -> MemoryStore:
    return request.app.state.store
