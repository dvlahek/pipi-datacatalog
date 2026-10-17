# Second-Corpus Confirmation Amendment 1 — SPARQL transport hardening

**Date:** 2026-10-17  
**Status:** frozen before any second-corpus dataset was selected and before any retrieval, generation, qrels, or answer-drift result existed.

## Trigger

The first bootstrap attempt failed immediately at `DISCOVER ENVI` with an HTTP 504 Gateway Timeout from `https://data.europa.eu/sparql`. No `SELECT <theme> ...` event had occurred and no second-corpus snapshot manifest or scientific result had been frozen.

## Scope of amendment

This amendment changes only the metadata-discovery transport layer. It does not change the scientific selection rule, corpus target size, themes, eligibility criteria, distribution cap, file-size cap, identity definitions, retrieval profiles, generators, metrics, hypotheses, or statistical interpretation.

The bootstrap implementation is amended as follows:

1. Prefer the documented machine-readable endpoint `https://data.europa.eu/data/sparql?locale=en` and retain `https://data.europa.eu/sparql` as a fallback.
2. Reduce SPARQL page size from 2000 to 500 rows.
3. Keep the predeclared discovery ceiling at 40,000 SPARQL rows per theme.
4. Retry transient HTTP 429/500/502/503/504 responses with exponential backoff before switching endpoint.
5. Record the effective SPARQL endpoints, page size, and per-theme discovery ceiling in the final snapshot freeze JSON.
6. Remove the unnecessary pip self-upgrade from the runner and pin only the bootstrap dependency `requests==2.34.2` inside `.venv-second-corpus`.

## Scientific invariants

The following remain unchanged:

- four themes: ENVI, TRAN, HEAL, ECON;
- target 200 eligible datasets per theme, 800 total;
- deterministic SHA-256 selection key based on `SECOND_CORPUS_DATAEUROPA_V1|theme|dataset_uri`;
- at most two retained distributions per dataset;
- 5 MiB maximum per retained distribution;
- 8 GiB raw-download budget;
- accepted textual/text-extractable formats;
- dataset → distribution/file → chunk provenance hierarchy;
- frozen E5/BGE-M3 retrieval setup;
- frozen Qwen3-8B primary generator and Ministral/Gemma robustness generators;
- frozen replay, churn, RBO, hidden-drift, and answer-drift analyses.

## Interpretation

Because the amendment was made after an infrastructure-level 504 and before the first selected dataset or any downstream result, it is treated as a pre-result operational amendment rather than result-dependent tuning.
