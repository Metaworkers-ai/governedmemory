#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-demo-key}"

echo "Health:"
curl --fail --silent --show-error "$API_URL/healthz"
echo

echo "Writing a benign memory:"
curl --fail --silent --show-error -X POST "$API_URL/v1/memory" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"customer-1","agent_id":"example-agent","session_id":"example-session","content":"Customer prefers email.","provenance":{"source_type":"user","source_ref":"example:benign"}}'
echo

echo "Retrieving governed memories:"
curl --fail --silent --show-error -X POST "$API_URL/v1/retrieve" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"customer preference","agent_id":"example-agent","session_id":"example-session","k":5}'
echo
