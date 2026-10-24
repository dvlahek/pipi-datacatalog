# Published replay-verification artifacts

This directory contains the publication-safe frozen retrieval artifacts supporting the exact ordered-evidence replay result reported in **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**.

The files expose retrieval identities, ordering, provenance identifiers, scores, configuration hashes, and content hashes needed to inspect the recorded replay result without redistributing the underlying source or evidence text. They are original frozen experiment artifacts; they were not regenerated or rewritten for publication.

## Corpus A

- `corpus_a/benchmark_v2_confirmation_retrieval_ledger_c725fba20382.json` — complete frozen 20-result retrieval ledger for the 960 recorded corpus-A retrieval runs.
- `corpus_a/benchmark_v2_confirmation_strict_replay_c725fba20382.json` — strict replay audit linked to the ledger by SHA-256. It records 960 evaluated runs, 960 exact ordered-evidence reproductions, and zero failures.

The published corpus-A ledger has SHA-256:

```text
335555045685798fc27f781b39092d1b1b9f17af8c53dd16d0e2f757db18a1c0
```

The strict replay artifact records the same ledger hash.

## Corpus B

- `corpus_b/primary_retrieval_runs.jsonl` — frozen ordered top-10 retrieval identities for 192 corpus-B runs.
- `corpus_b/retrieval_freeze.json` — retrieval freeze linking the 192-run ledger to its recorded configuration and SHA-256.
- `corpus_b/replay_audit.json` — exact replay audit reporting 192/192 ordered-evidence reproductions and zero failures.

The published corpus-B retrieval ledger has SHA-256:

```text
5138ae7d90906709b1b5f8792560c8ddde95b57a01614cafbc951e7542294383
```

The same value is recorded as `primary_retrieval_runs_sha256` in `retrieval_freeze.json`.

## Integrity checks

`SHA256SUMS.txt` records the hashes of all published frozen replay artifacts. From the repository root, verify them with:

```bash
(cd reproducibility/replay && sha256sum -c SHA256SUMS.txt)
```

The publication verifier also checks the replay-artifact hashes, linkage, replay counts, and manuscript headline summaries:

```bash
python reproducibility/verify_reported_results.py
```

## Scope

These artifacts support public verification of the recorded exact ordered-evidence replay endpoint: 960/960 corpus-A runs plus 192/192 corpus-B runs, for 1,152/1,152 in total.

They do **not** constitute a clean-room rebuild of the original retrieval environment. The package does not redistribute the underlying source/chunk text, raw answer/evidence material, the full corpus-A confirmation query JSON, or every original runtime and index-construction input. The manuscript documents those environment-level limitations separately.
