# PiPi Retrieval Benchmark V2 Protocol

Status: **design frozen before query authoring**

This document defines the experimental protocol for the first confirmation-scale PiPi retrieval benchmark. The machine-readable specification is `config/rag_benchmark_v2_protocol.json` and takes precedence if a count differs from this prose summary.

## 1. Why this benchmark exists

Pilot P1 showed two facts that now need confirmation on a larger benchmark. First, frozen retrieval profiles can be replayed exactly when the profile hash and catalog snapshot are unchanged. Second, changing only the retrieval representation can alter the selected evidence even when the corpus, base embedding model, RRF configuration, and query are held fixed.

V2 is not designed to tune a better retriever. Its main purpose is to measure retrieval quality and retrieval-induced evidence drift under controlled, versioned retrieval profiles.

## 2. Research questions

**RQ1.** How much does retrieval-profile design alter evidence selection under fixed data?

**RQ2.** Can versioned retrieval provenance reproduce and attribute evidence-set changes without confusing retrieval drift with data drift?

**RQ3.** How do retrieval quality and retrieval stability relate across query types, source families, and language relations?

Answer drift is deliberately outside V2. It will be added only after the retrieval benchmark and relevance judgments are frozen.

## 3. Split design

V2 contains 240 queries:

| Split | Queries | Use |
|---|---:|---|
| Development | 60 | construction checks, annotation checks, implementation debugging |
| Confirmation | 180 | final statistical claims |
| Total | 240 | |

The 16 Pilot P1 queries remain a historical development artifact. They must not enter the V2 confirmation set.

No retrieval parameter, profile definition, confirmation query wording, relevance threshold, or corpus composition may be tuned using confirmation results.

## 4. Source-family balance

The benchmark contains three heterogeneous source families, each with 80 queries:

- `structured-data`: 20 development + 60 confirmation
- `software-documentation`: 20 development + 60 confirmation
- `institutional-documents`: 20 development + 60 confirmation

Before query writing starts, a corpus-capacity audit must verify that each family has enough distinct evidence to support its quota without excessive target reuse. If not, the protocol is amended before query authoring, not after retrieval results are observed.

## 5. Query-type balance

Six query types are used, each with 40 queries overall and 30 confirmation queries:

- `exact-lookup`
- `semantic-paraphrase`
- `topic-discovery`
- `entity-document-lookup`
- `relation-comparison`
- `constraint-filtered-lookup`

The confirmation split is perfectly balanced: every source-family × query-type cell contains exactly 10 queries. The development split contains 3 or 4 queries per cell according to the matrix in the machine-readable protocol.

## 6. Cross-language design

Cross-language retrieval is an orthogonal factor, not a separate retrieval task.

- development: 18 cross-language, 42 same-language
- confirmation: 54 cross-language, 126 same-language
- total: 72 cross-language, 168 same-language

Every development source-family × query-type cell contains exactly one cross-language query. Every confirmation cell contains exactly three cross-language queries.

For every case we record query language, primary target-evidence language, and `language_relation`. Direction is not artificially forced to be symmetric when a source family is naturally language-specific.

## 7. Query authoring rules

Each query must begin from a documented information need before retrieval output is inspected. Confirmation wording is frozen before confirmatory profile results are viewed.

Near-duplicate questions are not allowed. Changing punctuation, copying one different keyword, or trivially reordering the same words does not create a new information need. Reuse of one evidence target is allowed only when the questions represent genuinely different information needs and no target dominates a benchmark cell.

Every query must be answerable from the corpus snapshot that will later be frozen for V2.

## 8. Relevance judgments

Relevance is graded at chunk level:

| Grade | Meaning |
|---:|---|
| 3 | directly answers the information need |
| 2 | clearly relevant supporting evidence, but incomplete alone |
| 1 | topically related but insufficient or weak evidence |
| 0 | irrelevant |

Candidate pooling uses the top 20 results from each frozen baseline profile and deduplicates candidates by `(dataset_identifier, dataset_version, chunk_index)`.

The pooling profiles are:

- `lexical-v1`
- `vector-e5-content-v1`
- `hybrid-e5-content-v1`
- `vector-e5-metadata-v1`
- `hybrid-e5-metadata-v1`

All pooled candidates receive one human judgment. At least 54 confirmation queries are double-annotated: exactly three from each of the 18 source-family × query-type cells, stratified across language relation where possible. Ordinal inter-annotator agreement is reported. Disagreements larger than one relevance grade are adjudicated.

## 9. Frozen profile comparisons

The primary controlled contrast is:

`hybrid-e5-content-v1` vs `hybrid-e5-metadata-v1`

Secondary preregistered contrasts are:

- `vector-e5-content-v1` vs `vector-e5-metadata-v1`
- `lexical-v1` vs `hybrid-e5-content-v1`
- `lexical-v1` vs `hybrid-e5-metadata-v1`

Existing profile IDs are immutable. A changed configuration requires a new profile ID. New profiles are exploratory unless added by protocol amendment before confirmation results are inspected.

## 10. Metrics

Primary retrieval-quality metric:

- nDCG@10

Secondary quality metrics:

- MRR
- Recall@10
- Hit@1
- Hit@3
- Hit@10

Chunk-level drift metrics:

- Jaccard@10
- retention@10
- churn@10
- top-1 chunk change rate
- mean absolute rank shift on shared chunks

Source-level drift collapses repeated chunks from the same versioned dataset and reports:

- source Jaccard@10
- source retention@10
- source churn@10
- top-1 source change rate

After relevance judgments exist, V2 also measures retention of clearly relevant evidence (grades 2–3) and the association between evidence drift and absolute nDCG change.

## 11. Statistical plan

The query is the statistical unit. Final hypothesis tests use the 180 confirmation queries only.

We report 95% paired bootstrap confidence intervals using 10,000 query-level resamples. Preregistered profile-quality comparisons use paired Wilcoxon signed-rank tests on per-query nDCG@10 with paired rank-biserial effect sizes. Holm correction is applied across secondary preregistered profile comparisons.

Subgroup estimates by source family, query type, and language relation are reported with bootstrap intervals. Interaction models remain exploratory unless explicitly added before confirmation unblinding.

The association between retrieval drift and retrieval-quality change is measured with Spearman correlation on the confirmation split.

## 12. Provenance freeze

The final V2 result package must record:

- catalog snapshot hash
- retrieval profile IDs and full config hashes
- benchmark file SHA-256
- taxonomy/design file SHA-256
- relevance-judgment file SHA-256
- Git commit SHA
- ordered evidence identities for each run
- metric implementation version

Corpus changes after the snapshot freeze create a new benchmark snapshot. Results from different snapshots must not be silently combined.

## 13. What happens next

The next step is **not** to author 240 questions immediately. First run the corpus-capacity audit. We then confirm that each source family can support the planned balanced design with sufficiently diverse evidence targets. Only after that gate passes do we create the development queries, validate the annotation workflow, and then freeze the 180-query confirmation set.
