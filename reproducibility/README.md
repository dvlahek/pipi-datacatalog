# Reproducing the paper results

This directory is the publication-facing index for **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**.

The full repository contains the data-catalog service, benchmark construction code, historical protocol records, retrieval analyses, and provenance utilities. This directory points to the artifacts needed to check the values reported in the paper without requiring a reader to reconstruct the project history first.

## Corpus conventions

**Corpus A** uses datasets as its sampling units. It contains 274 sampled datasets and 274 unique dataset IDs. There is no separate selection-record layer. The provenance levels used in the paper are dataset, file-aware intermediate identity, and chunk.

**Corpus B** uses selection records as its sampling units. One selection record is one source dataset included in one topical stratum. The design contains 400 selection records but 397 unique dataset IDs because three datasets occur in two strata. Each selection record contributes two retained distributions, giving 800 distributions. The provenance levels are dataset, distribution, and chunk. Selection records are not retrieval-provenance identities.

## Publication artifacts

- [`results/main_results_summary.json`](results/main_results_summary.json) contains the numerical values used to check the main tables and headline results.
- [`results/same_evidence_summary.json`](results/same_evidence_summary.json) records the 306 same-evidence generation controls.
- [`protocols/corpus_b_amendment.md`](protocols/corpus_b_amendment.md) documents the corpus-B sample-size change and its timing.
- [`manifest.json`](manifest.json) lists the compact files kept in this directory.
- [`CITATION.cff`](CITATION.cff) provides citation metadata.

## Main code paths

The analyses use code already present in the repository. The most relevant scripts are:

- `scripts/compare_retrieval_evidence.py`
- `scripts/analyze_retrieval_drift_taxonomy.py`
- `scripts/evaluate_rag_profiles.py`
- `scripts/audit_retrieval_provenance_negative_controls.py`
- `scripts/second_corpus_confirmatory_analysis_v1.py`
- `scripts/second_corpus_reporting_v1.py`
- `scripts/second_corpus_answer_drift_reporting_v2.py`
- `scripts/second_corpus_secondary_judge_analysis_v1.py`

The dated records under `docs/` preserve the protocol and analysis chronology. They include the corpus-A benchmark development, corpus-B confirmation protocol, answer-drift extension, secondary judging protocol, and the amendments made before the corresponding analyses. They are retained as historical research records, so older filenames and terminology are not retroactively rewritten.

## Protocol chronology

For corpus A, the benchmark design was recorded before the confirmation evaluation. A later pre-authoring amendment added open-data catalogs as the fourth source family and rebalanced the query allocation before confirmation-query authoring and retrieval evaluation.

For corpus B, the confirmation protocol was recorded before dataset selection. Corpus-construction feasibility testing later reduced the target from 200 to 100 selection records per topical stratum. That change occurred before query authoring, retrieval evaluation, or inspection of confirmatory outcomes. The amendment is documented in [`protocols/corpus_b_amendment.md`](protocols/corpus_b_amendment.md).

The exact commit identifiers and the longer protocol history remain available in the dated records under `docs/` and in the repository history. They are not required to interpret the main manuscript.

## What can be reproduced from the public branch

The publication branch provides the code and retained artifacts needed to recompute the reported aggregate analyses from the archived experiment outputs, including provenance churn, corpus-B H1/H2 statistics, answer-drift summaries, judge-agreement summaries, and same-evidence controls.

The exact ordered-evidence replay reported in the paper is evaluated against the recorded retrieval/index state. This branch does not claim a clean-room rebuild of every dependency or the complete original runtime environment. The manuscript states the remaining environment-level gaps explicitly.

## Data boundaries

Corpus B is based on openly licensed public distributions and can be reconstructed from stable dataset/distribution identifiers, source URLs, and the documented materialization rules. Corpus A contains source families with different redistribution conditions. When source or chunk text cannot be redistributed, the publication artifacts retain identifiers, hashes, configurations, and aggregate results instead.

Human-validation summaries are pseudonymized. Raw answer/evidence material and any third-party content whose redistribution rights are unclear are not copied into the publication package.