# Second-corpus V2 pre-result amendment 5: detail identity field fix

Date: 2026-10-17

## Status

Pre-result implementation correction. No second-corpus dataset had been accepted into the final corpus, no distribution payload had been retained in the final corpus, and no retrieval or generation result had been produced when this correction was made.

## Observed failure

The first V2.2 selection attempt processed 3,335 ECON detail records and accepted zero datasets. The attrition ledger contained 3,322 `detail_identity_mismatch` rejections.

The mismatch was caused by using the generic `stable_id()` helper for dataset-detail identity validation. That helper intentionally prefers `resource`/URI-like identifiers before `id`. The modern data.europa.eu detail endpoint is addressed as `GET /datasets/{id}` and its canonical request identity is the explicit top-level `id` field. Consequently, comparing the generic `stable_id(detail)` value to the frozen candidate `dataset_id` incorrectly rejected valid detail records when `resource` and `id` were both present.

## Correction

The selector now validates detail identity against the explicit top-level `id` field only:

- frozen candidate order is unchanged;
- frozen candidate IDs are unchanged;
- candidate-universe and candidate-order hashes are unchanged;
- cached detail responses remain valid and are reused;
- the old attrition ledger is regenerated from zero on rerun;
- no eligibility, license, format, size, chunk-count, publisher, theme, or target rule is changed.

The selector now also emits a progress line every 100 attempted candidates. This logging change has no effect on selection.

## Scientific impact

None. This correction changes only the implementation of the identity consistency check between an already-frozen candidate ID and the corresponding metadata-detail response. It was made before the first accepted C2 dataset and before any C2 retrieval evaluation.
