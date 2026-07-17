from datetime import UTC, datetime

import pytest

from scripts.discord_daily_article import (
    Article,
    RankedArticle,
    canonicalize_url,
    discord_payload,
    parse_feed,
    select_article,
    validate_webhook_url,
)


def test_parse_rss_feed_removes_source_suffix():
    feed = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <title>Example Security</title>
      <item>
        <title>New prompt injection defense - Example Security</title>
        <link>https://example.com/article</link>
        <pubDate>Thu, 16 Jul 2026 08:42:00 GMT</pubDate>
        <description>Researchers describe a new agent security control.</description>
      </item>
    </channel></rss>
    """

    articles = parse_feed(feed)

    assert len(articles) == 1
    assert articles[0].title == "New prompt injection defense"
    assert articles[0].source == "Example Security"


def test_parse_atom_feed():
    feed = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>arXiv</title>
      <entry>
        <id>https://arxiv.org/abs/1234.5678</id>
        <updated>2026-07-16T08:42:00Z</updated>
        <published>2026-07-16T08:42:00Z</published>
        <title>Securing long-term agent memory</title>
        <summary>A study of memory poisoning defenses.</summary>
        <author><name>Research Team</name></author>
        <link href="https://arxiv.org/abs/1234.5678" rel="alternate" />
      </entry>
    </feed>
    """

    articles = parse_feed(feed)

    assert len(articles) == 1
    assert articles[0].link == "https://arxiv.org/abs/1234.5678"
    assert articles[0].source == "Research Team"
    assert articles[0].summary == "A study of memory poisoning defenses."


def test_canonicalize_url_removes_tracking_and_fragment():
    assert (
        canonicalize_url("https://Example.com/post/?utm_source=newsletter&topic=agents#section")
        == "https://example.com/post?topic=agents"
    )


def test_select_article_skips_posted_and_prefers_relevance():
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    posted = Article(
        title="Agent memory security",
        link="https://example.com/posted",
        source="Source",
        summary="A security update for autonomous systems.",
        published_at=datetime(2026, 7, 17, 11, tzinfo=UTC),
    )
    weaker = Article(
        title="AI safety update",
        link="https://example.com/weaker",
        source="Source",
        summary="A broad overview.",
        published_at=datetime(2026, 7, 17, 11, tzinfo=UTC),
    )
    stronger = Article(
        title="Prompt injection and memory poisoning defenses for AI agents",
        link="https://openai.com/research/stronger",
        source="OpenAI",
        summary="Researchers describe new defenses.",
        published_at=datetime(2026, 7, 17, 10, tzinfo=UTC),
    )

    selected = select_article(
        [posted, weaker, stronger],
        {posted.identifier},
        now=now,
        max_age_days=30,
    )

    assert selected.article.link == stronger.link
    assert "memory poisoning" in selected.matched_topics
    assert "prompt injection" in selected.matched_topics


def test_discord_payload_disables_and_neutralizes_mentions():
    article = Article(
        title="Prompt injection warning for @everyone",
        link="https://example.com/article",
        source="@here Security",
        summary="An article that says hello to @everyone.",
        published_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    payload = discord_payload(
        RankedArticle(article=article, score=10, matched_topics=("prompt injection",)),
        "Governed Memory Daily",
    )

    assert payload["allowed_mentions"] == {"parse": []}
    assert "@everyone" not in payload["embeds"][0]["title"]
    assert "@here" not in payload["embeds"][0]["fields"][0]["value"]
    assert "@everyone" not in payload["embeds"][0]["description"]


def test_webhook_validation_rejects_non_discord_url():
    with pytest.raises(RuntimeError, match="unexpected format"):
        validate_webhook_url("https://example.com/webhook")
