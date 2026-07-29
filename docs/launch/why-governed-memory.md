# Why governed memory?

AI agents do not only act on prompts. They act on facts retrieved from memory,
and a single poisoned record can turn a routine workflow into a privileged
action. A memory system therefore needs more than storage and semantic search:
it needs a decision boundary around what an agent may trust and use.

GovernedMemory keeps the memory content and embeddings in the system you already
use, while adding a governance layer that records:

- provenance: where a memory came from and which records it derived from;
- trust and taint: trusted, untrusted, or quarantined state;
- purpose binding: whether a record is eligible for the caller's purpose;
- policy decisions: why a privileged action was allowed or denied; and
- tamper-evident audit history: what happened, when, and under which agent/session.

The result is practical defense in depth: suspicious content can be retained for
investigation without silently becoming eligible for retrieval or action.

Try the [hosted sandbox](https://demo.metaworkers.ai/) or run the
[Quickstart](../quickstart.md) locally. The project is MIT-licensed and
self-hosted; no managed account is required.
