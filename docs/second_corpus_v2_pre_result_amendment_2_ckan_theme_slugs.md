# Second-corpus V2 pre-result amendment 2: CKAN theme slugs

Date: 2026-10-17
Protocol: `SECOND_CORPUS_DATAEUROPA_V2`
Status: PRE-RESULT / PRE-SELECTION

## Trigger

The first V2 harvest attempt called the public data.europa.eu CKAN-compatible `package_search` endpoint with `fq=groups:econ`. The endpoint returned zero rows for ECON and the bootstrap aborted with `EMPTY_CANDIDATE_UNIVERSE theme=ECON`.

No candidate universe was frozen, no dataset was selected, no distribution was downloaded under V2, and no retrieval, answer-generation, relevance, churn, replay, or answer-drift outcome was observed.

## Cause

The configuration used DCAT controlled-vocabulary abbreviations (`ECON`, `ENVI`, `HEAL`, `TRAN`) as if they were CKAN group names. In the data.europa.eu CKAN representation, thematic categories are exposed through human-readable CKAN group slugs. The official package-search example represents the category `Economy and finance` with `groups[].name = "economy-and-finance"`.

## Amendment

Only the metadata-harvest mapping from protocol theme codes to CKAN group slugs is changed:

- `ECON -> economy-and-finance`
- `ENVI -> environment`
- `HEAL -> health`
- `TRAN -> transport`

The frozen protocol theme codes, target counts, deterministic SHA-256 ordering, publisher cap, distribution eligibility rules, open-license rules, downloadURL-only rule, file-size limit, chunk-count limit, chunking rules, query target, retrieval profiles, generators, statistical hypotheses, and decision rules are unchanged.

## Scientific status

This is a schema/transport correction made before any C2 corpus selection or scientific outcome. It is not result-dependent tuning. The failed zero-row harvest log should be retained as provenance of the amendment.
