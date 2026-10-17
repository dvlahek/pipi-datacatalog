# PiPi Benchmark V2 — reproducibility record

This document records the frozen identifiers and public result artifacts used for the PiPi Benchmark V2 retrieval-provenance study.

## Frozen parent state

- catalog snapshot SHA-256: `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- corpus fingerprint SHA-256: `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- 192-query confirmation-set SHA-256: `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`
- original frozen confirmation qrels SHA-256: `a0946546b7b0109bfc8f0920b7cd8de6412c210cbe26ffb36f155f4a0a5637ad`
- original retrieval protocol SHA-256: `d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde`

The confirmation protocol was pre-specified and frozen before confirmation evaluation. No external preregistration registry was used, so public documentation should not describe this protocol as preregistered.

## Frozen E5 retrieval profiles

- `lexical-v1`: `4234a9a6691d7f0c004eb7b6469662675db35f66fe04dd8eb5b053b1d7a31a54`
- `vector-e5-content-v1`: `8c00e6326839a8e0e798083197225d1fd90b60db7d6a9e974fe8667de5f0562f`
- `hybrid-e5-content-v1`: `04fd11fb3c56e9273f7b312a376d5c975a852489276f87fc796f7e0c716f7a45`
- `vector-e5-metadata-v1`: `e250344e567f85c3dc8ac36b0cd68663f570e322bed7686de99a270ffa0e1628`
- `hybrid-e5-metadata-v1`: `7b63711593b091d1c21a1548f1b672f4572c69b4fca380779114cad6163211e4`

The built-in profiles are immutable by profile ID. Reusing an existing ID with a different configuration hash is treated as an error.

## Primary retrieval results

Overall nDCG@10:

- lexical: 0.4891
- vector E5 content: 0.7013
- hybrid E5 content: 0.6712
- vector E5 metadata: 0.7759
- hybrid E5 metadata: 0.6996

Pre-specified frozen hybrid metadata-minus-content contrast:

- mean ΔnDCG@10: +0.0284
- 95% paired-bootstrap CI: [0.0134, 0.0441]
- Wilcoxon p: 0.000967
- rank-biserial: 0.369

Vector metadata-minus-content contrast:

- mean ΔnDCG@10: +0.0745
- 95% CI: [0.0429, 0.1087]
- Wilcoxon p: 1.20e-05
- rank-biserial: 0.451

## Retrieval drift and replay

For the frozen hybrid content-versus-metadata intervention:

- chunk retention@10: 0.7698
- chunk churn@10: 0.2302
- chunk Jaccard@10: 0.6550
- top-1 chunk change rate: 0.2604
- source churn: 0.1037
- source Jaccard: 0.8383
- relevant-evidence retention for grades 2/3: 0.9584

Strict replay reproduced the exact ordered evidence set for 960/960 frozen runs, corresponding to 192 queries under five frozen retrieval profiles.

Because exact deterministic replay is expected when all frozen inputs match, a separate post-hoc negative-control audit checks the provenance gates themselves:

- same profile ID with RRF `k` changed from 60 to 61
- same profile ID with a changed embedding revision
- changed chunk boundaries in a publication-safe fixture hashed with the same chunk-manifest fields as the frozen corpus
- foreign catalog-snapshot and corpus-fingerprint anchors

These controls are implemented in `scripts/audit_retrieval_provenance_negative_controls.py` and tested by `tests/test_retrieval_provenance_negative_controls.py`. They are systems validation and do not alter the frozen RQ1–RQ4 results.

## Primary relevance judging

The frozen candidate pool contained 9,170 query-candidate pairs. Pass 1 used a blinded deterministic criteria-assisted OpenAI GPT-5.6 Sol judgment pass. A fresh-context replicate pass was run independently on a stratified 48-query subset containing 2,252 pairs.

Agreement on the replicate subset:

- exact agreement: 0.7886
- within-one-grade agreement: 0.9307
- quadratic weighted kappa: 0.6482

The final qrels were frozen and hashed before retrieval-quality metrics were computed.

## RQ3 answer-drift protocol

The answer-drift protocol was frozen before benchmark answer generation. It used:

- Qwen3-8B Q4_K_M as the primary generator
- Ministral-3-8B-Instruct Q4_K_M as replication
- Gemma-3-4B-it Q4_K_M as replication
- local llama.cpp OpenAI-compatible server
- temperature 0
- top-p 1
- seed 20261014
- max 384 tokens
- context size 16,384
- grounded-only prompt with no retrieval-profile identity exposed to the generator

Changing only the frozen hybrid retrieval profile produced material semantic answer differences in 10.4–11.5% of confirmation queries across the three generator families. Same-evidence deterministic controls were exact in 144/144 runs.

The semantic-drift endpoint is symmetric. It establishes material difference, not that one answer is more correct or better grounded.

## BGE-M3 second-backbone robustness

BGE-M3 is a post-hoc robustness analysis. It does not replace or relabel the frozen E5 confirmation experiment.

- model: `BAAI/bge-m3`
- revision: `5617a9f61b028005a4858fdac845db406aefb181`
- dense component only
- 1024 dimensions
- exact cosine retrieval
- same 192 frozen confirmation queries and corpus

BGE-M3 produced 1,090 novel top-10 query-candidate pairs outside the original E5 judged pool. These were judged in a separate blinded supplementary process. Initial S1/S2 agreement was 42.3% exact, 77.3% within one grade, with quadratic weighted kappa 0.156. Every one of the 629 disagreements then received fresh blinded third-pass adjudication. Final BGE top-10 qrels coverage was 7,680/7,680 slots.

Final BGE-M3 contrasts:

- vector metadata-minus-content ΔnDCG@10 = +0.0937, 95% CI [0.0678, 0.1209]
- hybrid metadata-minus-content ΔnDCG@10 = +0.0349, 95% CI [0.0217, 0.0484]

The original E5 qrels remain unchanged.

## Public reproducibility boundary

The repository can publish profile configurations, query definitions, hashes, qrels, publication-safe retrieval ledgers, judging manifests, aggregate results, and replay/audit code. Source or chunk text is not automatically redistributable. Institutional documents, sensor data, and third-party content remain subject to their original access and licensing conditions.

The open-data cohort is frozen by identity for the benchmark. A future fresh upstream “first 200” harvest is not assumed to reproduce the same cohort if the provider changes result ordering.
