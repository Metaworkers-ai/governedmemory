# GovernedMemory AgentDojo Banking benchmark — results

Model: `gemini-2.5-flash`
Suite: Banking v1.2.2, agentdojo==0.1.35
Git commit: `3142f53109ce663cc266e9b9ab7b8b0e37c158d6`
Detection backend: `ensemble`
Injection threshold: `0.7`
Classifier SHA-256: `ceaf4624f2cbfb6ea606d3ed605f5b518ef9211799ac53e49aea37a0f213152f`
Source mapping: `banking-v4-content-scored-files`
Gate policy: `tool_outputs_only`


Only a pre-execution policy denial counts as a GovernedMemory block (LLD section 16) — injection detection or taint assignment alone does not.

| Metric | 1. baseline_benign | 2. governed_benign | 3. baseline_attacked | 4. governed_attacked |
|---|---|---|---|---|
| record_count | 16 | 16 | 144 | 144 |
| valid_record_count | 16 | 16 | 144 | 144 |
| utility_success_rate | 0.500 | 0.438 | 0.535 | 0.312 |
| security_success_rate | — | — | 0.562 | 1.000 |
| targeted_asr | — | — | 0.438 | 0.000 |
| governance_block_rate | — | 0.000 | — | 0.912 |
| untrusted_evidence_rate | — | 0.053 | — | 0.166 |
| false_block_rate | — | 0.000 | — | — |
| infrastructure_error_rate | 0.000 | 0.000 | 0.000 | 0.000 |

## Latency

- **governed_benign / write_latency_ms**: mean=36.1ms, median=31.4ms, p95=65.9ms, n=38
- **governed_benign / gate_latency_ms**: mean=89.6ms, median=67.4ms, p95=201.3ms, n=3
- **governed_attacked / write_latency_ms**: mean=41.0ms, median=34.8ms, p95=71.2ms, n=463
- **governed_attacked / gate_latency_ms**: mean=174.5ms, median=191.0ms, p95=291.6ms, n=102
