# C2 Qwen answer-drift descriptive extension V1

**Status:** FROZEN BEFORE ANY C2 ANSWER GENERATION  
**Freeze date:** 2026-10-17  
**Scientific status:** post-confirmatory descriptive extension

## Purpose

The confirmatory C2 retrieval analysis is already frozen. C2-H1 was supported, C2-H2 was not statistically supported, and C2-H3 achieved exact replay. This extension does not alter those results and does not add a new confirmatory hypothesis.

The purpose is narrower: describe whether the already-frozen content-versus-metadata retrieval intervention propagates into materially different grounded answers on the 96 C2 confirmation queries.

The decision to run this extension was made after inspecting the frozen C2 retrieval-drift results. Therefore all answer-level results are secondary/descriptive and must not be presented as prospectively confirmatory evidence.

## Generator

Only the C1 primary generator is run in V1:

- model key: `qwen3-8b-q4km`
- family: Qwen3
- file: `Qwen3-8B-Q4_K_M.gguf`
- GGUF SHA-256: `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`
- reasoning mode: off
- backend: llama.cpp OpenAI-compatible local server

The generation settings and prompt are copied exactly from the frozen C1 RQ3 protocol:

- temperature 0
- top-p 1
- seed 20261014
- max tokens 384
- maximum answer length requested in prompt: 180 words
- context size 16384
- sampling disabled
- same grounded-only system prompt and user template

No prompt, decoding, model, or retrieval parameter may be changed after C2 answer generation starts.

## Frozen evidence conditions

Each of the 96 frozen C2 queries is generated under exactly two already-frozen retrieval conditions:

1. `hybrid-e5-content-v1`
2. `hybrid-e5-metadata-v1`

Each condition uses the exact ordered top-10 evidence frozen in `results/second_corpus_retrieval_v1/primary_retrieval_runs.jsonl`.

The C2 evidence serializer is a format adapter only. For each evidence item it exposes:

- evidence label `[E1]` ... `[E10]`
- dataset identifier
- distribution identifier
- chunk index
- frozen URL-derived file path when available
- exact frozen chunk text

Retrieval-profile identity is never included in the generator prompt.

## Generation count

Main generation count:

`96 queries x 2 evidence conditions = 192 answers`

No C2 same-evidence stability subset is added in V1 because the C2 protocol did not prospectively define such a subset. The C1 control result remains a C1 systems validation and is not relabeled as C2 evidence.

## Descriptive answer-drift analysis

After all 192 answers are generated and frozen, answer pairs are blinded. Content-versus-metadata identity is hidden and A/B order is assigned deterministically from a frozen seed before judging.

The ordinal material-change rubric is copied from C1:

- 0: semantically the same answer; wording-only differences
- 1: minor difference; same substantive conclusion
- 2: materially different content, support, qualification, or conclusion
- 3: substantially different or contradictory answer

Grades 2-3 count as material answer drift.

Planned descriptive outputs:

- overall material-drift count/rate and Wilson interval
- grade distribution 0-3
- exact-text-change rate
- descriptive breakdown by theme and query type
- descriptive answer drift within the frozen hidden-retrieval-drift subset
- exploratory association with frozen chunk churn

No p-value from this answer extension is a C2 confirmatory endpoint.

## Replication generators

Ministral and Gemma are not part of V1. A later run may use the already-frozen C1 replication generator settings as a post-hoc robustness extension. Such a decision must not change or relabel the Qwen V1 result.

## Reporting guardrails

Permitted:

> In a post-confirmatory descriptive C2 extension, changing only the frozen retrieval representation produced material grounded-answer differences in X of 96 queries under Qwen3-8B.

Not permitted:

- C2 answer-drift hypothesis confirmed
- preregistered answer-drift replication
- generator-independent
- causal effect on answer correctness
- selective omission of weak or null Qwen results
