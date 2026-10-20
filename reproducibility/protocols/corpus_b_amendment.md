# Second-Corpus Confirmation Protocol V2 - Corpus-Size Amendment

**Documentation date:** 2026-10-18  
**Base protocol commit:** `3f1e2adabe12d2697f3a3bf5c66749fc9d097274`  
**Base protocol commit time:** 2026-10-17 06:55 UTC  
**Scope:** second-corpus sample-size target only

## Terminology

A **selection record** is one stratum-specific inclusion of a source dataset. It is a sampling unit, not a retrieval-provenance identity. The final design contains 400 selection records but 397 unique dataset identifiers because three datasets occur in two topical strata. Dataset-level retrieval identity uses the dataset identifier. Each selection record contributes exactly two retained eligible distributions.

## Reason for this amendment

The V2 protocol set a target of 800 selection records, 200 per topical stratum. During corpus-construction feasibility testing, the target was reduced to 400 selection records, 100 per stratum. The reduction was made before query authoring, retrieval evaluation, or inspection of the confirmatory outcomes.

This file documents that operational change explicitly. It does not backdate its own creation time.

## What changed

| Field | V2 protocol | Final design |
| --- | ---: | ---: |
| Selection records | 800 | 400 |
| Selection records per topical stratum | 200 | 100 |
| Unique dataset identifiers | not a changed target | 397 |

The final corpus therefore contains 400 stratum-specific selection records corresponding to 397 unique dataset identifiers. Each accepted selection record contributes exactly two retained eligible distributions, for 800 retained distributions in total.

## What did not change

The following rules were already present in commit `3f1e2adabe12d2697f3a3bf5c66749fc9d097274` and are not amendments:

- exactly two retained eligible distributions per accepted selection record;
- supported formats PDF, TXT, CSV, JSON, HTML, and XHTML, with XML excluded;
- one to 512 chunks per eligible distribution, with distributions above the limit excluded rather than truncated;
- a maximum of 20 selection records per normalized publisher key per topical stratum;
- row-preserving CSV chunking, with one non-empty data row represented as one chunk;
- the four topical strata, six query types, and 96-query design;
- the content-versus-metadata retrieval intervention;
- H1, H2, and H3 and their analysis rules;
- dataset, distribution, and chunk identity definitions;
- exact ordered-evidence replay as the H3 endpoint.

No confirmatory hypothesis, retrieval parameter, identity definition, or replay criterion was changed by the sample-size reduction.