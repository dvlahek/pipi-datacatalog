# Independent second-corpus confirmation — results record

**Status:** frozen confirmatory retrieval analysis plus reporting-only derivatives  
**Date:** 2026-10-18  
**Corpus:** data.europa.eu public distributions  
**Role in the paper:** independent balanced confirmation of the provenance-granularity effect observed in C1

## Scope

C2 was designed to separate the provenance-granularity result from the naturally heterogeneous composition of the original benchmark corpus. The original target of 200 datasets per theme was reduced to 100 per theme before query generation, retrieval evaluation, answer generation, or confirmatory statistical testing. All eligibility, ordering, distribution, chunking, retrieval, and H1/H2/H3 rules remained unchanged.

The final corpus contains:

- 400 theme-stratum records, 100 each for ECON, ENVI, HEAL and TRAN
- 397 unique dataset IDs
- 800 retained distributions
- 44,520 physical chunk rows
- 44,491 logical chunk rows after collapsing exact cross-theme fine-identity duplicates once
- 96 frozen queries: 4 themes × 6 query types × 4 replicates

The primary intervention is unchanged from C1:

- `hybrid-e5-content-v1`
- `hybrid-e5-metadata-v1`
- top-k = 10
- multilingual E5 small, normalized embeddings
- lexical + vector RRF with k = 60
- candidate depth 50
- soft source cap 2

C2 adds an explicit distribution identity between dataset and chunk identity because each selected dataset contributes two retained distributions.

## Confirmatory results

| Endpoint | Result | Status |
|---|---:|---|
| H1 mean chunk churn@10 | 39.38% | expected direction observed |
| H1 mean dataset churn@10 | 20.89% | — |
| H1 mean paired gap | +18.48 pp | supported |
| H1 median paired gap | +20.00 pp | supported |
| H1 Wilcoxon, Holm-adjusted p | 1.075 × 10^-13 | supported |
| H1 paired rank-biserial | 0.928 | large paired effect |
| H2 Spearman rho | +0.155 | expected direction observed |
| H2 Holm-adjusted p | 0.131 | not statistically supported |
| H3 exact ordered-evidence replay | 192/192 | passed |

H1 produced 81 positive, 6 negative and 9 zero paired differences across 96 queries. The granularity ordering therefore reproduced strongly in the independent corpus.

H2 was directionally consistent with the frozen multiplicity hypothesis but did not reach the pre-specified Holm-adjusted significance threshold. It is reported as not confirmed. No alternative multiplicity variable is substituted post hoc.

H3 reproduced every frozen ordered evidence list exactly.

## Three-level provenance view

The descriptive C2 results show a clear identity hierarchy:

| Identity level | Mean churn@10 | Mean Jaccard@10 | Top-1 change rate |
|---|---:|---:|---:|
| Dataset | 20.89% | 0.6243 | 34.38% |
| Distribution | 24.07% | 0.6023 | 43.75% |
| Chunk | 39.38% | 0.4586 | 56.25% |

In 27/96 queries (28.1%), the dataset set remained fully stable while the chunk set changed. This is the central operational interpretation of the granularity result: coarse provenance can remain unchanged while the specific evidence supplied downstream changes.

## Domain consistency

The effect is not driven by one theme.

| Theme | Mean chunk churn@10 | Mean dataset churn@10 | Mean chunk-dataset gap |
|---|---:|---:|---:|
| ECON | 38.75% | 18.21% | +20.54 pp |
| ENVI | 36.67% | 20.45% | +16.22 pp |
| HEAL | 40.83% | 24.98% | +15.85 pp |
| TRAN | 41.25% | 19.93% | +21.32 pp |

All four themes retain the same qualitative ordering: chunk churn exceeds dataset churn.

## Query-type description

Mean chunk churn ranged from 33.75% for constraint-filtered lookup to 48.13% for relation/comparison queries. The largest mean chunk-minus-dataset gaps occurred for semantic paraphrase (+24.06 pp) and entity/dataset lookup (+24.03 pp). These subgroup values are descriptive only.

## C1–C2 comparison

| Metric | C1 | C2 |
|---|---:|---:|
| Chunk churn@10 | 23.02% | 39.38% |
| Dataset churn@10 | 10.37% | 20.89% |
| Chunk-dataset churn gap | 12.65 pp | 18.48 pp |
| Chunk Jaccard@10 | 0.6550 | 0.4586 |
| Dataset Jaccard@10 | 0.8383 | 0.6243 |
| Top-1 chunk change | 26.04% | 56.25% |
| Exact ordered-evidence replay | 960/960 | 192/192 |

C1 and C2 differ in corpus construction and evidence content. Differences in magnitude are descriptive. The confirmatory C2 claim is replication of the granularity ordering, not equality or formal cross-corpus comparison of effect sizes.

## Reproducibility anchors

Key frozen identifiers:

- corpus freeze SHA-256: `d3fa4e2007e348ace37e6a8666c4562bcdc3cf80c1b96b821c06ef5641581be0`
- query SHA-256: `4257116b4d9ec417217b2030df58b5de3ba479fe0125f021a3ca50b7022699f7`
- retrieval input freeze SHA-256: `8ba8756b8896086ba52116d8ee0f849faecf65ada55c6cd84e5dbd64a133a1e1`
- embedding manifest SHA-256: `0abdf9adb0c3ea0e43d1ea54ab563798b6b33c6126d240656fe8617c0fb32b76`
- primary retrieval runs SHA-256: `5138ae7d90906709b1b5f8792560c8ddde95b57a01614cafbc951e7542294383`
- confirmation freeze SHA-256: `e7bbe1bfd048103de047a816ebd48ae359a5a74b38f2462463e1a9be752ff841`
- reporting freeze SHA-256: `8be141a77806bddc1cc1c90c1b269cce8dae6f7d2238775d0f6b7a4b5d5e6bb1`

Relevant source-controlled records:

- `docs/second_corpus_confirmation_protocol_v2.md`
- `config/second_corpus_target100_amendment_v2_7.json`
- `docs/second_corpus_v2_preretrieval_adapter_10_distribution_identity.md`
- `config/second_corpus_retrieval_v1.json`
- `scripts/second_corpus_run_retrieval_v1.py`
- `scripts/second_corpus_confirmatory_analysis_v1.py`
- `scripts/second_corpus_reporting_v1.py`

Generated corpus payloads, embedding shards, third-party text and answer artifacts are not treated as repository source code. Publication should expose hashes, manifests, aggregate results and replay/audit code without assuming redistribution rights for third-party source material.

## Answer-drift extension

A Qwen3-8B answer-drift extension is defined separately as a post-confirmatory descriptive analysis. It is frozen under the original C1 grounded prompt and decoding settings but is not a C2 confirmatory endpoint.

See:

- `docs/second_corpus_c2_answer_drift_extension_v1.md`
- `config/second_corpus_answer_drift_qwen_v1.json`
- `scripts/second_corpus_prepare_answer_drift_v1.py`
- `scripts/second_corpus_run_answer_drift_qwen_v1.py`

Any answer-level result from this extension must remain explicitly secondary/descriptive.
