# Reproducibility package

This directory contains the publication-facing material for the paper *Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG*.

The goal is to keep the package small and auditable. The repository already contains the application, benchmark, retrieval-comparison, evaluation, and provenance-audit code. This directory points to the main reproduction targets and stores compact result summaries used to check the values reported in the paper.

## Corpus units

- **Corpus A:** the sampling unit is a dataset. The corpus contains 274 sampled datasets and 274 unique dataset IDs, so there is no separate selection-record layer.
- **Corpus B:** the sampling unit is a selection record, defined as one dataset included in one topical stratum. The design contains 400 selection records but 397 unique dataset IDs because three datasets occur in two strata. Selection records are not retrieval-provenance identities. Corpus-B provenance uses dataset, distribution, and chunk identities. Each selection record contributes two retained distributions, for 800 distributions in total.

## Protocol chronology

The paper reports the scientific chronology without embedding commit identifiers in the main text. The exact repository history is recorded here.

### Corpus A

- Initial Benchmark V2 design: `0a30e0dec255a07d99892cdf30b706132d206f9e` — **Add frozen Benchmark V2 experimental design**.
- Pre-authoring four-family amendment: `1375cee96ecc1f3628d679226e7fcfcd80821f57` — **Amend Benchmark V2 for four source families**. This amendment added open-data catalogs as the fourth source family and rebalanced the development/confirmation allocation before confirmation query authoring and retrieval evaluation.

### Corpus B

- Confirmation protocol V2: `3f1e2adabe12d2697f3a3bf5c66749fc9d097274` — **Freeze second-corpus confirmation protocol V2**. It was recorded before corpus-B dataset selection.
- The later feasibility change reduced the target from 200 to 100 selection records per topical stratum before query authoring, retrieval evaluation, or inspection of confirmatory outcomes. The change is documented in `protocols/corpus_b_amendment.md`.

The protocol files and commit history provide the detailed audit trail. The article keeps only the chronology needed to interpret the study design.

## Main reproduction targets

1. Provenance churn at dataset, intermediate-source, and chunk identity.
2. Sensitivity to representation, embedding-family, and ranking/fusion changes.
3. H1 and H2 statistics in corpus B.
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

`results/main_results_summary.json` contains the headline numerical results reported in the article. `results/same_evidence_summary.json` records the identical-evidence generation controls. The corpus-B sample-size amendment is preserved under `protocols/`.

The artifact map in `manifest.json` identifies the compact publication-facing files. Publication-safe ledgers and pseudonymized human-audit material are included only where redistribution rights and participant privacy allow it. Source payloads that cannot be redistributed remain at their original providers.

## Data boundaries

Corpus B is based on openly licensed public distributions and can be reconstructed from stable dataset/distribution identifiers, source URLs, and the documented materialization rules. Corpus A combines several source families with different redistribution conditions, so the public package uses stable identities and derived hashes where source text cannot be republished.

## Citation

Use the repository citation metadata in `CITATION.cff` for the current submission package.