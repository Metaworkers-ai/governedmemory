"""Minimal Mem0 OSS adapter example.

Requires ``pip install -e 'sdk/python[mem0]'`` and a Mem0 configuration. The
adapter keeps Mem0 as the system of record while GovernedMemory evaluates and
audits the operation.
"""

from mem0 import Memory
from metaworkers import GovernedMem0, GovernedMemory, Source

memory = GovernedMem0(
    Memory(),
    GovernedMemory("http://localhost:8000", "demo-key"),
    tenant_id="solstice-cloud",
)

result = memory.add(
    "Customer prefers email.",
    user_id="customer-1",
    source=Source(type="user", ref="example:mem0"),
)
print(result["governance"]["taint"])
