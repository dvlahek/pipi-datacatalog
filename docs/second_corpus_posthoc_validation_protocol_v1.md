# Second-corpus post-hoc validation protocol V1

**Status:** FROZEN BEFORE THE VALIDATION RUNS BELOW  
**Date:** 2026-10-18  
**Scientific status:** post-hoc validation and exploratory diagnostics; the frozen H1/H2/H3 family and the already-frozen answer-drift judgments are unchanged

## Purpose

The second corpus replicated the provenance-granularity ordering in an independently constructed public corpus balanced by topical stratum. Reviewer-facing validation now targets four narrower questions that were not part of frozen H1-H3:

1. Does the deterministic Qwen3-8B/llama.cpp platform reproduce the same answer from exactly the same second-corpus evidence context?
2. Why do some second-corpus prompts exceed the unchanged 16,384-token generation context although generic text chunks use a 1,200-character window?
3. Is the frozen H2 conclusion sensitive to measuring evidence density in the retrieved set rather than only in the query-authoring source dataset(s)?
4. How often does each retrieval profile recover the query-authoring source dataset(s), without introducing new relevance judgments?

These analyses must not be relabeled as confirmatory endpoints and must not replace frozen H2.

## V1 same-evidence repeat

The validation repeats **all 162 frozen generation conditions** in the context-feasible answer subset: 81 queries times the two frozen hybrid evidence conditions.

For every condition, the repeat must use:

- the exact frozen query text
- the exact frozen serialized top-10 evidence text and order
- Qwen3-8B Q4_K_M with the same frozen GGUF SHA-256
- the same grounded system and user prompt
- reasoning off
- temperature 0
- top-p 1
- seed 20261014
- maximum output 384 tokens
- context size 16,384
- the same llama.cpp OpenAI-compatible generation path

Before generation, the script verifies that the reconstructed prompt SHA-256 and serialized-evidence SHA-256 exactly match the original frozen V2 answer row. Repeated answers are compared by exact UTF-8 answer SHA-256 against the original answer for the same query and evidence condition.

The reported endpoint is exact repeat count/rate across 162 conditions, with the identities of failures reported only by query ID and condition. This is a deterministic platform validation, not a new answer-drift endpoint.

## Structure and context audit

The publication-safe structure audit reports no source text. It reports:

- chunk character-count distribution by retained format: count, median, quartiles/IQR, p95, maximum, and count above 1,200 characters
- chunks per selected topical record: median, quartiles/IQR, p95, maximum
- logical chunks per unique dataset ID: median, quartiles/IQR, p95, maximum
- frozen prompt-token distribution over all 192 answer conditions
- token distribution over the 162 context-feasible generation conditions

The extraction contract is reported explicitly. PDF, TXT, JSON, HTML and XHTML use the generic 1,200-character window with 200-character overlap after canonicalization. **CSV is the exception:** each non-empty data row is serialized as `header:value` pairs and retained as one chunk; it is not forcibly truncated to the generic 1,200-character limit. This row-preserving rule is the primary pre-existing reason very wide CSV records can generate long evidence chunks.

## Exploratory retrieved-set density

Frozen H2 remains unchanged. Its predictor is the mean `log1p(chunks_per_dataset)` of the frozen query-authoring source dataset(s), and its frozen result remains Spearman rho = +0.155 with Holm-adjusted p = 0.131.

One post-hoc exploratory predictor is fixed here before calculation:

1. Compute total logical chunk count for every dataset ID in the frozen second-corpus logical universe.
2. For each frozen retrieval profile and query, collect the **unique dataset IDs appearing in the top-10 evidence**.
3. Compute the mean `log1p(total_logical_chunks_for_dataset)` across those unique retrieved dataset IDs.
4. For each query, average that density across the frozen content and metadata hybrid runs.
5. Correlate that query-level value with the already-frozen `chunk_churn@10 - dataset_churn@10` gap using a two-sided Spearman correlation, n = 96.

This test is explicitly exploratory. No alternative predictor will be substituted because it produces a stronger result. A non-significant result will not be described as evidence of no mechanism.

## Label-free source-target retrieval diagnostics

Each frozen query contains one or two query-authoring source dataset IDs. Without adding relevance judgments, the two frozen profiles are summarized by:

- any-authoring-source Hit@10
- reciprocal rank of the first authoring source in the top 10 (MRR@10)
- mean fraction of authoring source dataset IDs represented in the top 10; this is particularly informative for two-source relation/comparison queries

These are **authoring-source recovery diagnostics**, not graded relevance metrics and not substitutes for nDCG.

## Human validation plan

A separate second-corpus human audit is recommended because high agreement among ChatGPT, Gemini and Claude tests robustness to LLM judge choice but does not establish independent human validity.

Before any human rating begins, the audit packet and sampling seed should be frozen. The planned validation sample is:

- all 19 context-feasible strict hidden-drift pairs with `dataset Jaccard@10 = 1` and `chunk churn@10 > 0`
- plus 25 additional context-feasible pairs drawn deterministically without replacement from the remaining 62 pairs
- target: 44 blinded answer pairs
- preferably five independent assessors, each rating all 44 pairs with the same frozen 0-3 semantic-change rubric

No profile identity, prior LLM grades, aggregate answer-drift rates, or hidden-drift result is shown to assessors. Human majority/median agreement is a validation analysis, not a replacement of the already-frozen ChatGPT endpoint.

**Ethics gate:** the human packet must not be distributed until the manuscript has an accurate author-supplied statement covering assessor recruitment, voluntariness/consent, compensation if any, relationship to the author/institution, and any applicable ethics approval or exemption. These facts must not be inferred.

## Optional second-backbone extension

A BGE-M3 run on the second corpus would add post-hoc corpus-by-backbone robustness for label-free churn. It is optional and is not required to preserve the existing confirmation claim. If run, its configuration must be frozen before retrieval and reported as post-hoc robustness, not as a new confirmatory endpoint.
