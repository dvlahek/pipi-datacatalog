# Reproducibility package

This directory contains the publication-facing material for the paper *Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG*.

The goal is to keep the release small and auditable. The repository already contains the application, benchmark, retrieval-comparison, evaluation, and provenance-audit code. This directory points to the main reproduction targets and stores compact result summaries used to check the values reported in the paper.

## Main reproduction targets

1. Provenance churn at dataset, intermediate-source, and chunk identity.
2. Sensitivity to representation, embedding-family, and ranking/fusion changes.
3. H1 and H2 statistics in the independent second corpus.
4. Exact ordered-evidence replay and first-divergence controls.
5. Answer-drift and blinded human-validation summaries.
6. Same-evidence generation controls.

## Main code paths

The relevant implementation already lives in this repository, including:

- `scripts/compare_retrieval_evidence.py`
- `scripts/analyze_retrieval_drift_taxonomy.py`
- `scripts/evaluate_rag_profiles.py`
- `scripts/audit_retrieval_provenance_negative_controls.py`
- `scripts/second_corpus_confirmatory_analysis_v1.py`
- `scripts/second_corpus_reporting_v1.py`
- `scripts/second_corpus_answer_drift_reporting_v2.py`
- `scripts/second_corpus_secondary_judge_analysis_v1.py`

The second-corpus configuration and protocol files are listed in the main repository README and in the paper.

## Result checks

`results/main_results_summary.json` contains the headline numerical results reported in the article. `results/same_evidence_summary.json` records the identical-evidence generation controls. The second-corpus sample-size amendment is preserved under `protocols/`.

Publication-safe ledgers and pseudonymized human-audit data will be attached to the archival paper release where redistribution rights allow it. Source payloads that cannot be redistributed remain at their original providers.

## Archival release

The publication release is intended to be archived on Zenodo. After the DOI is minted, it should be added to `CITATION.cff`, `.zenodo.json`, and the paper's Data and Artifact Availability section.