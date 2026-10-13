# PiPi Benchmark V2 — development results under Protocol Amendment 3

**Status:** development diagnostic only. These results are not confirmatory evidence.

## Judgment provenance

- Development queries: **48**
- Judged query–evidence pairs: **2314**
- Grade counts: **0=1918, 1=194, 2=121, 3=81**
- Judge: **OpenAI GPT-5.6 Sol**, blinded from retrieval profile, rank, score, authoring-seed status, frozen target IDs/chunk hints, and retrieval ordering.
- Operational procedure: case-specific semantic criteria were formalized from each frozen information need and applied consistently to candidate source identity/file path and evidence text.
- Judgment artifact SHA-256: `dc5cb32392c5c5fd29dbcbdffedbf1fd9735ec9867a8bfdf3d66ac686dcf41ac`
- Qrels TSV SHA-256: `b209215c127b5a4719ca9d84071d50e275c011c047ae6beda0f2f78c67bc0c33`
- Input A2 pool SHA-256: `6c1b72beb3ce64c0e2aa61f97bf64abfd17fc5ca83a5213c414e16e6b8894ad0`

The full judgment artifact and qrels are retained as reproducibility artifacts. This repository snapshot records their hashes together with the publication-safe aggregate results below.

## Overall retrieval quality

| Profile | nDCG@10 | MRR | Recall@10 | Hit@1 | Hit@3 | Hit@10 |
|---|---:|---:|---:|---:|---:|---:|
| `lexical-v1` | 0.3917 | 0.4242 | 0.4200 | 0.3750 | 0.4375 | 0.5625 |
| `vector-e5-content-v1` | 0.6736 | 0.7723 | 0.6817 | 0.7292 | 0.7917 | 0.8958 |
| `hybrid-e5-content-v1` | 0.5907 | 0.6461 | 0.6433 | 0.5208 | 0.7292 | 0.8125 |
| `vector-e5-metadata-v1` | 0.7249 | 0.8134 | 0.7200 | 0.7708 | 0.8542 | 0.8750 |
| `hybrid-e5-metadata-v1` | 0.6087 | 0.6630 | 0.6543 | 0.5625 | 0.7292 | 0.8333 |

`nDCG@10` uses graded relevance (gain `2^rel−1`). MRR, Recall and Hit metrics use grades 2–3 as relevant.

## Preregistered primary contrast

`hybrid-e5-content-v1` → `hybrid-e5-metadata-v1`: **0.5907 → 0.6087**, mean Δ **+0.0180**.
Paired bootstrap 95% CI for mean Δ: **[-0.0110, +0.0508]**. Wilcoxon p = **0.2691**, paired rank-biserial = **+0.243**. Query signs: 15 positive, 12 negative, 21 ties.

This is a modest development advantage for the metadata hybrid profile, but the interval crosses zero. It is not a confirmatory claim.

## Secondary development contrasts

| Contrast | Δ nDCG@10 | 95% bootstrap CI | Wilcoxon p | Holm p | Rank-biserial |
|---|---:|---:|---:|---:|---:|
| `vector-e5-content-v1` → `vector-e5-metadata-v1` | +0.0512 | [+0.0075, +0.0982] | 0.02567 | 0.02567 | +0.439 |
| `lexical-v1` → `hybrid-e5-content-v1` | +0.1990 | [+0.1065, +0.2945] | 8.804e-05 | 0.0001761 | +0.721 |
| `lexical-v1` → `hybrid-e5-metadata-v1` | +0.2170 | [+0.1283, +0.3107] | 2.687e-05 | 8.062e-05 | +0.781 |

The strongest development result is the general advantage of the hybrid profiles over the lexical baseline. Among the two vector profiles, metadata-v1 is also better on this development set. Existing frozen profile definitions should **not** be modified in response to these development outcomes.

## Primary evidence drift

- Chunk retention@10: **0.765**
- Chunk churn@10: **0.235**
- Chunk Jaccard@10: **0.647**
- Top-1 chunk change rate: **0.208**
- Mean absolute rank shift on shared chunks: **1.471**
- Source retention@10: **0.846**
- Source churn@10: **0.154**
- Source Jaccard@10: **0.795**
- Top-1 source change rate: **0.125**
- Relevant-evidence retention for grades 2–3: **0.936** across 39 queries where the content hybrid retrieved at least one relevant item.
- Relevant-evidence Jaccard for grades 2–3: **0.874**.

The important development pattern is that raw chunk membership changes substantially more than judged relevant evidence. Retrieval provenance therefore captures changes that ordinary relevance metrics can hide.

## Drift–quality association

Spearman correlation between chunk churn@10 and absolute per-query nDCG@10 change: ρ = **+0.240**, p = **0.101**.

This is only a weak development tendency at n=48.

## Exploratory primary-contrast subgroups

### Source family

| Family | n | content hybrid | metadata hybrid | Δ |
|---|---:|---:|---:|---:|
| institutional-documents | 12 | 0.4506 | 0.5494 | +0.0988 |
| open-data-catalogs | 12 | 0.6569 | 0.6472 | -0.0097 |
| software-documentation | 12 | 0.4124 | 0.3956 | -0.0168 |
| structured-data | 12 | 0.8430 | 0.8427 | -0.0003 |

The overall primary development gain is concentrated in **institutional documents**. Structured data is essentially unchanged, while software documentation and open-data catalogs are slightly negative.

### Query type

| Query type | content hybrid | metadata hybrid | Δ |
|---|---:|---:|---:|
| constraint-filtered-lookup | 0.7438 | 0.7270 | -0.0169 |
| entity-document-lookup | 0.4934 | 0.4792 | -0.0142 |
| exact-lookup | 0.6328 | 0.6715 | +0.0387 |
| relation-comparison | 0.6498 | 0.7428 | +0.0930 |
| semantic-paraphrase | 0.6226 | 0.6341 | +0.0115 |
| topic-discovery | 0.4019 | 0.3976 | -0.0043 |

### Language relation

| Relation | content hybrid | metadata hybrid | Δ |
|---|---:|---:|---:|
| cross-language | 0.4887 | 0.4858 | -0.0029 |
| same-language | 0.6928 | 0.7316 | +0.0388 |

All subgroup findings are exploratory development diagnostics.

## Decision before confirmation

1. Keep all five frozen retrieval profiles unchanged; do not tune RRF, diversity caps, embedding representation, or profile parameters from these results.
2. Finalize the confirmation judging procedure **before** confirmation query authoring and retrieval. If an LLM judge is used there too, record that prospectively.
3. Keep the exact LLM-judge provenance in the reproducibility material. The manuscript need not identify a human annotator, but it must not describe these qrels as human judgments.
4. Resolve the remaining fresh-reharvest reproducibility issue for the open-data cohort before making a from-scratch regeneration claim; the frozen current corpus itself remains exactly identified.
