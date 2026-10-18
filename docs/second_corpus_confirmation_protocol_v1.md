# Independent Second-Corpus Confirmation Protocol V1

**Status:** FROZEN BEFORE RETRIEVAL RESULTS  
**Freeze date:** 2026-10-17  
**Corpus:** data.europa.eu public DCAT-AP metadata + downloadable textual distributions  
**Purpose:** independent-corpus confirmation of the provenance-granularity and evidence-drift claims from the primary corpus.

## 1. Confirmation principle

Only the corpus and the confirmation query set change. The retrieval architecture, profile definitions, embedding families, lexical/vector/hybrid logic, top-k=10, chunking settings, provenance identity rules, RBO/churn/replay metrics, generator prompt/evidence serialization, local frozen Qwen3-8B / Ministral-3-8B / Gemma-3-4B checkpoints, generation settings, and 0–3 answer-drift rubric remain frozen from C1.

Qwen3-8B remains the primary answer-drift generator. Ministral-3-8B and Gemma-3-4B remain robustness generators. No parameter may be changed because of observed C2 results.

## 2. Public corpus

Four DCAT-AP thematic families are frozen:

1. Environment (ENVI)
2. Transport (TRAN)
3. Health (HEAL)
4. Economy and finance (ECON)

Target snapshot: **800 datasets**, 200 per theme.

Eligibility:

- English title and non-empty English description;
- at least two public distributions with stable DCAT distribution identity;
- at least two distributions downloadable as textual or text-extractable content;
- accepted content families: PDF, text/plain, CSV, JSON, XML, HTML;
- maximum downloaded size: **5 MiB per distribution**;
- at most **2 distributions per dataset** retained;
- redirects allowed, but final URL and hashes recorded;
- inaccessible, authentication-gated, oversized, executable, archive-only, and binary-only distributions excluded.

Selection is deterministic. Candidate datasets are ordered by SHA-256 of:

`SECOND_CORPUS_DATAEUROPA_V1|theme|dataset_uri`

and the first 200 eligible datasets per theme are retained. No retrieval or answer-drift result is used during corpus selection.

## 3. Provenance identities

- **dataset identity:** canonical DCAT dataset URI;
- **file/distribution identity:** canonical DCAT distribution URI + frozen content SHA-256;
- **chunk identity:** `(distribution identity, chunk_index, chunk_text_sha256)`.

## 4. Disk budget

At most 800 × 2 × 5 MiB ≈ **8 GiB** raw payload. The remainder is reserved for extracted text, E5/BGE-M3 embeddings, indexes, ledgers, and the three frozen generators. The bootstrap aborts at an 8-GiB raw-download budget.

## 5. Query set

Target: **96 frozen confirmation queries**.

Balanced design: 4 themes × 6 query types × 4 queries per cell.

Frozen query types:

1. exact lookup;
2. entity/dataset lookup;
3. relation/comparison;
4. topic discovery;
5. semantic paraphrase;
6. constraint-filtered lookup.

Queries are constructed only from the frozen snapshot. The complete 96-query JSON is frozen and SHA-256 hashed **before any C2 retrieval profile is evaluated**. No query may be edited after seeing retrieval or answer-drift results.

Qrels are optional for the core provenance analysis and, if created, are frozen separately.

## 6. Confirmation hypotheses

### H1-R — granularity

Apparent evidence stability depends on identity granularity. Chunk-level churn is expected to be at least as large as file/distribution-level churn, which is expected to be at least as large as dataset-level churn.

### H2-R — hidden drift

Cases exist in which coarse dataset identity remains stable while file/distribution or chunk evidence changes.

Report:
- same top-10 dataset set + changed chunk set;
- dataset churn = 0 + chunk churn > 0;
- same top-1 dataset + changed top-1 chunk.

### H3-R — semantic consequence

Under frozen Qwen3-8B, changed top-ranked evidence and greater chunk churn are expected to be associated with a higher probability/severity of answer drift. Repeat unchanged with Ministral-3-8B and Gemma-3-4B as robustness checks.

## 7. Retrieval profiles

Reuse C1 profile families unchanged:

- lexical;
- vector E5 content;
- hybrid E5 content;
- vector E5 metadata;
- hybrid E5 metadata;
- vector BGE-M3 content;
- hybrid BGE-M3 content;
- vector BGE-M3 metadata;
- hybrid BGE-M3 metadata.

For C2, metadata means frozen canonical DCAT metadata serialization and content means extracted distribution content.

## 8. Required label-free outputs

For every frozen profile comparison:

- dataset churn@10;
- file/distribution churn@10;
- chunk churn@10;
- RBO@10;
- top-1 dataset change;
- top-1 distribution change;
- top-1 chunk change;
- ordered-evidence identity hash;
- replay success/failure;
- first-divergence component.

These are the primary independent-corpus provenance outputs and require no qrels.

## 9. Answer-drift confirmation

For the same frozen primary retrieval-profile pair used in C1, generate answers with the same three frozen generators.

Primary generator: Qwen3-8B.

Report:

- material-drift count/rate;
- ordinal grade distribution;
- material-drift rate when top-1 chunk changed vs unchanged;
- Fisher exact odds ratio and two-sided p-value;
- Spearman association between chunk churn and ordinal answer-drift grade;
- hidden-drift answer-impact subsets.

No new human audit is required for C2 unless reviewers explicitly request it.

## 10. Replay

Reuse the C1 replay contract:

`B_R = (h_D, h_C, h_i, h_r, h_q, h_x, h_E)`

First divergence is localized in frozen order:

`h_D → h_C → h_i → h_r → h_q → h_x → h_E`.

## 11. Reporting rule

C2 is a confirmation layer, not a gate for retaining C1.

Possible outcomes are reported unchanged:

- strong replication: granularity ordering + hidden drift + semantic association;
- partial replication: provenance results reproduce but semantic association is weaker;
- non-replication: expected ordering or semantic relationship is absent.

No outcome may trigger post-hoc parameter optimization.

## 12. Permitted manuscript wording if successful

> The granularity-dependent provenance pattern was reproduced in an independent public DCAT-AP corpus Under the frozen retrieval and generation protocol.

Do not claim corpus-independence, universality, embedding-independence, generator-independence, or causality.

## 13. Freeze artifacts required before first retrieval run

1. `SECOND_CORPUS_CONFIRMATION_PROTOCOL_V1.md`
2. `dataeuropa_snapshot_manifest.jsonl`
3. `dataeuropa_snapshot_freeze.json`
4. `second_corpus_queries_96.json`
5. SHA-256 manifest covering 1–4
6. exact local model/checkpoint/config manifest
7. exact retrieval-profile manifest

Only after these are frozen should C2 retrieval begin.
