# PiPi retrieval-provenance reproducibility package

This branch supports the paper **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**.

The paper studies how retrieval stability changes when the same execution is compared at dataset, intermediate-source, and chunk identity. It also tests whether evidence changes hidden by coarse source identity propagate to generated answers and whether the recorded retrieval execution can be replayed exactly.

## Headline results

- Corpus A: mean top-10 churn is 10.37% at dataset identity, 17.56% at file-aware identity, and 23.02% at chunk identity.
- Corpus B: mean top-10 churn is 20.89% at dataset identity, 24.07% at distribution identity, and 39.38% at chunk identity.
- In corpus B, 82.8% of the mean dataset-to-chunk gap remains below distribution identity.
- Across six controlled retrieval changes, dataset-level mean churn is 41-53% as large as chunk-level mean churn.
- Exact ordered-evidence replay succeeds for 1,152/1,152 recorded retrieval runs.
- Same-evidence generation repeats are exact for 306/306 controls.
- Material answer drift is 10.4-11.5% across three local generators in corpus A and 31/81 in the context-feasible corpus-B subset.

## Reproducibility material

Start with [`reproducibility/README.md`](reproducibility/README.md).

The publication-facing directory contains compact result summaries, protocol documentation, citation metadata, and an artifact map. The implementation and analysis scripts remain in their original repository locations and are linked from the reproducibility guide.

Key code paths include:

- `scripts/compare_retrieval_evidence.py`
- `scripts/analyze_retrieval_drift_taxonomy.py`
- `scripts/evaluate_rag_profiles.py`
- `scripts/audit_retrieval_provenance_negative_controls.py`
- `scripts/second_corpus_confirmatory_analysis_v1.py`
- `scripts/second_corpus_reporting_v1.py`
- `scripts/second_corpus_answer_drift_reporting_v2.py`
- `scripts/second_corpus_secondary_judge_analysis_v1.py`

## Data boundaries

The second corpus is based on openly licensed public distributions and can be represented through stable dataset/distribution identifiers, source URLs, and materialization instructions. Material from the heterogeneous corpus is redistributed only where its original access conditions and licences permit it. Publication-safe ledgers use stable identities and derived hashes rather than copying restricted evidence text.

## Citation

Repository citation metadata are provided in `CITATION.cff`. A separate archival DOI is not required for the current submission package.