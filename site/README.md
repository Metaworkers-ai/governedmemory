# Governed Memory — landing page

A single self-contained static page (no build step, no dependencies) introducing the
project: the problem it solves, the four-stage governance pipeline, what's live vs.
in review vs. next, and a self-host quickstart. Separate in purpose from
[`web/`](../web) (the authenticated internal console) — this page is public and
requires no backend to load.

**Live:** https://d1t8rv0ba48g0k.cloudfront.net *(placeholder URL — swap once a
custom domain is attached)*

## Preview locally

It's one HTML file with everything inlined — just open it:

```bash
# Windows PowerShell, macOS, Linux
open site/index.html      # macOS
start site/index.html     # Windows
xdg-open site/index.html  # Linux
```

## Deploy

Currently deployed manually to S3 + CloudFront (private bucket, CloudFront reads it
via Origin Access Control — no public S3 access):

```bash
aws s3 cp site/index.html s3://metaworkers-governedmemory-site/index.html \
  --content-type "text/html; charset=utf-8" \
  --cache-control "public, max-age=300"

aws cloudfront create-invalidation \
  --distribution-id E1OQ1IZJWY5JA6 \
  --paths "/*"
```

Bucket and distribution live in the `ap-south-1` AWS account. No CI/CD wired up yet —
a follow-up would be a GitHub Actions job that runs this on every push to `main`
touching `site/`.
