#!/usr/bin/env python3
"""Summarize opt-in, content-free adoption events from JSONL."""
from __future__ import annotations

import argparse
import json
from collections import Counter
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


def read_events(path: Path) -> tuple[Counter[str], list[str]]:
    counts: Counter[str] = Counter()
    errors: list[str] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            event: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
            continue
        name = event.get("event") if isinstance(event, dict) else None
        if name not in EVENTS:
            errors.append(f"line {line_number}: unknown event {name!r}")
            continue
        counts[name] += 1
    return counts, errors


def rate(numerator: int, denominator: int) -> str:
    return "n/a" if denominator == 0 else f"{numerator / denominator:.1%}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path, help="Content-free adoption events in JSONL format")
    args = parser.parse_args()

    counts, errors = read_events(args.events)
    print("# Adoption metrics")
    print("\n| Event | Count |\n| --- | ---: |")
    for name in EVENTS:
        print(f"| `{name}` | {counts[name]} |")
    print("\n| Funnel | Conversion |\n| --- | ---: |")
    print(
        f"| Quickstart started → completed | "
        f"{rate(counts['quickstart_completed'], counts['quickstart_started'])} |"
    )
    print(
        f"| Sandbox started → completed | "
        f"{rate(counts['sandbox_completed'], counts['sandbox_started'])} |"
    )
    print(
        f"| SDK installs → first governed operation | "
        f"{rate(counts['first_governed_operation'], counts['sdk_install'])} |"
    )
    if errors:
        print("\n## Ignored records")
        for error in errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
