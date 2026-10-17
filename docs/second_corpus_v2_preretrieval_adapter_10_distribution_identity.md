# C2 pre-retrieval adapter 10: distribution and chunk identity

Date: 2026-10-17

## Scope

This adapter is frozen after the 96-query C2 set was frozen and before the first C2 retrieval result was produced. It resolves representation details that do not occur in the C1 corpus because every C2 dataset retains two DCAT distributions. It does not change the frozen C1 retrieval profiles, model, RRF parameter, candidate depth, top-k, query texts, source dataset identities, corpus membership, or confirmatory hypotheses.

## Frozen C1 retrieval semantics retained

Primary profiles:

- `hybrid-e5-content-v1`, config hash `04fd11fb3c56e9273f7b312a376d5c975a852489276f87fc796f7e0c716f7a45`
- `hybrid-e5-metadata-v1`, config hash `7b63711593b091d1c21a1548f1b672f4572c69b4fca380779114cad6163211e4`

Both use `intfloat/multilingual-e5-small`, 384 dimensions, E5 `passage:` / `query:` prefixes, normalized embeddings, lexical-plus-vector reciprocal-rank fusion with `k=60`, candidate depth 50 for a final `top_k=10`, and a soft source cap of 2 before deferred candidates are appended.

The C1 pgvector path serializes embedding components with 10 significant digits before vector storage/query. The standalone C2 runner reproduces that numerical boundary by quantizing each embedding component with `.10g` and storing it as float32 before cosine ranking.

## Distribution identity

The C2 file/source identity is the frozen distribution identity:

`(dataset_id, distribution_id, payload_sha256)`.

The soft source-diversity key is this distribution identity. The cap remains 2, matching the C1 `source-file-soft-cap-v1` semantics.

Different distribution IDs are retained as different source identities even when their payload hashes are identical. This follows the frozen corpus policy of reporting, but not post-selection deduplicating, distinct distribution references.

## Chunk identity

The C2 retrieval chunk identity is:

`(dataset_id, distribution_id, payload_sha256, chunk_index, chunk_text_sha256)`.

This prevents collisions between chunk 0 of the two distributions retained for the same dataset. Exact duplicate fine-grained identities caused only by the same dataset/distribution appearing in more than one theme stratum are collapsed once in the logical retrieval universe. Their theme memberships are retained as provenance metadata. This avoids multiplying identical evidence solely because a catalogue dataset belongs to more than one frozen theme stratum.

If the same dataset/distribution/chunk index appears with a different payload or chunk-text hash, it remains a distinct frozen evidence identity.

## Metadata-v1 file-path adapter

C1 `metadata-v1` prepends the dataset title and source file path before chunk content. C2 maps the distribution URL to that file-path field deterministically:

1. use `final_url` when present, otherwise `download_url`;
2. parse the URL and take only the percent-decoded path component;
3. discard scheme, host, query string, and fragment;
4. normalize repeated `/` separators;
5. omit the file-path line if the resulting path is empty or `/`.

The embedding input remains exactly:

```text
Dataset title: <title>
File path: <decoded URL path, when non-empty>
Content:
<chunk text>
```

`content-v1` remains the raw frozen chunk text only.

## Ranking tie handling

C1 vector SQL orders by cosine distance without a secondary tie key. The standalone C2 implementation adds a deterministic evidence-identity tie break only when scores are equal. Lexical and fused ranking likewise use the frozen evidence identity as the deterministic secondary key after the C1 primary score. This is required for exact replay and does not use relevance labels or retrieval outcomes.

## Cross-theme overlaps

The frozen C2 corpus has 400 theme-stratum records but 397 unique dataset IDs. Retrieval searches one logical corpus across all themes, as in C1. Theme labels are not retrieval filters. Exact duplicate fine-grained evidence is indexed once, while nonidentical distributions or payloads associated with an overlapping dataset remain available under that dataset identity.

## Provenance boundary

The C2 runner must verify both the complete pre-query corpus SHA manifest and the complete query-freeze SHA manifest before embeddings or retrieval. Embeddings are checkpointed and hashed before primary retrieval. Retrieval outputs are frozen before H1/H2/H3 statistics are computed. No relevance judgment is required for the three confirmatory C2 hypotheses.