# Launch post draft

## Governed Memory: the missing policy boundary between agents and memory

AI agents increasingly act on facts they retrieved earlier. That makes memory
poisoning a product problem, not just a prompt problem: an injected instruction
stored in a CRM note, email, or tool output can look like a trustworthy fact on
the next turn.

GovernedMemory is an open-source governance layer for agent memory. It keeps
your existing memory system and semantic search, while adding provenance,
taint, purpose-bound retrieval, quarantine, policy decisions, and a
tamper-evident audit trail.

See the attack/block flow in the [hosted sandbox](https://demo.metaworkers.ai/),
then run the same path locally with the [Quickstart](../quickstart.md). If you
use Mem0 OSS, the [Mem0 adapter guide](https://github.com/Metaworkers-ai/governedmemory/blob/mem0-adapter/docs/integrations/mem0.md)
shows the intended five-line integration (adapter release pending merge).

The project is MIT-licensed. Contributions, threat-model feedback, and real
integration examples are welcome in [GitHub issues](https://github.com/Metaworkers-ai/governedmemory/issues)
and [Discord](https://discord.gg/4XFAyrMYa6).

Suggested launch links:

- Demo: https://demo.metaworkers.ai/
- Repository: https://github.com/Metaworkers-ai/governedmemory
- Quickstart: https://github.com/Metaworkers-ai/governedmemory/blob/main/docs/quickstart.md
- Community: https://discord.gg/4XFAyrMYa6
