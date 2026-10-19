# Reproducibility package

This directory contains the publication-facing material for the paper *Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG*.

The goal is to keep the package small and auditable. The repository already contains the application, benchmark, retrieval-comparison, evaluation, and provenance-audit code. This directory points to the main reproduction targets and stores compact result summaries used to check the values reported in the paper.

## Main reproduction targets

1. Provenance churn at dataset, intermediate-source, and chunk identity.
2. Sensitivity to representation, embedding-family, and ranking/fusion changes.
3. H1 and H2 statistics in the independently constructed second corpus.
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

## Result checks

`results/main_results_summary.json` contains the headline numerical results reported in the article. `results/same_evidence_summary.json` records the identical-evidence generation controls. The second-corpus sample-size amendment is preserved under `protocols/`.

The artifact map in `manifest.json` identifies the compact publication-facing files. Publication-safe ledgers and pseudonymized human-audit material are included only where redistribution rights and participant privacy allow it. Source payloads that cannot be redistributed remain at their original providers.

## Data boundaries

The second corpus is based on openly licensed public distributions and can be reconstructed from stable dataset/distribution identifiers, source URLs, and the documented materialization rules. The heterogeneous corpus combines several source families with different redistribution conditions, so the public package uses stable identities and derived hashes where source text cannot be republished.

## Citation

Use the repository citation metadata in `CITATION.cff` for the current submission package.