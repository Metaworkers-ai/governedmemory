# REST example

With the Docker Quickstart running, execute:

```bash
./examples/rest/curl.sh
```

The script uses synthetic data, generates unique IDs for every run, and exits
non-zero if the governed result is wrong. It does not print memory content.
Expected output is concise and should look like:

```text
PASS health
PASS writes (benign trusted; suspicious unsafe)
PASS governed retrieval (suspicious record excluded)
PASS audit events
```

Override the local endpoints or development key when needed:

```bash
API_URL=http://localhost:8010 API_KEY=demo-key ./examples/rest/curl.sh
```

This example requires `curl` and Python 3 for JSON field extraction; it does
not require `jq`.
