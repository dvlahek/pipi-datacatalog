# Second-corpus V1 supersession record

Date: 2026-10-17

Protocol V1 and its initial bootstrap are superseded by V2 before any C2 dataset was selected and before any C2 retrieval, generation, answer-drift, or replay result was observed.

The V1 run reached only metadata discovery for ENVI. Both public SPARQL endpoints returned gateway timeouts. The log contained no `SELECT` event and no snapshot manifest was frozen.

V2 was therefore defined as a pre-result methodological amendment, not a result-dependent tuning step.

Changes frozen in V2:

- metadata acquisition through the documented data.europa.eu CKAN-compatible `package_search` API;
- candidate-universe and hash-order freeze before distribution download;
- `download_url` only, with no `accessURL` substitution;
- explicit open-licence whitelist;
- deterministic distribution ordering and attrition ledger;
- exactly two eligible distributions per selected dataset;
- 5 MiB payload ceiling and 512-chunk eligibility ceiling with no truncation;
- reuse of the C1 extraction/chunking semantics for PDF, TXT, HTML, JSON, and CSV;
- XML exclusion because C1 did not have a dedicated XML extraction path;
- prospective evidence-multiplicity mechanism hypothesis;
- C2 answer drift reclassified as secondary/descriptive, while granularity, multiplicity, and exact replay are confirmatory outcomes.

No V1 C2 science result is retained or relabelled because no V1 C2 science result existed.
