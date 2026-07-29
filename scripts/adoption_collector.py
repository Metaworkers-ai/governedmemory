#!/usr/bin/env python3
"""Append validated, content-free adoption events to a local JSONL file.

This is deliberately a local collector. It never makes a network request and is
only used when an operator explicitly invokes it. Keep the output file private.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENTS = (
    "quickstart_started",
    "quickstart_completed",
    "sandbox_started",
    "sandbox_completed",
    "sdk_install",
    "first_governed_operation",
    "cta_clicked",
)
SURFACES = ("quickstart", "sandbox", "sdk", "site")
TOKEN_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
ANONYMOUS_ID_RE = re.compile(r"^[0-9a-f]{32}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[.-][0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SENSITIVE_FIELDS = {
    "api_key",
    "content",
    "customer_id",
    "error",
    "ip_address",
    "memory",
    "payload",
    "query",
    "tenant_id",
}
REQUIRED_FIELDS = {"event", "occurred_at", "anonymous_id", "surface", "version", "success"}


def new_anonymous_id() -> str:
    """Return a non-reversible, per-event identifier."""

    return secrets.token_hex(16)


def build_event(
    *,
    event: str,
    surface: str,
    version: str,
    success: bool,
    anonymous_id: str | None = None,
    duration_seconds: int | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Build and validate one event using only the documented fields."""

    record: dict[str, Any] = {
        "event": event,
        "occurred_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "anonymous_id": anonymous_id or new_anonymous_id(),
        "surface": surface,
        "version": version,
        "success": success,
    }
    if duration_seconds is not None:
        record["duration_seconds"] = duration_seconds
    if error_code is not None:
        record["error_code"] = error_code
    validate_event(record)
    return record


def validate_event(event: Any) -> dict[str, Any]:
    """Validate the public event contract and return the event unchanged."""

    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")
    missing = REQUIRED_FIELDS - event.keys()
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    unknown = set(event) - REQUIRED_FIELDS - {"duration_seconds", "error_code"}
    forbidden = unknown & SENSITIVE_FIELDS
    if forbidden:
        raise ValueError(f"sensitive fields are not allowed: {', '.join(sorted(forbidden))}")
    if unknown:
        raise ValueError(f"unknown fields are not allowed: {', '.join(sorted(unknown))}")
    if event["event"] not in EVENTS:
        raise ValueError(f"unknown event: {event['event']!r}")
    if event["surface"] not in SURFACES:
        raise ValueError(f"surface must be one of: {', '.join(SURFACES)}")
    if not isinstance(event["version"], str) or not VERSION_RE.fullmatch(event["version"]):
        raise ValueError("version must be a semantic version")
    if not isinstance(event["anonymous_id"], str) or not ANONYMOUS_ID_RE.fullmatch(
        event["anonymous_id"]
    ):
        raise ValueError("anonymous_id must be a 32-character lowercase hexadecimal id")
    if not isinstance(event["occurred_at"], str) or not event["occurred_at"].endswith("Z"):
        raise ValueError("occurred_at must be an ISO-8601 UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(event["occurred_at"].removesuffix("Z"))
    except ValueError as exc:
        raise ValueError("occurred_at must be an ISO-8601 UTC timestamp") from exc
    if not isinstance(event["success"], bool):
        raise ValueError("success must be a boolean")
    if "duration_seconds" in event and (
        not isinstance(event["duration_seconds"], int) or event["duration_seconds"] < 0
    ):
        raise ValueError("duration_seconds must be a non-negative integer")
    if "error_code" in event and event["error_code"] is not None:
        if not isinstance(event["error_code"], str) or not TOKEN_RE.fullmatch(event["error_code"]):
            raise ValueError("error_code must be a short lowercase token when present")
    return event


def append_event(path: Path, event: dict[str, Any]) -> None:
    """Append one validated event and keep a newly-created file owner-only."""

    validate_event(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    except BaseException:
        # fdopen owns the descriptor after entering the context manager.
        raise
    finally:
        try:
            path.chmod(0o600)
        except FileNotFoundError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="private JSONL output path")
    parser.add_argument("--event", choices=EVENTS, required=True)
    parser.add_argument("--surface", required=True, help="quickstart, sandbox, sdk, or site")
    parser.add_argument("--version", required=True)
    parser.add_argument("--anonymous-id", help="optional ephemeral id; generated when omitted")
    parser.add_argument("--duration-seconds", type=int)
    parser.add_argument("--error-code")
    result = parser.add_mutually_exclusive_group(required=True)
    result.add_argument("--success", action="store_true")
    result.add_argument("--failure", action="store_true")
    args = parser.parse_args()
    event = build_event(
        event=args.event,
        surface=args.surface,
        version=args.version,
        success=args.success,
        anonymous_id=args.anonymous_id,
        duration_seconds=args.duration_seconds,
        error_code=args.error_code,
    )
    append_event(args.file, event)
    print(f"Recorded {event['event']} in {args.file}")


if __name__ == "__main__":
    main()
