# C2 Qwen answer-drift secondary-judge replication protocol V1

**Status:** FROZEN BEFORE GEMINI OR CLAUDE JUDGING  
**Date:** 2026-10-18  
**Scientific status:** post-confirmatory judging-robustness analysis  
**Primary frozen judge:** ChatGPT blinded pass already completed and frozen before private A/B mapping was opened

## Purpose

This protocol tests whether the C2 Qwen V2 semantic-change result is robust to two additional independent blinded judges. It does not redefine the primary C2 answer-drift endpoint and does not alter any frozen ChatGPT grade.

The two replication judges are:

- `GEMINI_C2_SECONDARY_JUDGE_V1`
- `CLAUDE_C2_SECONDARY_JUDGE_V1`

Each judge must evaluate the same 81 blinded answer pairs independently.

## Materials given to each replication judge

Each judge receives exactly one research-data file:

`qwen_answer_pairs_v2_blinded.json`

Frozen SHA-256:

`0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa`

The file contains the query, blinded answer A, blinded answer B, theme, query type, pair ID and answer hashes. Retrieval-profile identity is hidden.

The judge must not receive or inspect any of the following before all 81 grades are complete:

- `qwen_answer_pairs_v2_mapping_PRIVATE.json`
- ChatGPT judgments or their grade distribution
- C2 answer-drift rates
- theme/query-type answer-drift breakdowns
- hidden-drift answer-level results
- unblinded descriptive results
- manuscript text reporting the C2 answer result

No outside web search, memory, external source checking or truth verification is used. The task is semantic-change judging between answer A and answer B relative to the supplied query, not factual adjudication against the world.

## Frozen ordinal rubric

Each pair receives exactly one integer grade:

- `0` — semantically the same; wording-only differences
- `1` — minor difference; same substantive conclusion
- `2` — materially different content, support, qualification or conclusion
- `3` — substantially different or contradictory

Grades `2` and `3` define material answer drift.

The judgment is symmetric. The judge must not decide which answer is better, more correct or preferred. A material difference can be present even when the judge cannot determine which answer is factually correct.

### Grading guidance

Use grade `0` when the answers communicate the same substantive information and differ only in phrasing, citation placement or harmless detail.

Use grade `1` when one answer adds or omits secondary detail but both preserve the same substantive answer, conclusion and qualification.

Use grade `2` when the answers differ in a way that can change what a reader would take away, including a different value/entity, materially different support, materially different scope, a changed qualification, or an answer-versus-insufficient-evidence difference.

Use grade `3` for strong contradictions, mutually incompatible substantive answers, or major answer-versus-no-answer reversals where the two responses would lead a reader to substantially different conclusions.

Do not upgrade a pair merely because wording differs, answer length differs or citation labels differ. Do not downgrade a pair merely because both answers are plausible.

## Required judgment output

Each external judge must return exactly 81 records, one for every `pair_id` in the blinded packet, preserving the packet order.

Required JSONL schema:

```json
{"pair_id":"...","query_id":"...","grade":0,"note":"brief optional rationale"}
```

Rules:

- `grade` must be one of `0,1,2,3`
- `pair_id` and `query_id` must be copied exactly from the blinded packet
- no pair may be omitted or duplicated
- `note` should be brief and must not mention or infer profile identity
- no aggregate counts, rates or interpretation should be calculated before all 81 row-level grades are complete

Expected output filenames:

- Gemini: `c2_qwen_v2_judgments_gemini_v1.jsonl`
- Claude: `c2_qwen_v2_judgments_claude_v1.jsonl`

## Frozen robustness analysis

After both external judgment files are frozen, the analysis will report the original ChatGPT judge and the two replication judges separately. No judge will be discarded because of its outcome.

For each judge:

- grade distribution 0/1/2/3
- material count and rate, grades 2-3
- Wilson 95% interval for the material rate

Across judges:

- pairwise exact ordinal agreement
- pairwise within-one-grade agreement
- pairwise quadratic weighted kappa
- pairwise binary agreement for non-material (`0-1`) versus material (`2-3`)
- three-judge all-exact ordinal agreement
- three-judge binary unanimity
- three-judge median ordinal grade for each pair
- median-grade material rate, where median grade >= 2 is material

With three judges, the median-grade material classification is equivalent to a two-of-three majority at the binary material threshold. This is a pre-specified sensitivity summary, not a replacement of the original frozen ChatGPT result.

No adjudication pass will be introduced merely because judges disagree. If disagreement is substantial, it will be reported as judging uncertainty.

## Evidential boundary

The original ChatGPT result remains the frozen C2 V2 answer-drift result produced before these replication judgments. Gemini and Claude provide post-hoc judging robustness only.

The replication analysis must not be described as:

- a new C2 confirmatory endpoint
- independent replication of retrieval H1/H2/H3
- factual accuracy evaluation
- evidence that one retrieval profile is more correct
- justification for changing any previously frozen grade

The correct interpretation is sensitivity of the semantic-change endpoint to judge choice.
