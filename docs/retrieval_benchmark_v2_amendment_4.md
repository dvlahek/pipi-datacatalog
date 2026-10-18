# PiPi Retrieval Benchmark V2 — Protocol Amendment 4

Status: **adopted after development diagnostics and before confirmation query authoring, confirmation retrieval, or confirmation relevance grading**

This amendment freezes the confirmation relevance-judgment procedure. It does not alter the frozen corpus, the five retrieval profiles, retrieval parameters, the 192-query confirmation allocation, the 48-query duplicate-judgment allocation, the relevance scale, the authoring-seed rule, or the preregistered retrieval metrics.

## Reason for the amendment

Development evaluation under Amendment 3 used a blinded LLM judge. Before confirmation query authoring begins, the confirmation judging procedure must be fixed prospectively so the evaluation method cannot be chosen after confirmation retrieval results are observed.

The confirmation split remains confirmatory. Development results may inform implementation checks and reporting clarity, but they do not authorize changes to frozen retrieval-profile semantics.

## Confirmation judgment pool

Protocol Amendment 2 applies unchanged to confirmation.

For every confirmation query, the judgment pool is the deduplicated union of:

1. the top-20 results from each of the five frozen retrieval profiles, and
2. the authoring evidence seeds frozen during retrieval-blind confirmation query authoring.

Authoring seeds receive no automatic relevance grade and do not modify retrieval ranks or profile results.

## Primary confirmation judge

Every confirmation query–evidence pair is graded in one primary pass by **OpenAI GPT-5.6 Sol** using the frozen four-level scale:

- **3 — directly relevant:** directly answers the information need or contains decisive evidence needed for the answer
- **2 — supporting relevant:** clearly contributes useful evidence but is incomplete on its own
- **1 — weakly/topically related:** related to the topic or entity but insufficient for the information need
- **0 — irrelevant:** does not provide useful evidence for the information need

For relation-comparison queries, a chunk that clearly supports one side of the comparison may receive grade 2. Grade 3 is reserved for evidence that directly satisfies the information need on its own.

## Blinding

The judge may receive only:

- frozen query text
- frozen information-need description
- source identity needed to interpret the candidate
- source/file path when applicable
- candidate evidence text

The judge must not receive:

- retrieval-profile identity
- retrieval rank or score
- lexical/vector component ranks
- authoring-seed status
- frozen target identifiers or chunk hints
- aggregate confirmation retrieval-quality results
- grades from another judging pass

Candidate order must be independent of retrieval rank.

## Preregistered replicate-judgment subset

The existing query-authoring scaffold already marks exactly **48 confirmation queries** for duplicate judgment: two queries from each of the 24 source-family × query-type cells.

The frozen selection rule is:

- `cell_position = 1` — cross-language query
- `cell_position = 3` — same-language query

These 48 queries receive a second independent judging pass with the same model and rubric. The second pass uses a separate context and an independently derived candidate order and has no access to first-pass grades.

Because both passes use the same model family, the resulting statistic is reported as **replicate-judge consistency**, not as human inter-annotator agreement.

Report at least:

- exact grade agreement
- agreement within one grade
- quadratic-weighted Cohen's kappa
- the full 4 × 4 grade-confusion matrix

## Disagreement resolution

For the 48-query replicate subset:

- if pass 1 and pass 2 agree, that grade is final
- if they disagree, a third independent blinded pass is run for that candidate
- the final grade is the median of the three ordinal grades

The third pass has no access to the first two grades. All disagreements are resolved this way, not only disagreements larger than one grade.

For the other 144 confirmation queries, the primary-pass grade is final.

The raw pass-level grades, replicate-consistency statistics, third-pass grades where needed, and final qrels must all be retained in provenance artifacts.

## Confirmation metric boundary

Final confirmation metrics are computed only after the confirmation qrels are frozen and hashed.

The primary quality metric remains `nDCG@10`. Secondary metrics remain MRR, Recall@10, Hit@1, Hit@3, and Hit@10. Drift metrics and the preregistered statistical tests remain unchanged.

No retrieval-profile parameter, query wording, relevance threshold, corpus item, or profile definition may be changed after confirmation retrieval results are inspected.

## Reporting boundary

The manuscript must describe confirmation judgments as LLM judgments, not human annotations. A concise main-text description is sufficient, for example:

> Confirmation relevance judgments were assigned by a blinded LLM judge using the preregistered four-level relevance scale. Retrieval-profile identities, ranks, scores, and authoring-seed status were hidden during grading. A preregistered 48-query subset was independently re-judged to quantify replicate-judge consistency, with a third blinded pass resolving disagreements.

The exact model label, prompts/protocol, pool hash, amendment hash, pass-level judgment hashes, final qrels hash, and replicate-consistency results should be included in the reproducibility material.

## Provenance

This amendment supplements the immutable base protocol revision 2 and Amendments 1–3. Existing artifacts retain their original `protocol_sha256`. Confirmation artifacts must additionally record the SHA-256 or Git blob identity of this amendment and the machine-readable confirmation judging configuration.
