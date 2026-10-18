# PiPi Retrieval Benchmark V2 — Protocol Amendment 2

Status: **adopted after development retrieval pooling and before any development relevance grading, confirmation query authoring, or confirmation retrieval**

This amendment adds frozen authoring evidence seeds to the human relevance-judgment pool. It does not change any retrieval profile, retrieval rank, corpus item, development query, or confirmation allocation.

## Reason for the amendment

The frozen 48-query development set was retrieved with the five preregistered profiles at depth 20 per profile. The resulting union pool covered every pre-authored target scope for 46 of 48 development queries. Two pre-authored evidence scopes were absent from the union of the five top-20 lists.

This is not a retrieval-quality result. It is a pooling-adequacy finding: finite-depth pooling can omit evidence that was identified from the frozen corpus before retrieval output was inspected. Excluding such evidence from human judging would make the resulting qrels depend unnecessarily on the retrieval systems being evaluated.

The development split is the intended place to settle this annotation workflow. No pooled candidate had been graded when this amendment was adopted, and confirmation queries had not yet been authored.

## Authoring-seed rule

For every benchmark query, the evidence identifiers frozen during retrieval-blind query authoring are treated as **authoring seeds** for the human judgment pool.

The pool is therefore the deduplicated union of:

1. the top-20 results from each preregistered retrieval profile, and
2. the frozen authoring evidence seeds recorded with the query.

Authoring seeds are identified only from the already-frozen fields:

- `target_dataset_identifiers`
- `target_file_paths`
- `target_chunk_hints`

No new evidence target may be chosen from observed retrieval rankings when applying this rule.

## Seed resolution

Seed resolution is deterministic against the frozen/current benchmark snapshot.

For non-software evidence, each target dataset is combined with the frozen target chunk hints. For software evidence, the frozen file path is part of the seed identity. When multiple software file paths and chunk hints are present, one-to-one pairing is used only when the cardinalities match; otherwise the augmentation step must refuse ambiguous input rather than infer a mapping.

A resolved seed is identified by the same pool key used for retrieved evidence:

`(dataset_identifier, dataset_version, chunk_index)`

If the seed already exists in the retrieval pool, it is marked as an authoring seed and not duplicated. If it is absent, it is appended with an empty `retrieved_by` map.

## Judgment boundary

An authoring seed receives **no automatic relevance grade**.

Every seeded candidate is judged on the same 0–3 scale as every retrieved candidate:

- 3 — directly answers the information need
- 2 — clearly relevant supporting evidence but incomplete on its own
- 1 — topically related but insufficient or weak evidence
- 0 — irrelevant

The existence of a seed is provenance about query construction, not a relevance label.

## Retrieval-metric boundary

Seed augmentation does not modify retrieval output or retrieval ranks. A seed that was not returned by a profile remains absent from that profile's ranked list. It therefore cannot become a hit, improve reciprocal rank, change nDCG, or otherwise alter a profile's retrieval result merely because it was added to the judgment pool.

The original development retrieval ledger remains immutable and publication-safe. The augmented annotation pool is a separate local artifact.

## Confirmation use

The same authoring-seed rule applies prospectively to confirmation queries. Confirmation evidence seeds must be frozen during retrieval-blind query authoring, before confirmatory profile results are inspected. The confirmation pool is then constructed from the preregistered top-20 profile union plus those already-frozen seeds.

## Provenance

This amendment supplements, but does not rewrite, the base machine-readable protocol revision 2. Existing frozen development artifacts retain their original `protocol_sha256` so their provenance remains reproducible. Augmented annotation artifacts must additionally record the SHA-256 of this amendment and the unaugmented pool hash.
