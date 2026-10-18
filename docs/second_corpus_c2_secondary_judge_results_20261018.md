# C2 Qwen V2 secondary-judge robustness — results record

**Date:** 2026-10-18  
**Scientific status:** post-confirmatory judging-robustness analysis  
**Primary frozen endpoint:** ChatGPT blinded semantic-change judgments  
**Replication judges:** Gemini and Claude

## Scope

This analysis tests sensitivity of the C2 Qwen V2 semantic-change endpoint to judge choice. It does not change any frozen ChatGPT grade, does not alter C2 H1/H2/H3, and is not a factual-accuracy evaluation.

All three judges evaluated the same 81 blinded answer pairs using the same frozen 0–3 rubric. Grades 2–3 define material answer drift.

The Gemini and Claude judges received only the blinded packet. They did not receive the private A/B mapping, ChatGPT grades, aggregate answer-drift results, hidden-drift results, or manuscript text reporting the C2 answer result.

## Frozen input anchors

- blinded packet SHA-256: `0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa`
- ChatGPT judgments SHA-256: `61a82e092fc1ea62887061ada03c19c49fb4810332b8cb2a2f533e5acbd3b144`
- Gemini judgments SHA-256: `e0c83139f02f598802d4895e70ce3d025db589b8193f434ea4cdf25fa1a1afe4`
- Claude judgments SHA-256: `7fdc956e7294e0fcd73455e58f583b37609980b3d216210a6047645f5ba3fccf`
- secondary-judge validation freeze SHA-256: `b0b97af9a3ffe331a90615b9c123866d5360f4fab1b5577442bf0bb0c20f7d76`

Both replication files contained exactly 81 unique pair/query identities in the exact blinded-packet order and all grades were valid integers in 0–3 before aggregate analysis.

## Material answer drift by judge

| Judge | Grade 0 | Grade 1 | Grade 2 | Grade 3 | Material | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| ChatGPT | 15 | 35 | 11 | 20 | 31/81 | **38.27%** | 28.45–49.16% |
| Gemini | 31 | 18 | 12 | 20 | 32/81 | **39.51%** | 29.57–50.39% |
| Claude | 18 | 30 | 13 | 20 | 33/81 | **40.74%** | 30.70–51.62% |

The binary material-drift rate is therefore highly stable across judge choice: 38.3%, 39.5%, and 40.7%.

## Pairwise agreement

| Judge pair | Exact ordinal | Within one grade | Quadratic weighted kappa | Binary material agreement |
|---|---:|---:|---:|---:|
| ChatGPT–Gemini | 74.07% | **100%** | **0.900** | 93.83% |
| ChatGPT–Claude | 88.89% | **100%** | **0.952** | 97.53% |
| Gemini–Claude | 75.31% | **100%** | **0.907** | 93.83% |

No pair of judges differed by more than one ordinal grade on any of the 81 cases.

## Three-judge sensitivity

Across all three judges:

- exact ordinal unanimity: **56/81 = 69.14%**
- binary material/non-material unanimity: **75/81 = 92.59%**
- unanimously material: **29/81**
- unanimously non-material: **46/81**
- binary-threshold disagreement: **6/81**

The frozen median-grade sensitivity rule gives:

- median grade 0: 19
- median grade 1: 30
- median grade 2: 12
- median grade 3: 20
- material under median grade >= 2: **32/81 = 39.51%**
- Wilson 95% CI: **29.57–50.39%**

With three judges, the median-grade binary classification is equivalent to a two-of-three majority at the material threshold.

The median/majority result is almost identical to the original frozen ChatGPT endpoint of 31/81 = 38.27%, so the main C2 answer-drift conclusion is not sensitive to the choice among these three blinded judges.

## Interpretation

The robustness layer strengthens the answer-level evidence without changing its evidential status. The original ChatGPT result remains the frozen C2 V2 answer-drift endpoint. Gemini and Claude are post-hoc independent judging replications.

The correct claim is that the semantic-change rate is robust to judge choice under the frozen rubric. This analysis does not establish which answer is factually correct and does not show that one retrieval profile is more accurate.

No adjudication pass is introduced because the pre-specified protocol treats judge disagreement as uncertainty rather than an invitation to change frozen grades.

## Publication-safe reproducibility

Raw external-judge JSONL files remain local frozen artifacts. The public repository exposes their hashes, the frozen protocol, validation code, aggregate analysis code, and aggregate results.

Relevant files:

- `docs/second_corpus_c2_secondary_judge_replication_protocol_v1.md`
- `docs/c2_secondary_judge_prompt_gemini_v1.txt`
- `docs/c2_secondary_judge_prompt_claude_v1.txt`
- `scripts/validate_second_corpus_secondary_judgments_v1.py`
- `scripts/second_corpus_secondary_judge_analysis_v1.py`

Publication-safe aggregate result SHA-256 from the local frozen analysis:

- result JSON: `589af8f3ad4fd54abf347215ac2646156541f9ef0f90f60a64b67a59066c5e74`
- result Markdown: `921b8e8eb1cfa052fda1be63ad87e77084c931635874c6b0ff5b45d424bde488`
