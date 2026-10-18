# C2 Qwen answer-drift context-feasible amendment V2

**Status:** FROZEN BEFORE V2 ANSWER GENERATION  
**Date:** 2026-10-18  
**Scientific status:** post-confirmatory descriptive technical amendment

## Why V2 is needed

The C2 answer-drift V1 plan copied the C1 Qwen generation contract exactly, including a 16,384-token context window and a 384-token output allowance. After V1 generation started, llama.cpp rejected an oversized frozen prompt. Generation was stopped and no answer text was inspected for scientific interpretation.

A dedicated token-count audit was then run over all 192 frozen C2 conditions using the same Qwen llama.cpp tokenizer. The audit reported:

- 192 total conditions
- 27 conditions whose input alone exceeded 16,384 tokens
- 27 conditions that also failed `input_tokens + 384 <= 16,384`
- median input length 5,029 tokens
- maximum input length 81,255 tokens
- maximum single frozen evidence text observed in the largest prompts: 33,970 characters

The audit SHA-256 is:

`4af1779c50cc05a7a688fb08014f1a3e7f60cdd37bea1a2ec2523ed3ba7937cc`

This is a technical feasibility failure of the V1 generation adapter under the frozen C1 context size. It does not alter the frozen C2 retrieval results or C2-H1/H2/H3.

## V1 disposition

The partial V1 answer file is retained unchanged for provenance. Its answers are not reused in V2 and are not analyzed. V1 is treated as an incomplete technical attempt, not as a scientific answer-drift result.

## Frozen V2 rule

V2 keeps the complete C1/Qwen generation contract unchanged:

- Qwen3-8B Q4_K_M, same GGUF SHA-256
- reasoning off
- temperature 0
- top-p 1
- seed 20261014
- max output tokens 384
- context size 16,384
- identical grounded-only prompt
- identical C2 evidence serialization
- identical frozen top-10 evidence order and text

No evidence is truncated and the context window is not increased.

A C2 query is included in V2 only when **both** of its frozen retrieval conditions satisfy:

`input_tokens + 384 <= 16,384`

The two required conditions are:

1. `hybrid-e5-content-v1`
2. `hybrid-e5-metadata-v1`

If either condition fails, the entire query pair is excluded. This preserves a paired answer-drift design and prevents condition-specific missingness.

The rule is deterministic and depends only on frozen prompt length measured before V2 answer generation. It does not use answer text, answer-drift grade, retrieval quality, theme performance, or any downstream outcome.

## Reporting boundary

V2 answer drift remains secondary and descriptive. The denominator is the number of complete context-feasible query pairs, not all 96 C2 queries.

Every report must state:

- included and excluded query counts
- coverage rate
- excluded-condition counts by retrieval profile
- descriptive excluded-query distribution by theme and query type

The V2 rate must not be presented as an estimate for all 96 C2 queries without the context-feasible-subset qualification.

## Why no truncation or larger context

Post-hoc truncation would change the evidence supplied to the generator and introduce a new evidence-selection rule. Increasing the context window would change the frozen C1 generation contract and still would not solve the largest 81k-token prompts without substantial extrapolation beyond the original setting. The complete-pair feasibility rule is therefore the narrowest amendment that preserves the original prompt, model, evidence text, evidence order, and context size for every analyzed pair.
