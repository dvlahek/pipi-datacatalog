# Corpus B sample-size amendment

**Documentation date:** 2026-10-18  
**Base protocol commit:** `3f1e2adabe12d2697f3a3bf5c66749fc9d097274`  
**Base protocol commit time:** 2026-10-17 06:55 UTC  
**Scope:** corpus-B sample-size target

This note records the only change to the planned corpus-B sample size after the V2 confirmation protocol had been written.

## Sampling terminology

A **selection record** is one inclusion of a source dataset in one topical stratum. It is a sampling unit, not a retrieval-provenance identity. Dataset-level provenance uses the dataset identifier. Each accepted selection record contributes exactly two retained eligible distributions.

The final design contains 400 selection records but 397 unique dataset identifiers because three datasets occur in two topical strata.

## Amendment

The V2 protocol originally targeted 800 selection records, with 200 records in each of four topical strata. During corpus-construction feasibility testing, the target was reduced to 400 selection records, with 100 per stratum.

The decision was made before query authoring, retrieval evaluation, or inspection of confirmatory outcomes.

| Field | V2 protocol | Final design |
| --- | ---: | ---: |
| Selection records | 800 | 400 |
| Selection records per topical stratum | 200 | 100 |
| Unique dataset identifiers | not a separate target | 397 |

With two retained eligible distributions per selection record, the final corpus contains 800 retained distributions.

## Protocol elements that were unchanged

The sample-size amendment did not change:

- the requirement for exactly two retained eligible distributions per accepted selection record;
- the supported formats PDF, TXT, CSV, JSON, HTML, and XHTML, with XML excluded;
- the eligibility range of one to 512 chunks per distribution, with larger distributions excluded rather than truncated;
- the cap of 20 selection records per normalized publisher key within each topical stratum;
- row-preserving CSV chunking, with each non-empty data row represented as one chunk;
- the four topical strata, six query types, and 96-query design;
- the content-versus-metadata retrieval intervention;
- H1, H2, and H3 and their analysis rules;
- the dataset, distribution, and chunk identity definitions;
- exact ordered-evidence replay as the H3 endpoint.

No hypothesis, retrieval parameter, provenance identity, or replay criterion was changed by the sample-size reduction.