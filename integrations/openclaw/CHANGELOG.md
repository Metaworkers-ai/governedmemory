# Changelog

## 0.1.0 — 2026-07-23

Initial working plugin, verified live on a real OpenClaw gateway.

- Three lifecycle hooks: `message_received`, `before_prompt_build`, `before_tool_call`
- Injection-scores inbound content via the Governed Memory REST API (`POST /v1/memory`)
- Blocks sensitive tool calls (`web_fetch`, `send_money`, `send_email`, etc.) when the
  current turn is flagged as poisoned (injection score >= threshold)
- Turn-level gating: a poisoned turn blocks tools for that turn only
- Configurable injection threshold (default 0.7) and sensitive tool list
- `web_fetch` included in default sensitive tools (confirmed exfiltration vector)
- Live demo: poisoned "SYSTEM OVERRIDE" prompt scored 0.98, blocked; benign fetch passed
