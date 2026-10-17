# C2 pre-query amendment 9: final materialization availability

Date: 2026-10-17

## Scope

This amendment is made before C2 query generation, retrieval evaluation, answer generation, or inspection of confirmatory outcomes.

The balanced target remains 100 theme-stratum records for each of ECON, ENVI, HEAL, and TRAN. All content eligibility, distribution, chunking, publisher-cap, candidate-order, and retrieval rules remain unchanged.

## Trigger

The first target-100 recovery retained the first 100 historical V2.4 selections for ECON and ENVI. During final payload reconstruction, all 100 ECON selections were materializable. Nine of the first 100 ENVI selections could not be materialized because every otherwise relevant distribution download attempt failed at the transport layer with connection errors to the EnviDat infrastructure. These failures occurred before any C2 retrieval result existed.

## Frozen recovery rule

The nine unavailable ENVI slots are not filled by a new candidate search and are not chosen using retrieval outcomes. They are filled from the already-preserved V2.4 ENVI selection trace beyond the target-100 cutoff.

1. Keep every successfully materialized ENVI selection among historical V2.4 selections 1--100.
2. Mark each missing first-100 ENVI selection as unavailable at final materialization and preserve its dataset identity, candidate rank, original selection number, and failure evidence.
3. Traverse historical V2.4 ENVI selections 101--125 in their original selection order.
4. A historical overflow selection may fill the next missing ENVI slot only if its preserved metadata-detail snapshot exists, its dataset identity and frozen candidate rank match, its distributions satisfy the unchanged frozen eligibility rules, and the rebuilt dataset chunk count exactly matches the chunk count recorded in the V2.4 selection log.
5. If an overflow selection cannot be materialized under those rules, record the failure and continue to the next already-selected V2.4 overflow row.
6. Stop after all missing ENVI slots are filled. Do not inspect later candidates once the balanced target is restored.
7. The final corpus freeze must report the replacement mapping and all skipped overflow attempts.

This rule preserves the original frozen candidate ordering and historical V2.4 selection decisions while avoiding post-hoc content or retrieval-based choice. It changes only the handling of datasets that cannot be physically reconstructed for the final pre-query corpus freeze.
