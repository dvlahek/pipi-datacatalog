# Publication verification package

This directory is the paper-facing package for **Retrieval Is Part of Data Space Provenance: Evidence Granularity and Replay for RAG**.

It is intentionally compact. The rest of the repository contains the PiPi data-catalog implementation and historical experiment-development records. Those files are useful for project provenance, but they are not required to read the paper or to check its headline claims.

## What is included here

- [`results/main_results_summary.json`](results/main_results_summary.json) — compact numerical summary of the corpus sizes, provenance-granularity results, H1/H2 outcomes, replay count, answer-drift endpoints, and human-validation statistics reported in the manuscript.
- [`results/same_evidence_summary.json`](results/same_evidence_summary.json) — the 306 same-evidence generation controls.
- [`replay/`](replay/) — publication-safe frozen retrieval ledgers, replay audits, retrieval-freeze linkage, checksums, and a focused replay-verification guide.
- [`protocols/corpus_b_amendment.md`](protocols/corpus_b_amendment.md) — the corpus-B sample-size amendment and its timing.
- [`verify_reported_results.py`](verify_reported_results.py) — a standard-library check of the manuscript headline values and the published replay-artifact hashes, linkage, and counts.
- [`manifest.json`](manifest.json) — index of this compact package.
- [`CITATION.cff`](CITATION.cff) — citation metadata.

Run the publication check from the repository root:

```bash
python reproducibility/verify_reported_results.py
```

A successful run confirms both the retained manuscript summaries and the integrity of the published replay-verification artifacts. The replay checksum file can also be checked directly:

```bash
(cd reproducibility/replay && sha256sum -c SHA256SUMS.txt)
```

## Corpus conventions

**Corpus A** uses datasets as sampling units: 274 sampled datasets, 274 unique dataset IDs, 3,974 chunk occurrences, and 192 confirmation queries. Its provenance levels are dataset, file-aware intermediate identity, and chunk.

**Corpus B** uses selection records as sampling units. The 400 selection records correspond to 397 unique dataset IDs because three datasets occur in two topical strata. Each selection record contributes two retained distributions, giving 800 distributions. The retained material contains 44,520 chunk occurrences before exact cross-stratum deduplication and 44,491 distinct retrieval rows after deduplication. Corpus B contains 96 queries. Its provenance levels are dataset, distribution, and chunk. A selection record is not a retrieval-provenance identity.

## Replay verification

The public package now includes the original frozen per-run retrieval ledgers and replay audits used for the exact ordered-evidence replay result:

- corpus A: 960/960 exact ordered-evidence replays;
- corpus B: 192/192 exact ordered-evidence replays;
- combined: 1,152/1,152.

The corpus-A strict replay artifact cryptographically identifies the published corpus-A ledger. The corpus-B retrieval freeze identifies the published 192-run ledger by SHA-256, and the corpus-B replay audit reports the corresponding 192/192 exact replay result. See [`replay/README.md`](replay/README.md) for the artifact-level details.

## Scope of verification

The package supports verification of the published numerical summaries, replay-artifact identities, hash linkage, and recorded exact ordered-evidence replay endpoint. It is not a substitute for every original experiment input and does not claim a clean-room rebuild of the complete runtime environment.

The full corpus-A confirmation query set is cryptographically identified by SHA-256 `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`, but the complete 192-query JSON artifact is not redistributed in this compact publication surface. Selected original runtime and index-construction inputs are also outside the package.

Raw source/chunk text and raw answer/evidence material are a separate case: they are not redistributed where licensing or privacy constraints do not permit publication. The published replay ledgers instead retain stable identities, ordering, provenance fields, and content hashes needed to inspect the recorded evidence identity without publishing the evidence text itself.

## Broader repository

The application code under `app/`, database code, tests, and experiment scripts remain in the repository because the paper was produced from the PiPi system rather than from a separate toy implementation. The dated files under `docs/` and `history/` are historical project records. They preserve development chronology and may contain superseded terminology or intermediate analyses; they are **not** an extension of the manuscript claims.

For the paper itself, use this directory and the manuscript as the authoritative publication surface.
