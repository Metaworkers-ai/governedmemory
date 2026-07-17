# Discord daily article automation

This automation scans direct publisher feeds and arXiv once per day for recent
articles about AI agent memory, memory poisoning, prompt injection, LLM
security, and RAG security. It selects one relevant unposted result and sends a
compact embed to the GovernedMemory Discord through an incoming webhook.

The workflow runs at **09:00 Asia/Kolkata (03:30 UTC)** and can also be started
manually from the GitHub Actions page. Scheduled workflows run from the
repository's default branch, so the workflow must be merged to `main` before the
daily schedule becomes active.

## Enable it

1. In Discord, create an incoming webhook for the target channel.
2. In the GitHub repository, open **Settings → Secrets and variables → Actions**.
3. Add a repository secret named `DISCORD_DAILY_ARTICLE_WEBHOOK_URL` containing
   the webhook URL.
4. Merge `.github/workflows/discord-daily-article.yml` into the default branch.
5. Open **Actions → Discord daily article → Run workflow** and leave **dry_run**
   enabled for the first test.
6. Inspect the selected article in the workflow log, then run it again with
   **dry_run** disabled to publish the first message.

Treat the webhook URL like a password. Do not commit it, paste it into an issue,
or share it in chat. Delete and recreate the webhook in Discord if it is ever
exposed.

## How selection works

The default source list includes official OpenAI, Hugging Face, Microsoft
Security, Google Security, The Hacker News, Help Net Security, and an arXiv
search. The script:

- parses RSS and Atom feeds without third-party dependencies;
- scores titles and summaries against Governed Memory topics;
- gives a small preference to fresh articles from known domains;
- rejects stale, future-dated, low-quality, and previously posted results;
- stores recent article hashes in the GitHub Actions cache; and
- disables Discord mentions and neutralizes mention-like article text.

If no suitable unposted article is available, the workflow fails without
posting unrelated content.

## Optional configuration

The defaults work without repository variables. These Actions variables can
customize the automation:

| Variable | Purpose |
| --- | --- |
| `DISCORD_ARTICLE_FEEDS` | Comma- or newline-separated RSS/Atom URLs to scan |
| `DISCORD_ARTICLE_WEBHOOK_NAME` | Override the displayed webhook name |

## Local dry run

```bash
python3 scripts/discord_daily_article.py --dry-run
```

A live local test requires the secret only in the current shell:

```bash
read -s DISCORD_DAILY_ARTICLE_WEBHOOK_URL
export DISCORD_DAILY_ARTICLE_WEBHOOK_URL
python3 scripts/discord_daily_article.py
unset DISCORD_DAILY_ARTICLE_WEBHOOK_URL
```
