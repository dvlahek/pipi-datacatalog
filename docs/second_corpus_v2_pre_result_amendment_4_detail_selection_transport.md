# Second corpus V2 pre-result amendment 4: detail-selection transport

Date: 2026-10-17

Status: PRE-RESULT / BEFORE SECOND-CORPUS SELECTION

## Trigger

The frozen V2.1 category-filtered candidate universe was successfully harvested from the current data.europa.eu `/search` endpoint. The resulting search records did not contain distribution metadata (`with_dists=0`, `with_download_url=0` for all four themes), although the dataset-detail endpoint returned full `distributions` records in a read-only preflight.

At the time of this amendment:

- the candidate universe and order were frozen,
- zero C2 datasets had been selected,
- zero C2 distributions had been retained,
- zero retrieval outcomes had been computed,
- zero answer-generation outcomes had been observed.

## Frozen candidate universe

The following already-frozen artifacts remain unchanged and authoritative:

- candidate-universe SHA-256: `a27ee40d3cacb77a1981c6fdf403affb11a9e669e6f2fbc808d7f14b1ff5d952`
- candidate-order SHA-256: `121c3e038b65ccca663e516db9a28d5cb2e1ac9f6aaaaed43587733ad436ce18`
- 10,000 candidates per theme for ECON, ENVI, HEAL, and TRAN.

The effective 10,000-record search window is retained rather than re-harvested. The final selection target remains 200 datasets per theme.

## V2.2 transport

Selection traverses the already-frozen `candidate_order.jsonl` without reordering candidates.

For each candidate reached by that deterministic traversal:

1. fetch the current data.europa.eu dataset-detail record from `GET /api/hub/search/datasets/{id}`;
2. store the raw JSON response locally before applying eligibility rules;
3. record SHA-256, retrieval timestamp, request URL, and response size for that detail record;
4. evaluate the frozen distribution-level eligibility rules;
5. retain the first two eligible distributions according to the frozen distribution SHA-256 order;
6. retain the dataset only if two eligible distributions survive all checks.

The detail snapshot is therefore part of the corpus provenance and is hash-addressed in the final pre-query freeze.

## Licence clarification before selection

The whitelist remains restricted to explicitly open licences. Before any C2 selection, authoritative licence vocabularies were checked and the following additional open identifiers were admitted:

- DCAT-AP CH `terms_open`;
- DCAT-AP CH `terms_by` (open use, attribution required);
- Datenlizenz Deutschland Namensnennung 2.0 (`dl-by-de/2.0`);
- Datenlizenz Deutschland Zero 2.0 (`dl-zero-de/2.0`).

Swiss `terms_ask` and `terms_by_ask` are not admitted because commercial use requires permission.

V2.2 additionally requires an explicit accepted licence at distribution level. Dataset-level inheritance is disabled for the confirmation corpus.

## Scientific protocol unchanged

This amendment changes metadata-detail transport and provenance capture only. It does not change:

- the four themes,
- target sample size,
- deterministic candidate order,
- retained distributions per dataset,
- 5 MiB distribution limit,
- 512-chunk cap,
- chunking rules,
- retrieval profiles,
- query target,
- confirmatory hypotheses,
- replay requirement,
- generator settings.

No observed C2 science result was available when this amendment was written.
