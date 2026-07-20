"""Compatibility contract for the one supported Mem0 OSS release."""

from __future__ import annotations

import inspect
from importlib.metadata import PackageNotFoundError, version

import pytest
from metaworkers import ExternalContractError
from metaworkers.adapters.mem0 import GovernedMem0


def test_pinned_mem0_oss_contract():
    try:
        installed_version = version("mem0ai")
    except PackageNotFoundError:
        pytest.skip("mem0ai optional dependency is not installed")

    import mem0

    assert installed_version == "2.0.12"
    memory_cls = mem0.Memory
    add = inspect.signature(memory_cls.add)
    search = inspect.signature(memory_cls.search)
    assert "messages" in add.parameters
    assert "metadata" in add.parameters
    assert "filters" in search.parameters
    assert "top_k" in search.parameters


def test_supported_result_id_shapes_and_multiple_results():
    items, mapping = GovernedMem0._result_items(
        {"results": [{"id": "m1"}, {"metadata": {"id": "m2"}}]}
    )
    assert mapping is True
    assert [GovernedMem0._external_id(item) for item in items] == ["m1", "m2"]

    items, mapping = GovernedMem0._result_items([{"id": "m3"}, {"id": "m4"}])
    assert mapping is False
    assert [GovernedMem0._external_id(item) for item in items] == ["m3", "m4"]


@pytest.mark.parametrize(
    "payload",
    [None, {"results": "not-a-list"}, {"items": []}, {"results": ["not-a-mapping"]}],
)
def test_changed_or_malformed_result_shapes_raise(payload):
    with pytest.raises(ExternalContractError):
        GovernedMem0._result_items(payload)
