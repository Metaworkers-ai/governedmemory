"""Compatibility contract for the one supported Mem0 OSS release."""

from __future__ import annotations

import inspect
from importlib.metadata import version

import pytest


def test_pinned_mem0_oss_contract():
    mem0 = pytest.importorskip("mem0")
    assert version("mem0ai") == "2.0.12"
    memory_cls = mem0.Memory
    add = inspect.signature(memory_cls.add)
    search = inspect.signature(memory_cls.search)
    assert "messages" in add.parameters
    assert "metadata" in add.parameters
    assert "filters" in search.parameters
    assert "top_k" in search.parameters
