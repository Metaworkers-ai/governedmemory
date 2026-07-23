#!/usr/bin/env python3
"""Select one relevant article and post it to the Governed Memory Discord."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_MAX_AGE_DAYS = 30
MINIMUM_RELEVANCE_SCORE = 24
DEFAULT_STATE_PATH = Path(".cache/discord-daily-article.json")
DEFAULT_WEBHOOK_NAME = "Governed Memory Daily"
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
ARXIV_QUERY = (
    '(all:"agent memory" OR all:"memory poisoning" OR all:"prompt injection" '
    'OR all:"LLM security" OR all:"AI agent security" OR all:"agentic AI security")'
)
ARXIV_FEED_URL = "https://export.arxiv.org/api/query?" + urlencode(
    {
        "search_query": ARXIV_QUERY,
        "start": 0,
        "max_results": 100,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
)

DEFAULT_FEED_URLS = (
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://www.microsoft.com/en-us/security/blog/feed/",
    "https://security.googleblog.com/feeds/posts/default",
    "https://rss.arxiv.org/rss/cs.AI",
    "https://rss.arxiv.org/rss/cs.CR",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.helpnetsecurity.com/feed/",
    ARXIV_FEED_URL,
)

TOPIC_WEIGHTS = {
    "memory poisoning": 15,
    "agent memory": 13,
    "indirect prompt injection": 12,
    "long-term memory": 11,
    "prompt injection": 10,
    "tool poisoning": 10,
    "llm security": 9,
    "rag security": 9,
    "agent security": 8,
    "model context protocol": 8,
    "mcp security": 8,
    "ai agent": 7,
    "agentic ai": 7,
    "autonomous agent": 7,
    "retrieval augmented generation": 6,
    "provenance": 6,
    "taint tracking": 6,
    "data governance": 5,
    "ai security": 5,
    "ai safety": 4,
}

TRUSTED_DOMAIN_SUFFIXES = (
    "anthropic.com",
    "arxiv.org",
    "cisa.gov",
    "deepmind.google",
    "github.com",
    "googleblog.com",
    "helpnetsecurity.com",
    "huggingface.co",
    "microsoft.com",
    "nist.gov",
    "openai.com",
    "owasp.org",
    "paloaltonetworks.com",
    "research.google",
    "security.googleblog.com",
    "thehackernews.com",
)

LOW_QUALITY_TITLE_TERMS = (
    "coupon",
    "crypto price",
    "gambling",
    "press release",
    "sponsored",
)

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


@dataclass(frozen=True)
class Article:
    title: str
    link: str
    source: str
    summary: str
    published_at: datetime

    @property
    def identifier(self) -> str:
        canonical_link = canonicalize_url(self.link)
        return hashlib.sha256(canonical_link.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RankedArticle:
    article: Article
    score: int
    matched_topics: tuple[str, ...]


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in TRACKING_QUERY_KEYS
    ]
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            urlencode(filtered_query),
            "",
        )
    )


def fetch_bytes(url: str, timeout_seconds: int = 15, attempts: int = 2) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml",
            "User-Agent": (
                "GovernedMemory-DailyArticle/1.0 (https://github.com/Metaworkers-ai/governedmemory)"
            ),
        },
    )
    last_error: OSError | urllib.error.URLError | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def plain_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_feed(feed: bytes) -> list[Article]:
    root = ET.fromstring(feed)
    if root.tag == f"{{{ATOM_NAMESPACE}}}feed":
        return parse_atom_feed(root)
    return parse_rss_feed(root)


def parse_rss_feed(root: ET.Element) -> list[Article]:
    channel = root.find("./channel")
    if channel is None:
        return []

    channel_title = plain_text(channel.findtext("title") or "")
    articles = []
    for item in channel.findall("item"):
        title = plain_text(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        summary = plain_text(item.findtext("description") or "")
        published_text = (item.findtext("pubDate") or "").strip()
        source_element = item.find("source")
        source = channel_title
        if source_element is not None:
            source = plain_text(source_element.text or "") or source

        if not title or not link or not published_text:
            continue
        try:
            published_at = parsedate_to_datetime(published_text)
        except (TypeError, ValueError):
            continue
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        articles.append(
            Article(
                title=remove_source_suffix(title, source),
                link=link,
                source=source or domain_from_url(link) or "Unknown source",
                summary=summary,
                published_at=published_at.astimezone(UTC),
            )
        )
    return articles


def parse_atom_feed(root: ET.Element) -> list[Article]:
    namespace = {"atom": ATOM_NAMESPACE}
    feed_title = plain_text(root.findtext("atom:title", default="", namespaces=namespace))
    articles = []

    for entry in root.findall("atom:entry", namespace):
        title = plain_text(entry.findtext("atom:title", default="", namespaces=namespace))
        link = atom_link(entry, namespace)
        summary = plain_text(
            entry.findtext("atom:summary", default="", namespaces=namespace)
            or entry.findtext("atom:content", default="", namespaces=namespace)
        )
        published_text = (
            entry.findtext("atom:published", default="", namespaces=namespace)
            or entry.findtext("atom:updated", default="", namespaces=namespace)
        ).strip()
        author = plain_text(
            entry.findtext("atom:author/atom:name", default="", namespaces=namespace)
        )

        if not title or not link or not published_text:
            continue
        try:
            published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        articles.append(
            Article(
                title=title,
                link=link,
                source=author or feed_title or domain_from_url(link) or "Unknown source",
                summary=summary,
                published_at=published_at.astimezone(UTC),
            )
        )
    return articles


def atom_link(element: ET.Element, namespace: dict[str, str]) -> str:
    links = element.findall("atom:link", namespace)
    for link in links:
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return (link.get("href") or "").strip()
    for link in links:
        if link.get("href"):
            return (link.get("href") or "").strip()
    return ""


def remove_source_suffix(title: str, source: str) -> str:
    suffix = f" - {source}"
    if source and title.casefold().endswith(suffix.casefold()):
        return title[: -len(suffix)].strip()
    return title


def domain_from_url(url: str) -> str:
    hostname = (urlsplit(url).hostname or "").casefold()
    return hostname.removeprefix("www.")


def is_trusted_domain(domain: str) -> bool:
    return any(
        domain == suffix or domain.endswith(f".{suffix}") for suffix in TRUSTED_DOMAIN_SUFFIXES
    )


def feed_urls_from_environment() -> tuple[str, ...]:
    configured = os.environ.get("DISCORD_ARTICLE_FEEDS", "").strip()
    if not configured:
        return DEFAULT_FEED_URLS
    values = re.split(r"[\n,]+", configured)
    feed_urls = tuple(value.strip() for value in values if value.strip())
    return feed_urls or DEFAULT_FEED_URLS


def fetch_all_articles(feed_urls: tuple[str, ...]) -> list[Article]:
    articles = []
    errors = []
    worker_count = min(6, len(feed_urls))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_url = {executor.submit(fetch_bytes, url): url for url in feed_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                articles.extend(parse_feed(future.result()))
            except (ET.ParseError, OSError, urllib.error.URLError) as exc:
                errors.append(f"{url}: {exc}")

    for error in errors:
        print(f"warning: could not read feed: {error}", file=sys.stderr)
    if not articles:
        raise RuntimeError("No configured article feed could be read")
    return articles


def rank_article(article: Article, now: datetime) -> RankedArticle | None:
    title_text = article.title.casefold()
    if any(term in title_text for term in LOW_QUALITY_TITLE_TERMS):
        return None

    searchable_text = f"{article.title} {article.summary}".casefold()
    matched_topics = tuple(topic for topic in TOPIC_WEIGHTS if topic in searchable_text)
    if not matched_topics:
        return None

    score = sum(TOPIC_WEIGHTS[topic] for topic in matched_topics)
    age = now - article.published_at
    if age <= timedelta(days=1):
        score += 8
    elif age <= timedelta(days=3):
        score += 5
    elif age <= timedelta(days=7):
        score += 2

    if is_trusted_domain(domain_from_url(article.link)):
        score += 5
    if score < MINIMUM_RELEVANCE_SCORE:
        return None
    return RankedArticle(article=article, score=score, matched_topics=matched_topics)


def select_article(
    articles: list[Article],
    posted_ids: set[str],
    *,
    now: datetime,
    max_age_days: int,
) -> RankedArticle:
    cutoff = now - timedelta(days=max_age_days)
    ranked_by_id = {}

    for article in articles:
        if article.identifier in posted_ids:
            continue
        if article.published_at < cutoff or article.published_at > now + timedelta(days=1):
            continue
        candidate = rank_article(article, now)
        if candidate is None:
            continue
        current = ranked_by_id.get(article.identifier)
        if current is None or candidate.score > current.score:
            ranked_by_id[article.identifier] = candidate

    if not ranked_by_id:
        raise RuntimeError("No fresh, relevant, unposted article was found")

    return max(
        ranked_by_id.values(),
        key=lambda candidate: (candidate.score, candidate.article.published_at),
    )


def load_posted_history(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Could not read state file {path}: {exc}") from exc
    return [str(value) for value in data.get("posted_ids", [])]


def save_posted_history(path: Path, posted_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "posted_ids": posted_ids[-500:],
        "updated_at": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def neutralize_mentions(value: str) -> str:
    return (
        value.replace("@everyone", "@\u200beveryone")
        .replace("@here", "@\u200bhere")
        .replace("<@", "<@\u200b")
    )


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def discord_payload(ranked: RankedArticle, username: str) -> dict[str, object]:
    article = ranked.article
    topics = ", ".join(ranked.matched_topics[:4])
    selection_note = f"Selected because it matches Governed Memory topics: {topics}."
    summary = truncate(neutralize_mentions(article.summary), 700)
    description = f"{summary}\n\n{selection_note}" if summary else selection_note

    return {
        "username": truncate(neutralize_mentions(username), 80),
        "content": "📚 **Daily reading: AI agent memory & security**",
        "allowed_mentions": {"parse": []},
        "embeds": [
            {
                "title": truncate(neutralize_mentions(article.title), 256),
                "url": article.link,
                "description": truncate(neutralize_mentions(description), 1000),
                "color": 0x2E6F5E,
                "fields": [
                    {
                        "name": "Source",
                        "value": truncate(neutralize_mentions(article.source), 1024),
                        "inline": True,
                    },
                    {
                        "name": "Published",
                        "value": article.published_at.strftime("%d %b %Y"),
                        "inline": True,
                    },
                ],
                "footer": {
                    "text": "Automated daily selection • Verify claims in the original source"
                },
            }
        ],
    }


def validate_webhook_url(webhook_url: str) -> None:
    valid_prefixes = (
        "https://discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
    )
    if not webhook_url.startswith(valid_prefixes):
        raise RuntimeError("The configured Discord webhook URL has an unexpected format")


def post_to_discord(webhook_url: str, payload: dict[str, object]) -> None:
    validate_webhook_url(webhook_url)
    separator = "&" if "?" in webhook_url else "?"
    request = urllib.request.Request(
        f"{webhook_url}{separator}wait=true",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GovernedMemory-DailyArticle/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in {200, 204}:
                raise RuntimeError(f"Discord returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Discord returned HTTP {exc.code}: {truncate(response_body, 500)}"
        ) from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Select and print; do not post")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=int(
            os.environ.get("DISCORD_ARTICLE_MAX_AGE_DAYS", str(DEFAULT_MAX_AGE_DAYS))
            or DEFAULT_MAX_AGE_DAYS
        ),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("DISCORD_ARTICLE_STATE", DEFAULT_STATE_PATH)),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    now = datetime.now(UTC)
    articles = fetch_all_articles(feed_urls_from_environment())
    posted_history = load_posted_history(args.state)
    selected = select_article(
        articles,
        set(posted_history),
        now=now,
        max_age_days=args.max_age_days,
    )

    print(
        json.dumps(
            {
                "dry_run": args.dry_run,
                "title": selected.article.title,
                "source": selected.article.source,
                "published_at": selected.article.published_at.isoformat(),
                "score": selected.score,
                "matched_topics": selected.matched_topics,
                "link": selected.article.link,
            },
            indent=2,
        )
    )
    if args.dry_run:
        return 0

    webhook_url = os.environ.get("DISCORD_DAILY_ARTICLE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("DISCORD_DAILY_ARTICLE_WEBHOOK_URL is not configured")
    payload = discord_payload(
        selected,
        os.environ.get("DISCORD_ARTICLE_WEBHOOK_NAME", "") or DEFAULT_WEBHOOK_NAME,
    )
    post_to_discord(webhook_url, payload)
    save_posted_history(args.state, [*posted_history, selected.article.identifier])
    print("Posted the selected article to Discord.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ET.ParseError, OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
