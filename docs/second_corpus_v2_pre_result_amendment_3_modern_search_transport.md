# Second-corpus V2 pre-result amendment 3: modern search transport

Date: 2026-10-17

Status: pre-result transport amendment. The scientific C2 protocol, hypotheses, target sample sizes, selection seed, eligibility rules, retrieval profiles, generators, and statistical analysis remain unchanged.

## Trigger

A read-only API preflight was run before any candidate-universe freeze, corpus selection, distribution download, retrieval evaluation, or answer generation.

Observed preflight facts:

- `GET /api/hub/search/ckan/package_search` without filters returned `count = 1,751,838`.
- CKAN `fq=groups:economy-and-finance` returned `count = 0`.
- CKAN `fq=groups:\"economy-and-finance\"` returned `count = 0`.
- CKAN `fq=categories:ECON` returned the unfiltered count `1,751,838`, so the category expression was not acting as the intended filter.
- `GET /api/hub/search/search?filters=dataset&facets={\"categories\":[\"ECON\"]}` returned `count = 119,421`.

Therefore the CKAN compatibility endpoint could not provide a trustworthy category-filtered candidate universe under the tested query contract, while the current Hub Search endpoint could.

## Amendment

The V2 metadata harvest transport is revised to V2.1:

- candidate discovery endpoint: `https://data.europa.eu/api/hub/search/search`
- document filter: `dataset`
- theme facet: `categories`
- theme values: `ECON`, `ENVI`, `HEAL`, `TRAN`
- page size: 1000
- deterministic API ordering: `id+asc`
- candidate cap: 20,000 per theme
- aggregation disabled during harvest
- distribution filtering disabled during harvest
- candidate universe and deterministic SHA-256 order are frozen before any payload download

The scientific protocol identifier remains `SECOND_CORPUS_DATAEUROPA_V2`; V2.1 denotes only the metadata-transport implementation revision.

## Guardrail

At the time of this amendment:

- no `candidate_universe_freeze.json` existed,
- no C2 dataset had been selected,
- no distribution payload had been accepted into C2,
- no C2 retrieval metric had been computed,
- no C2 answer had been generated.

This amendment therefore cannot depend on C2 scientific outcomes.
