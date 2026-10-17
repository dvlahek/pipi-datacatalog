# Independent Second-Corpus Confirmation Protocol V2

**Status:** FROZEN BEFORE ANY C2 DATASET SELECTION  
**Freeze date:** 2026-10-17  
**Supersedes:** `second_corpus_confirmation_protocol_v1.md` before any C2 dataset was selected and before any C2 retrieval/generation result was observed.  
**Corpus:** data.europa.eu public DCAT/CKAN metadata plus directly downloadable, openly licensed distribution contents.

## 1. Purpose

C2 is an independent-corpus confirmation and a prospective mechanism test.

C1 showed that apparent provenance stability depended on evidence identity granularity. It also suggested that the dataset-to-chunk gap was larger when a coarse dataset identity contained many independently retrievable evidence units. C2 is designed before observing C2 results to test that mechanism on independently harvested public distributions.

C1 open-data evidence consisted primarily of catalogue records. C2 instead indexes the contents of downloadable DCAT distributions. C2 therefore does not simply repeat the C1 open-data family.

Only the corpus and the confirmation query set change. Retrieval, generation, identity, replay, and answer-drift definitions remain frozen from C1 unless an explicitly documented format-adapter requirement is listed below.

## 2. Acquisition source and immutable candidate ordering

Metadata source:

`https://data.europa.eu/api/hub/search/ckan/package_search`

The CKAN-compatible search API is used instead of the public SPARQL endpoint because the V1 pre-selection bootstrap encountered gateway timeouts before any dataset was selected. The API change is a transport/acquisition amendment only and occurred before any C2 result existed.

Themes:

1. ENVI — Environment
2. TRAN — Transport
3. HEAL — Health
4. ECON — Economy and finance

For each theme, the candidate universe is the first **20,000** records returned by the frozen CKAN query with:

- `fq=groups:<lowercase-theme-code>`
- `sort=id asc`
- pagination in blocks of 1,000.

If fewer than 20,000 theme records exist, all returned records form the candidate universe.

Before any distribution payload is downloaded, the script writes and hashes:

- `candidate_universe.jsonl`
- `candidate_order.jsonl`
- `candidate_universe_freeze.json`

Candidate selection order is then independent of API relevance/ranking output:

`SHA256("SECOND_CORPUS_DATAEUROPA_V2|theme|dataset_id")`, ascending.

The harvest UTC timestamp, endpoint, exact request parameters, candidate counts, and hashes are frozen.

## 3. Dataset sample

Target: **800 datasets**, 200 per theme.

Selection traverses the frozen SHA-256 order and accepts the first 200 eligible datasets per theme. No manual replacement is permitted.

To reduce domination by one provider, no more than **20 selected datasets per normalized publisher key per theme** are allowed. If publisher identity is missing, the catalogue identifier is used as the provider key. The cap is part of eligibility and is applied before accepting a dataset.

If fewer than 200 eligible datasets can be selected in any theme under these frozen rules, C2 corpus construction fails. Rules are not relaxed after inspecting attrition.

Every attempted candidate and every rejected distribution is written to an attrition ledger with a machine-readable reason.

## 4. Distribution eligibility

Each selected dataset must provide at least **two** eligible distributions. Exactly two are retained.

Only explicit `dcat:downloadURL` equivalents exposed through the CKAN `download_url` field are eligible. `accessURL`/resource `url` is not used as a substitute.

When multiple download URLs are present for one distribution, URLs are sorted lexicographically and the first HTTP(S) URL is used.

Distributions are tried in deterministic order:

`SHA256("SECOND_CORPUS_DATAEUROPA_V2|theme|dataset_id|distribution_id")`, ascending.

A failed/ineligible distribution is skipped and the next distribution in this frozen order is tried.

Distribution constraints:

- direct HTTP(S) download URL
- explicit open licence under the frozen whitelist in `second_corpus_frozen_config_v2.json`
- maximum downloaded payload: **5 MiB**
- supported C1-compatible formats only: PDF, plain text, CSV, JSON, HTML/XHTML
- XML is excluded because the C1 indexer did not support a dedicated XML extraction path
- successfully extractable non-empty canonical text
- **1–512 chunks** after the frozen extraction/chunking contract

A distribution producing more than 512 chunks is excluded in full. It is never truncated.

A dataset is accepted only after two distributions pass all rules.

## 5. Licence rule

The retained distribution must expose an explicit licence value that matches the frozen open-licence whitelist.

Licence lookup precedence:

1. distribution/resource-level `license` / `licence` fields
2. dataset-level `license`, `license_id`, `license_url`, or equivalent only when the resource does not expose its own licence

The provenance scope (`distribution` or `dataset`) is recorded.

Unknown, missing, ambiguous, non-whitelisted, or non-open licences are excluded.

The publication artifact will include dataset ID, distribution ID, download URL, licence value/scope, byte count, and SHA-256. Raw third-party bytes do not need to be redistributed.

## 6. Extraction and chunking contract

C2 deliberately reuses the C1 extraction/chunking semantics for already-supported content types.

Generic text chunker:

- `chunk_size = 1200` characters
- `overlap = 200` characters
- boundary preference: double newline, newline, sentence boundary
- normalized CR/LF and horizontal whitespace exactly as frozen in the C2 adapter implementation

Format rules:

- PDF: pypdf text extraction with `[Page N]` markers, then generic chunker
- TXT: decoded/normalized text, then generic chunker
- HTML/XHTML: script/style/noscript removed by the frozen HTML text adapter, then generic chunker
- JSON: deterministic key-sorted JSON serialization, then generic chunker
- CSV: the C1 structural rule is retained — one non-empty data row per chunk, represented as `header: value` pairs

The C2 adapter implementation and dependency versions are hashed in the corpus freeze.

The corpus report must provide chunk-count distributions by theme and format: median, IQR, p95, maximum, and chunks per dataset/distribution.

## 7. Provenance identities

- **dataset identity:** stable data.europa.eu/CKAN dataset identifier, with canonical URI recorded when available
- **file/distribution identity:** stable CKAN/DCAT distribution identifier plus frozen payload SHA-256
- **chunk identity:** `(distribution identity, chunk_index, chunk_text_sha256)`

The selected-corpus manifest also stores extracted-text SHA-256 and ordered chunk hashes.

## 8. Query set

After the corpus snapshot is frozen, construct **96 confirmation queries**:

- 4 themes
- 6 query types
- 4 queries per `(theme, query_type)` cell

Query types:

1. exact lookup
2. entity/dataset lookup
3. relation/comparison
4. topic discovery
5. semantic paraphrase
6. constraint-filtered lookup

Each query record must freeze `source_dataset_ids` before any retrieval run.

Queries may use only the frozen metadata and retained distribution contents. The complete query JSON and SHA-256 are frozen before retrieval evaluation.

Qrels are optional for the provenance hypotheses.

## 9. Confirmatory hypotheses

The primary C2 retrieval intervention is the same frozen E5 hybrid representation change used in C1:

`hybrid-e5-content-v1` versus `hybrid-e5-metadata-v1`, top-k = 10.

### C2-H1 — Granularity

For each query q, compute dataset and chunk churn@10 between the two frozen profiles.

Confirmatory prediction: `chunk_churn_q > dataset_churn_q` in aggregate.

Test: paired Wilcoxon signed-rank test, two-sided, with the preregistered expected direction reported together with median paired difference and effect size.

### C2-H2 — Evidence-multiplicity mechanism

For each query q, define the preregistered source multiplicity from the query's frozen `source_dataset_ids`:

`M_q = mean_d log(1 + n_chunks(d))`.

Define:

`Delta_q = chunk_churn_q - dataset_churn_q`.

Confirmatory prediction: `Spearman(M_q, Delta_q) > 0`.

The multiplicity variable is computed from the frozen corpus and query provenance, not from retrieved results.

Test: two-sided Spearman correlation.

C2-H1 and C2-H2 form the two inferential confirmation tests. Holm adjustment is applied across their p-values at familywise alpha = 0.05.

### C2-H3 — Exact replay

The frozen retrieval replay contract must reproduce every recorded ordered evidence list exactly. Target: **100% exact replay**. Any failure is reported as a failed confirmation outcome, not tuned away.

## 10. Secondary descriptive outcomes

The following are secondary/descriptive in C2:

- file/distribution churn
- RBO@10
- top-1 dataset/distribution/chunk changes
- hidden retrieval drift
- conventional IR metrics if qrels are created
- answer drift
- hidden-drift answer impact
- generator-to-generator differences

Answer drift is not a confirmatory C2 endpoint because 96 queries are expected to yield too few material-drift events for stable subset inference.

The same frozen generators may be run:

- Qwen3-8B — primary C1 generator
- Ministral-3-8B — robustness
- Gemma-3-4B — robustness

C2 answer-drift rates, Wilson intervals, and exploratory associations may be reported descriptively, clearly separated from C2-H1/H2/H3.

No new human audit is required for C2.

## 11. Frozen retrieval/generation settings

The C1 settings remain frozen:

- multilingual-E5-small and BGE-M3
- lexical, vector, and hybrid/RRF profile definitions
- RRF parameter and top-k
- evidence formatting and prompt template
- generator checkpoints and decoding parameters
- dataset/file/chunk identity comparison code
- replay bundle `B_R = (h_D,h_C,h_i,h_r,h_q,h_x,h_E)`
- first-divergence order `h_D -> h_C -> h_i -> h_r -> h_q -> h_x -> h_E`
- answer-drift rubric 0–3 and material threshold 2–3

C2-specific extraction adapters are part of `P_i` and are therefore explicitly hashed and reported.

## 12. Required pre-query freeze artifacts

Before authoring the 96 queries:

1. this protocol
2. `second_corpus_frozen_config_v2.json`
3. candidate-universe freeze
4. selected dataset/distribution manifest
5. attrition ledger
6. chunk manifest
7. corpus freeze JSON
8. dependency/environment manifest
9. SHA-256 manifest covering all above artifacts

Only after these are frozen may the query set be authored. Only after the query set is frozen may retrieval evaluation begin.

## 13. Reporting guardrails

Permitted if supported:

> The granularity-dependent provenance pattern was reproduced in an independent public distribution corpus under a frozen protocol.

Permitted if C2-H2 is supported:

> The independent corpus also supported the preregistered mechanism that coarse-to-fine provenance divergence increases with the number of independently retrievable evidence units represented by a coarse source identity.

Not permitted:

- corpus-independent
- universal
- embedding-independent
- generator-independent
- causal proof

All non-replications and partial replications are retained and reported unchanged.
