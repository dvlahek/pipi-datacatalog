# PiPi Benchmark V2 — retrieval-provenance negative controls

This audit is a post-hoc systems validation. It does not alter or relabel the frozen RQ1–RQ4 scientific results.

The purpose is to test a narrower RQ2 claim: the frozen provenance anchors should reject or localize replay conditions that are no longer equivalent to the original run.

The audit covers four negative controls:

1. **Retrieval-profile mutation under the same profile ID.** The hybrid E5 profile keeps the same `profile_id`, but RRF `k` changes from 60 to 61. The configuration hash must change.
2. **Embedding-revision mutation under the same profile ID.** The embedding revision changes while the profile ID is unchanged. Both the embedding identity and profile hash must change.
3. **Chunking/index mutation.** A chunk-boundary change is applied to a publication-safe fixture hashed with the same chunk-manifest fields used by the frozen-corpus fingerprint (`chunk_index`, `char_start`, `char_end`, text SHA-256, metadata SHA-256). The fingerprint must change.
4. **Foreign catalog/corpus anchors.** Mutated catalog-snapshot and corpus-fingerprint anchors must fail equality with the frozen parent.

The audit also first checks that all five built-in E5 profile hashes still match the frozen confirmation hashes.

Run from the repository root:

```bash
python scripts/audit_retrieval_provenance_negative_controls.py
```

A successful audit ends with:

```text
RETRIEVAL_PROVENANCE_NEGATIVE_CONTROLS_PASS
```

## Interpretation

The strict 960/960 retrieval replay remains an implementation validation for a deterministic exact-retrieval path. These negative controls answer a different question. They show that the provenance contract does not silently accept a changed retrieval plan, changed embedding identity, changed chunk/index artifact, or changed catalog/corpus parent as the same frozen execution.

The chunking control is intentionally attached to the corpus/index artifact rather than to `RetrievalProfile`. Chunk construction precedes retrieval and is therefore modeled separately in the manuscript's provenance graph.

This audit does not evaluate ANN nondeterminism. The main benchmark deliberately uses exact pgvector cosine retrieval to isolate profile-induced drift from approximate-index effects.
