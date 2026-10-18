# PiPi Benchmark V2 — BGE-M3 second-backbone robustness

This analysis is **post-hoc robustness evidence**. It does not modify, replace, or relabel the pre-specified frozen E5 confirmation experiment.

The robustness question is narrow: does the direction of the content-versus-metadata retrieval-profile effect persist under a second multilingual embedding family?

## Frozen parent

- catalog snapshot: `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- corpus fingerprint: `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- confirmation queries: 192
- confirmation-query SHA-256: `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`
- original frozen E5 qrels remain unchanged

## BGE-M3 configuration

- model: `BAAI/bge-m3`
- pinned revision: `5617a9f61b028005a4858fdac845db406aefb181`
- dense component only
- dimensions: 1024
- normalized embeddings
- no query instruction
- max sequence length: 512
- exact pgvector cosine retrieval
- hybrid RRF `k=60`
- source/file soft cap: 2

## Supplementary qrels coverage

BGE-M3 produced 1,090 unique novel top-10 query-candidate pairs outside the original frozen E5 judged pool. They were not treated as non-relevant.

Two independent blinded supplementary passes were compared first. Exact S1/S2 agreement was 42.3%, within-one-grade agreement was 77.3%, and quadratic weighted kappa was 0.156. Because agreement was low, every one of the 629 disagreements received a fresh blinded third-pass adjudication. Final supplementary labels therefore consist of 461 S1/S2 consensus labels and 629 adjudicated labels.

After this extension, BGE-M3 top-10 qrels coverage was 7,680/7,680 slots. These supplementary labels are used only for the BGE-M3 robustness analysis.

## Overall retrieval quality

| Profile | nDCG@10 | MRR@10 | Recall@10 | Hit@1 | Hit@3 | Hit@10 |
|---|---:|---:|---:|---:|---:|---:|
| vector BGE-M3 content | 0.7393 | 0.8861 | 0.6872 | 0.8333 | 0.9375 | 0.9688 |
| vector BGE-M3 metadata | 0.8330 | 0.9345 | 0.7785 | 0.9010 | 0.9583 | 0.9896 |
| hybrid BGE-M3 content | 0.6686 | 0.8202 | 0.6567 | 0.7292 | 0.8854 | 0.9688 |
| hybrid BGE-M3 metadata | 0.7035 | 0.8501 | 0.6933 | 0.7708 | 0.9115 | 0.9792 |

## Metadata minus content

Vector BGE-M3:
- mean ΔnDCG@10 = 0.093699
- 95% bootstrap CI = [0.067815, 0.120893]
- Wilcoxon p = 1.468e-10
- rank-biserial = 0.6199
- positive / negative / ties = 99 / 43 / 50

Hybrid BGE-M3:
- mean ΔnDCG@10 = 0.034890
- 95% bootstrap CI = [0.021656, 0.048405]
- Wilcoxon p = 1.405e-07
- rank-biserial = 0.5632
- positive / negative / ties = 85 / 31 / 76

## Interpretation

The metadata-sensitive retrieval effect retained the same positive direction under a second multilingual embedding family.

- Frozen E5 vector metadata−content ΔnDCG@10 = 0.074541
- BGE-M3 vector metadata−content ΔnDCG@10 = 0.093699
- Frozen E5 hybrid metadata−content ΔnDCG@10 = 0.028359
- BGE-M3 hybrid metadata−content ΔnDCG@10 = 0.034890

The content-versus-metadata comparison is used as a realistic controlled retrieval-profile intervention. The main provenance result is not the metadata gain itself. The central observation is that source-level stability can hide larger chunk-level evidence drift, and that part of this evidence drift propagates into downstream answers.

This robustness result supports a limited claim: the positive representation effect observed in the frozen E5 experiment is not confined to the original E5 embedding family on this benchmark. It does not establish embedding-model independence, and it does not remove the single-corpus limitation.
