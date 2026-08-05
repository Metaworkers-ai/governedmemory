#!/usr/bin/env python3
"""Check relative Markdown links without making network requests."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urlparse

LINK_RE = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def markdown_files(root: Path) -> list[Path]:
    ignored = {".git", ".venv", "node_modules", "__pycache__"}
    return sorted(
        path for path in root.rglob("*.md") if not any(part in ignored for part in path.parts)
    )


def check(root: Path) -> list[str]:
    errors: list[str] = []
    for source in markdown_files(root):
        text = source.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw_target = match.group(1)
            target = raw_target.strip().strip("<>").split()[0]
            parsed = urlparse(target)
            if parsed.scheme or parsed.netloc or target.startswith("#"):
                continue
            path, _fragment = urldefrag(target)
            if not path:
                continue
            candidate = (source.parent / path).resolve()
            if not candidate.exists():
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{source}:{line}: {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    args = parser.parse_args()
    errors = check(args.root.resolve())
    if errors:
        print("Broken local Markdown links:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Checked {len(markdown_files(args.root))} Markdown files; local links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
