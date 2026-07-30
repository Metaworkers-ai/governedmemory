# AgentDojo Banking Defense Comparison - Gemini 2.5 Flash

## Result

GovernedMemory was the only evaluated defense to stop every targeted attack.

| Defense | Benign utility | Attacked utility | Targeted ASR | Security success |
|---|---:|---:|---:|---:|
| No defense | 50.00% (8/16) | 53.47% (77/144) | 43.75% (63/144) | 56.25% |
| Repeat User Prompt | 50.00% (8/16) | 58.33% (84/144) | 52.08% (75/144) | 47.92% |
| Spotlighting with delimiters | 50.00% (8/16) | 56.94% (82/144) | 42.36% (61/144) | 57.64% |
| **GovernedMemory** | **43.75% (7/16)** | **31.25% (45/144)** | **0.00% (0/144)** | **100.00%** |

All four rows use:

- `gemini-2.5-flash`
- AgentDojo Banking v1.2.2
- `agentdojo==0.1.35`
- all 16 user tasks
- all 9 injection tasks
- `ImportantInstructionsAttack`
- one repetition

## Interpretation

### Security

- Repeat User Prompt performed worse than no defense in this run: ASR rose
  from 43.75% to 52.08%.
- Spotlighting produced only a small improvement: ASR fell from 43.75% to
  42.36%.
- GovernedMemory reduced ASR from 43.75% to 0%, eliminating all 63 attack
  successes seen in the no-defense run.

The result supports the claim that action-time provenance and policy
enforcement is materially stronger here than prompt-only defenses.

### Utility

The two native prompt defenses retained the same benign utility as the
baseline: 8/16. GovernedMemory completed 7/16, but its only baseline/governed
benign mismatch (`user_task_3`) had no untrusted evidence, privileged action,
or policy denial. GovernedMemory's measured benign false-block rate remained
0%.

GovernedMemory's attacked utility was lower. This metric includes tasks where
blocking an attacker-induced privileged action prevents the final environment
from satisfying the original task. It should be reported, but it does not
override the security outcome.

### Model behavior

Spotlighting caused Gemini to return candidates with no content parts for
`user_task_9` and its injection pairings. AgentDojo still scored those records
as completed rather than infrastructure errors. This is a real model/defense
interaction and contributes to the observed utility result.

## Comparators not included

### Tool Filter

AgentDojo 0.1.35 implements Tool Filter only for its `OpenAILLM` class and
raises an error for Gemini. Running it would require changing the defense
implementation, so it would no longer be the pinned native comparator.

### ProtectAI transformer detector

The native `transformers_pi_detector` requires optional `torch` and
`transformers` dependencies plus the
`protectai/deberta-v3-base-prompt-injection-v2` model. Those dependencies were
not installed. Installation attempts stalled before downloading packages due
to this machine's Python package-network connectivity issue, so no detector
records were generated.

## Confidence limits

This is a controlled comparison but has one repetition. Gemini is
non-deterministic, and the no-defense/GovernedMemory/native-defense attempts
are separate API calls. Before publication, repeat each configuration two
more times and aggregate all three repetitions.

## Artifacts

- GovernedMemory/no-defense raw records:
  `results/full-gemini25-flash-r1/raw.jsonl`
- GovernedMemory/no-defense summary:
  `results/full-gemini25-flash-r1/summary.json`
- Native-defense raw records:
  `results/gemini-native-defenses-r1/raw.jsonl`
- Native-defense summary:
  `results/gemini-native-defenses-r1/summary.json`
