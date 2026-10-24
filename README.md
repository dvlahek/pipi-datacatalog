# PiPi data catalog and retrieval-provenance experiments

This repository contains the semantic data-catalog implementation and the experimental material used in the paper **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**.

The paper studies a simple reproducibility problem: two retrieval executions can refer to the same source dataset while supplying different evidence to a downstream generator. The experiments therefore compare retrieval change at dataset, intermediate-source, and chunk identity, and record enough execution state to replay the ordered evidence.

This branch (`paper/fgcs-reproducibility`) is the publication branch used by the manuscript. Development code lives in the same repository, but the paper-facing entry point is [`reproducibility/README.md`](reproducibility/README.md).

## Corpus overview

**Corpus A** samples datasets directly. It contains 274 sampled datasets, 274 unique dataset identifiers, 3,974 chunk occurrences, and 192 confirmation queries. Its evidence hierarchy is dataset → file-aware intermediate identity → chunk.

**Corpus B** samples selection records, where one selection record is one source dataset included in one topical stratum. The 400 selection records correspond to 397 unique dataset identifiers because three datasets occur in two strata. Each selection record contributes two retained distributions, for 800 distributions in total. Before exact cross-stratum deduplication the retained material contains 44,520 chunk occurrences; retrieval uses 44,491 distinct rows after exact duplicate fine-grained chunk identities are represented once. Corpus B contains 96 queries and uses the hierarchy dataset → distribution → chunk.

A selection record is a sampling unit only. It is not a retrieval-provenance identity.

## Results represented in this branch

The publication artifacts reproduce the numerical summaries reported in the manuscript, including:

- corpus-A mean top-10 churn of 10.37% at dataset identity, 17.56% at file-aware identity, and 23.02% at chunk identity;
- corpus-B mean top-10 churn of 20.89% at dataset identity, 24.07% at distribution identity, and 39.38% at chunk identity;
- 82.8% of the mean corpus-B dataset-to-chunk gap remaining below distribution identity;
- dataset-level mean churn equal to 41–53% of chunk-level mean churn across six controlled retrieval changes;
- exact ordered-evidence replay for 1,152/1,152 recorded retrieval runs;
- exact same-evidence generation repeats for 306/306 controls;
- material answer drift of 10.4–11.5% across three local generators in corpus A and 31/81 in the context-feasible corpus-B subset.

The compact machine-readable summary is in [`reproducibility/results/main_results_summary.json`](reproducibility/results/main_results_summary.json).

## Main analysis code

The paper uses the existing project implementation together with analysis scripts in `scripts/`. The main entry points are:

- `scripts/compare_retrieval_evidence.py` — compares evidence identities between recorded executions;
- `scripts/analyze_retrieval_drift_taxonomy.py` — summarizes drift by provenance level;
- `scripts/evaluate_rag_profiles.py` — computes corpus-A retrieval metrics;
- `scripts/audit_retrieval_provenance_negative_controls.py` — checks one-at-a-time provenance mutations;
- `scripts/second_corpus_confirmatory_analysis_v1.py` — computes the corpus-B confirmation statistics;
- `scripts/second_corpus_reporting_v1.py` — produces the corpus-B reporting summaries;
- `scripts/second_corpus_answer_drift_reporting_v2.py` — recomputes publication-safe answer-drift summaries;
- `scripts/second_corpus_secondary_judge_analysis_v1.py` — recomputes the multi-judge sensitivity results.

Historical protocol records and dated analysis notes are kept under `docs/`. They are useful for tracing the order in which the benchmark and confirmation analyses were defined, but [`reproducibility/README.md`](reproducibility/README.md) is the shorter guide for reproducing the paper results.

## Data and redistribution

Corpus B is based on openly licensed public distributions and is represented by stable dataset/distribution identifiers, source URLs, and documented materialization rules. Corpus A combines source families with different redistribution conditions. Where source text cannot be republished, the public artifacts retain stable identities, hashes, configurations, and aggregate results instead of copying the original content.

The repository does not claim a clean-room reconstruction of every software dependency used in the experiments. The replay results in the paper are against the recorded index and execution state; the manuscript lists the remaining environment-level limitations explicitly.

## Citation

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).