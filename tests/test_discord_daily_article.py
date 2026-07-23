from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.discord_daily_article import (
    Article,
    canonicalize_url,
    discord_payload,
    load_posted_history,
    rank_article,
    save_posted_history,
)


def article(**overrides: object) -> Article:
    values: dict[str, object] = {
        "title": "Memory poisoning attacks against AI agent memory",
        "link": "https://arxiv.org/abs/2607.12345?utm_source=test",
        "source": "arXiv",
        "summary": "A study of prompt injection and long-term memory in an AI agent.",
        "published_at": datetime.now(UTC) - timedelta(hours=2),
    }
    values.update(overrides)
    return Article(**values)  # type: ignore[arg-type]


def test_canonicalize_url_removes_tracking_parameters() -> None:
    assert canonicalize_url(
        "HTTPS://ARXIV.ORG/abs/2607.12345/?utm_source=test&ref=feed&version=1"
    ) == "https://arxiv.org/abs/2607.12345?version=1"


def test_relevant_recent_article_is_ranked() -> None:
    ranked = rank_article(article(), datetime.now(UTC))
    assert ranked is not None
    assert ranked.score >= 24
    assert "memory poisoning" in ranked.matched_topics


def test_posted_history_round_trip(tmp_path) -> None:
    state = tmp_path / "posted.json"
    save_posted_history(state, ["first", "second"])

    assert load_posted_history(state) == ["first", "second"]
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["updated_at"]


def test_payload_neutralizes_discord_mentions() -> None:
    ranked = rank_article(
        article(summary="@everyone review this <@123> result"),
        datetime.now(UTC),
    )
    assert ranked is not None

    payload = discord_payload(ranked, "Governed Memory Daily")
    serialized = json.dumps(payload)
    assert "@everyone" not in serialized
    assert "<@123>" not in serialized
    assert payload["allowed_mentions"] == {"parse": []}
