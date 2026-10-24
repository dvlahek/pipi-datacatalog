# Historical research records

The files in this directory record how the PiPi retrieval experiments were developed, amended, frozen, and checked over time.

They are retained for protocol chronology. They are **not** the publication package and should not be read as additional claims of the final manuscript. Some files contain intermediate analyses, superseded targets, older terminology, or implementation notes that were later narrowed or replaced.

For the paper **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**, use [`../reproducibility/README.md`](../reproducibility/README.md) as the publication-facing index and the manuscript as the authoritative statement of the final methods, results, and limitations.

The historical records remain here because the manuscript reports that protocol changes were documented before the corresponding analyses. Their purpose is chronology, not to provide a second narrative of the paper.

In particular:

- `retrieval_benchmark_v2_protocol.md` and `retrieval_benchmark_v2_amendment_*.md` record the corpus-A benchmark protocol history;
- `rq3_answer_drift_protocol_frozen_20261014.md` and its amendment record the corpus-A answer-drift boundary;
- `second_corpus_confirmation_protocol_v2.md` and the dated pre-result amendments record the corpus-B construction and confirmation history;
- `second_corpus_*answer_drift*` and `second_corpus_*judge*` files record later answer-drift and judging analyses;
- provider-specific judge prompt files are experimental instructions used in those analyses, not manuscript-writing prompts.

Development summaries, deployment notes, old protocol versions, and superseded construction records are retained only as project history. Final article values should be checked against `../reproducibility/results/main_results_summary.json` and the manuscript.
