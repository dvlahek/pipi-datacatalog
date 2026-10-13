# PiPi Retrieval Benchmark V2 — Protocol Amendment 3

Status: **adopted before any development relevance grades were assigned and before confirmation query authoring or confirmation retrieval**

This amendment changes the **development relevance-judgment procedure only**. It does not alter the frozen corpus, development queries, retrieval profiles, retrieval ranks, pooling depth, authoring-seed rule, metrics, or confirmation allocation.

## Reason for the amendment

The frozen development annotation pool contains 2314 distinct query–evidence pairs after Protocol Amendment 2. No relevance grade had been assigned when this amendment was adopted.

The original protocol specified one human graded-relevance judgment for each pooled candidate. For the development split, the project now uses a blinded LLM judge instead. The development split is explicitly non-confirmatory and is used to validate the benchmark workflow, inspect retrieval-quality behavior, and identify protocol or implementation problems before confirmation authoring.

This change is recorded before grading so that the provenance of the resulting development qrels is explicit rather than retroactively described.

## Development judge

Development candidates are graded by **OpenAI GPT-5.6 Sol** using the frozen four-level relevance scale.

The judge receives only:

- frozen query text
- frozen information-need description
- source identity needed to interpret the candidate
- source/file path when applicable
- candidate evidence text

The judge does not receive:

- retrieval-profile identity
- retrieval rank or score
- lexical/vector component ranks
- authoring-seed status
- frozen target identifiers or chunk hints
- aggregate retrieval-quality results while grading

Candidate order is independent of retrieval rank.

## Relevance scale

- **3 — directly relevant:** directly answers the information need or contains decisive evidence needed for the answer
- **2 — supporting relevant:** clearly contributes useful evidence but is incomplete on its own
- **1 — weakly/topically related:** related to the topic or entity but insufficient for the information need
- **0 — irrelevant:** does not provide useful evidence for the information need

For relation-comparison queries, a chunk that clearly supports one side of the comparison may receive grade 2. Grade 3 is reserved for evidence that directly satisfies the information need on its own.

## Development-only use

All quality estimates computed from these grades are **development diagnostics**, not confirmatory statistical evidence.

The judge provenance must be retained in the development judgment artifact, including model label, grading protocol hash, input-pool hash, development-query-set hash, and export timestamp.

## Confirmation boundary

This amendment does **not** silently replace the confirmation annotation procedure. The confirmation judging protocol must be finalized and recorded before confirmation query authoring and before confirmatory retrieval results are inspected.

If an LLM judge is later used for confirmation, that change must be explicitly documented before confirmatory grading. Any human-validation or double-annotation subset must likewise be defined before confirmation results are unblinded.

## Reporting boundary

A manuscript using these development judgments must not describe them as human annotations. A concise acceptable description is:

> Development relevance judgments were assigned by a blinded LLM judge using a preregistered four-level relevance scale; retrieval-profile identities, ranks, scores, and authoring-seed status were hidden during grading.

The exact judge model and protocol should be available in the reproducibility material. The main text need not emphasize operational details beyond what is necessary to make the evaluation method accurate and reproducible.
