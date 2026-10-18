# C2 pre-result amendment 8: unavailable metadata-detail responses

**Date:** 2026-10-17  
**Revision:** V2.5  
**Scope:** transport/acquisition handling only  
**Status:** before corpus freeze, query authoring, retrieval evaluation, generation, or C2 statistical analysis

## Trigger

The V2.4 selector reached the ENVI theme after completing the provisional ECON target and then stopped at ENVI candidate rank 1937. The modern data.europa.eu dataset-detail endpoint returned HTTP 403 for that frozen candidate. The V2.2 core treated every non-retryable metadata-detail HTTP response as fatal and aborted the entire corpus build.

No `corpus_freeze.json` had been produced. No C2 query set, retrieval result, generated answer, or confirmatory statistic existed.

## Problem

A metadata-detail response can be unavailable for an individual frozen candidate even though the candidate universe and order remain valid. Treating one unavailable detail response as fatal is inconsistent with deterministic traversal of the frozen candidate pool and with the attrition-ledger design. It also differs from the already frozen distribution-level rule, under which an unavailable/ineligible item is recorded and traversal continues without manual replacement.

## V2.5 correction

V2.5 preserves the candidate universe, candidate order, selection target, publisher cap, licence rules, `downloadURL`-only rule, size cap, supported formats, extraction/chunking rules, two-distribution requirement, query target, and all C2 hypotheses.

Only metadata-detail transport handling changes:

1. HTTP 200 detail responses are processed exactly as before.
2. Retryable/transient detail failures retain the frozen bounded retry behavior.
3. A non-retryable detail HTTP response is snapshotted with status and response hash, recorded as dataset-level `detail_unavailable` attrition, and the selector continues to the next frozen candidate.
4. If transient metadata-detail retries are exhausted, the failure is snapshotted, recorded as dataset-level `detail_unavailable` attrition, and traversal continues.
5. No candidate is manually substituted or reordered.

The V2.4 distribution-level `record_and_skip_distribution` policy remains unchanged.

## Scientific effect

This amendment does not change scientific eligibility or tune the corpus using C2 outcomes. It corrects a fatal transport behavior so that an unassessable candidate is represented transparently in attrition instead of terminating the entire deterministic selection process.

All final C2 pre-query artifacts will hash the V2.5 driver, V2.5 config, unchanged frozen candidate universe/order, metadata-detail manifest, selected-corpus manifest, attrition ledger, chunk manifest, environment manifest, and final corpus freeze.
