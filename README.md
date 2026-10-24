# PiPi data catalog and retrieval-provenance experiments

This repository contains the PiPi semantic data-catalog implementation and the experimental code used in the paper **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**.

The paper studies a reproducibility problem: two retrieval executions can refer to the same source dataset while supplying different evidence to a downstream generator. The experiments therefore compare change at dataset, intermediate-source, and chunk identity and record the execution state needed to identify the ordered evidence.

## Paper materials

The compact paper-facing package is [`reproducibility/`](reproducibility/). Start there if you are checking the manuscript.

The rest of this repository is the broader PiPi implementation and research history. It is retained because the experiments were run on the project system, but it is not an additional set of paper claims. In particular, dated files under `docs/` and `history/` may contain intermediate analyses, older terminology, or superseded protocol versions.

## Corpus overview

**Corpus A** samples datasets directly. It contains 274 sampled datasets, 274 unique dataset identifiers, 3,974 chunk occurrences, and 192 confirmation queries. Its evidence hierarchy is dataset → file-aware intermediate identity → chunk.

**Corpus B** samples selection records, where one selection record is one source dataset included in one topical stratum. The 400 selection records correspond to 397 unique dataset identifiers because three datasets occur in two strata. Each selection record contributes two retained distributions, for 800 distributions in total. Before exact cross-stratum deduplication the retained material contains 44,520 chunk occurrences; retrieval uses 44,491 distinct rows after exact duplicate fine-grained chunk identities are represented once. Corpus B contains 96 queries and uses the hierarchy dataset → distribution → chunk.

A selection record is a sampling unit only. It is not a retrieval-provenance identity.

## Headline results represented in the publication package

- corpus-A mean top-10 churn: 10.37% at dataset identity, 17.56% at file-aware identity, and 23.02% at chunk identity;
- corpus-B mean top-10 churn: 20.89% at dataset identity, 24.07% at distribution identity, and 39.38% at chunk identity;
- 82.8% of the mean corpus-B dataset-to-chunk gap remains below distribution identity;
- dataset-level mean churn is 41–53% of chunk-level mean churn across six controlled retrieval changes;
- exact ordered-evidence replay for 1,152/1,152 recorded retrieval runs;
- exact same-evidence generation repeats for 306/306 controls;
- material answer drift of 10.4–11.5% across the three corpus-A generators and 31/81 in the context-feasible corpus-B subset.

The machine-readable summary is [`reproducibility/results/main_results_summary.json`](reproducibility/results/main_results_summary.json). The compact verifier is [`reproducibility/verify_reported_results.py`](reproducibility/verify_reported_results.py). The published frozen replay artifacts are under [`reproducibility/replay/`](reproducibility/replay/).

## Reproducibility boundary

The publication package verifies the retained numerical summaries and denominators and now exposes the frozen per-run retrieval ledgers and replay-audit artifacts used for the reported exact ordered-evidence replay endpoint. The replay files contain ordered retrieval identities, ranks, provenance identifiers, configuration hashes, and content hashes without redistributing the underlying evidence text.

The replay endpoint in the paper is exact ordered-evidence replay against the recorded retrieval/index state. The public package supports inspection and cryptographic verification of that recorded replay chain for all 1,152 runs. It does not claim that cloning this branch alone reconstructs the complete original runtime or reruns every retrieval, judging, and generation experiment from all original inputs.

The full 192-query corpus-A confirmation JSON and selected original runtime/index-construction inputs are not redistributed in the compact publication package. Source/chunk text and raw answer/evidence material are also omitted where redistribution rights or privacy do not permit publication. The manuscript documents these remaining clean-room reconstruction limits.

## Code

The application and experiment code remain available in `app/`, `scripts/`, `config/`, `database/`, and `tests/`. These directories are the broader project implementation, not the minimal paper package.

## Citation

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).
