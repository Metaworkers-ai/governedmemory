#!/usr/bin/env python3
"""Verify the two public Quickstart endpoints are reachable."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def fetch(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"could not reach {url}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--web-url", default="http://localhost:3000")
    args = parser.parse_args()

    health_status, health_body = fetch(args.api_url.rstrip("/") + "/healthz")
    if health_status != 200:
        raise RuntimeError(f"API health returned HTTP {health_status}")
    try:
        health = json.loads(health_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("API health did not return JSON") from exc
    if health.get("status") != "ok":
        raise RuntimeError(f"API health is not ok: {health!r}")

    web_status, _ = fetch(args.web_url)
    if web_status >= 500:
        raise RuntimeError(f"web console returned HTTP {web_status}")

    print(f"API healthy: {args.api_url.rstrip('/')}/healthz")
    print(f"Web console reachable: {args.web_url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Quickstart smoke check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
