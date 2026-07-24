from __future__ import annotations

import json
import stat

import pytest

from scripts.adoption_collector import append_event, build_event, validate_event


def test_build_and_append_event_is_content_free_and_owner_only(tmp_path):
    path = tmp_path / "private" / "events.jsonl"
    event = build_event(
        event="quickstart_completed",
        surface="quickstart",
        version="0.1.0",
        success=True,
        duration_seconds=19,
    )

    append_event(path, event)

    assert json.loads(path.read_text()) == event
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "content" not in event
    assert len(event["anonymous_id"]) == 32


def test_validation_rejects_sensitive_fields_and_unknown_events():
    valid = build_event(event="sdk_install", surface="sdk", version="0.1.0", success=True)
    with pytest.raises(ValueError, match="sensitive fields"):
        validate_event({**valid, "content": "secret"})
    with pytest.raises(ValueError, match="unknown event"):
        validate_event({**valid, "event": "memory_content"})


def test_validation_rejects_invalid_duration_and_result():
    valid = build_event(event="sandbox_completed", surface="sandbox", version="0.1.0", success=True)
    with pytest.raises(ValueError, match="duration_seconds"):
        validate_event({**valid, "duration_seconds": -1})
    with pytest.raises(ValueError, match="success"):
        validate_event({**valid, "success": "true"})
