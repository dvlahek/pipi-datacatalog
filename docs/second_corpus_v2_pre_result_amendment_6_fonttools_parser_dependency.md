# C2 V2 pre-result amendment 6: fontTools parser dependency

Date: 2026-10-17

Status: pre-query, pre-retrieval, pre-corpus-freeze implementation correction.

## Trigger

During the first corrected V2.2 selection run, `pypdf==6.21.0` emitted repeated warnings that `fontTools` was required to fully parse the encoding of CFF Type1 fonts in some candidate PDFs. The run was stopped after four provisional ECON selections and before creation of `corpus_freeze.json`. No C2 query set, retrieval result, generator output, or confirmation statistic had been produced.

The warning exposes a parser-environment dependency that can affect canonical PDF text extraction. Because canonical extracted text and downstream chunks are part of the indexing provenance `P_i`, all selected C2 distributions must be processed under one frozen parser environment.

## Frozen correction

Transport revision V2.3 adds the exact dependency:

- `fontTools==4.67.0`
- `pypdf==6.21.0`
- `requests==2.34.2`

The V2.3 selector driver refuses to start unless the installed dependency versions exactly match the frozen configuration. It also verifies its own SHA-256, writes a deterministic parser-environment manifest, verifies that manifest SHA-256, and includes the parser driver, deterministic V2.2 selection core, parser manifest, corpus artifacts, and final freeze in `SHA256SUMS.prequery.txt`.

## What does not change

This amendment does not change:

- scientific protocol `SECOND_CORPUS_DATAEUROPA_V2`
- frozen candidate universe or candidate order
- theme strata
- target of 200 selected datasets per theme
- requirement for exactly two eligible distributions per selected dataset
- distribution-level open-license rule
- downloadURL-only rule
- 5 MiB distribution limit
- supported formats
- chunk size, overlap, CSV row chunking, or 512-chunk ceiling
- publisher cap
- query target or confirmatory hypotheses

Frozen candidate hashes remain:

- candidate universe SHA-256: `a27ee40d3cacb77a1981c6fdf403affb11a9e669e6f2fbc808d7f14b1ff5d952`
- candidate order SHA-256: `121c3e038b65ccca663e516db9a28d5cb2e1ac9f6aaaaed43587733ad436ce18`

## Restart rule

The V2.3 selection restarts deterministically from candidate rank 0. Existing metadata-detail snapshots may be reused because they are API metadata snapshots and are independent of PDF parsing. Provisional raw payloads, canonical text, selected-corpus manifest, attrition ledger, and chunk manifest are regenerated from scratch by the selector before the final corpus freeze.

This correction was made before any C2 corpus freeze, query freeze, retrieval evaluation, generation, or confirmatory result was observed.
