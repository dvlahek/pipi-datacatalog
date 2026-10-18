# C2 Qwen answer-drift judging protocol V2

**Status:** FROZEN BEFORE V2 ANSWER-PAIR JUDGING  
**Freeze date:** 2026-10-18  
**Scientific status:** post-confirmatory descriptive extension on the frozen context-feasible subset

## Scope

This protocol applies only to the 81 complete C2 query pairs retained by the frozen V2 context-feasibility rule. The 15 excluded queries remain excluded. The 8 partial V1 answers are provenance-only and are not reused.

Generation is already frozen:

- 81 queries
- 162 answers
- coverage of the original 96-query C2 set: 84.375%
- Qwen GGUF SHA-256: `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`
- frozen answers SHA-256: `c59a19c51cb05395cb4fbee23edb601f8f3b68e23940c14a54fbac5d434627b3`
- frozen answer-freeze SHA-256: `e03a321671b7e5f243d033ff506862c12c5b089ad2066a5b99711ed131df64ed`

No answer content was used to define the context-feasible subset.

## Blinding

The original C2 blinding seed is retained unchanged:

`SECOND_CORPUS_C2_ANSWER_DRIFT_BLIND_V1`

For each query, A/B orientation is determined only by:

`SHA256(seed + "|" + query_id)`

The lowest bit of the first digest byte determines whether the two frozen retrieval conditions are swapped. This operation is deterministic and independent of answer content.

The judging packet exposes:

- pair ID
- query ID
- theme
- query type
- query text
- Answer A
- Answer B

It does not expose which answer came from `hybrid-e5-content-v1` or `hybrid-e5-metadata-v1`.

The A/B mapping is written to a separate local file and must not be opened during judging.

## Ordinal rubric

Use the frozen C1/C2 rubric:

- **0** — semantically the same answer; wording-only differences
- **1** — minor difference; same substantive conclusion
- **2** — materially different content, support, qualification, or conclusion
- **3** — substantially different or contradictory answer

Grades **2–3** count as material answer drift.

The endpoint is symmetric. The judge does not decide that A or B is better, more correct, or more grounded. The task is only to classify the magnitude of substantive difference between the two answers.

## Judging rules

Judge each pair independently from the displayed query and answers only.

Do not use:

- retrieval-profile identity
- hidden A/B mapping
- C2 retrieval churn values
- source multiplicity values
- theme-level or query-type result summaries
- previously computed answer-drift rates

A short note may be recorded for difficult grades, but the ordinal grade is the analysis input.

## Pre-judging analysis contract

After all 81 grades are frozen, report descriptively:

1. material-drift count and rate, denominator 81
2. Wilson 95% confidence interval for the material-drift proportion
3. grade counts for 0, 1, 2, and 3
4. exact-answer-text-change count and rate
5. descriptive material-drift rates by theme
6. descriptive material-drift rates by query type
7. material-drift rate within the already-frozen hidden-retrieval-drift subset
8. exploratory association between ordinal grade and frozen chunk churn
9. context-feasibility coverage and exclusion breakdown from V2

No answer-level p-value is a C2 confirmatory endpoint. Theme/query-type subgroup values are descriptive. Any association with retrieval churn is exploratory.

## Reporting boundary

The answer-drift result must be described as applying to the **81 context-feasible complete query pairs**, not to all 96 C2 queries.

Permitted form:

> In the post-confirmatory C2 answer-drift extension, X of 81 context-feasible frozen query pairs showed material answer differences under Qwen3-8B. The subset retained 84.4% of the 96-query C2 set under the unchanged 16,384-token generation context.

Not permitted:

- answer drift was confirmed on all 96 C2 queries
- preregistered C2 answer-drift hypothesis
- generator-independent answer drift
- causal effect on answer correctness
- omission of the context-feasibility restriction
