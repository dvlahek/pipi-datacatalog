# PiPi Retrieval Benchmark V2 — Corpus Expansion Decision

Status: **query authoring blocked until corpus capacity passes**

The first V2 corpus-capacity audit showed that the planned 80/80/80 source-family balance is not yet supported by the current indexed corpus. This is a design-stage finding, not a benchmark result.

## Capacity finding

At the pre-authoring snapshot `f932c8191cce3b51145a525ec6d95d1a06d315d4a7f1ec5e41f93de8b059eb04`:

- structured data had 1 indexed dataset with 3 chunks for 80 planned queries
- software/documentation had 100 distinct indexed GitHub file paths and 1436 chunks for 80 planned queries
- institutional documents had 3 indexed documents with 48 chunks for 80 planned queries

The software/documentation family has adequate coarse diversity. Structured data and institutional documents do not.

## Decision

Keep the preregistered 80/80/80 query balance. Expand the corpus before authoring any V2 query instead of weakening the benchmark after seeing the capacity problem.

The minimum coarse diversity gate is 0.40 diversity units per planned query, which means at least 32 diversity units for each family with an 80-query quota. We target more than the minimum for institutional documents.

## Structured-data expansion

PiPi already treats Sensor Hub datasets as metadata-first. Raw observation streams are therefore not converted into long text documents and embedded as if they were prose.

For V2, every eligible Sensor Hub deployment-property dataset present before the corpus snapshot is frozen will receive a compact RAG metadata representation derived from its catalog metadata. The representation should contain stable fields useful for discovery, such as dataset title, description, measured property, deployment context, units or semantic links when available, access/distribution metadata, and provenance identifiers. It must not copy raw time-series payloads into the text RAG index.

The CSV demo remains one structured source. The target is at least 32 distinct versioned structured datasets with non-empty retrievable evidence.

## Software/documentation

No expansion is required before query authoring. The current GitHub adapter exposes 100 distinct file paths, which exceeds the minimum capacity gate. The exact repository HEAD and corpus provenance must be frozen with the final V2 snapshot.

## Institutional-document expansion

FOI document discovery already exposes a much larger catalog than the three documents currently indexed. V2 will index at least 40 distinct public FOI documents before query authoring.

Selection must be independent of retrieval results. Eligible FOI dataset identifiers are ordered by `SHA-256(dataset_identifier)`. Candidates are attempted in that deterministic order. Resolution/indexing failures are recorded and the next ranked candidate is tried until 40 distinct documents are successfully indexed.

This rule avoids manually choosing documents because they make one retrieval profile look better.

## Separation from Pilot P1

Pilot P1 remains bound to its original catalog snapshot and profile hashes. The V2 corpus expansion changes the catalog snapshot, so P1 must not be silently recomputed and presented as the same pilot.

## Gate before query authoring

After corpus expansion:

1. rebuild both content-v1 and metadata-v1 embedding representations for newly indexed chunks
2. rerun `scripts/audit_benchmark_v2_corpus.py`
3. require all three source families to report `PASS_CAPACITY_GATE`
4. freeze the V2 corpus snapshot and expansion manifest
5. only then begin writing development and confirmation queries

The machine-readable expansion decision is stored in `config/rag_benchmark_v2_corpus_expansion.json`.
