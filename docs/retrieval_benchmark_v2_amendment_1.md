# PiPi Retrieval Benchmark V2 — Protocol Amendment 1

Status: **adopted before V2 query authoring and before confirmation retrieval results**

This amendment updates the V2 benchmark design after the preregistered corpus-capacity gate exposed insufficient source diversity in two of the original three source families. No V2 confirmation query had been authored and no V2 confirmation retrieval result had been inspected when this amendment was adopted.

## Reason for the amendment

The first capacity audit found:

- `structured-data`: 1 indexed dataset with 3 chunks for an 80-query quota
- `software-documentation`: 100 unique source files and 1436 chunks for an 80-query quota
- `institutional-documents`: 3 indexed documents with 48 chunks for an 80-query quota

The structured and institutional families therefore had a high target-reuse risk. Reducing the evidence-diversity standard after seeing this result would weaken the benchmark. Instead, PiPi expands the Data Space before query authoring.

At the same time, the project adds a fourth first-class family, `open-data-catalogs`, harvested from external CKAN/DCAT catalogs into the same versioned PiPi catalog. This addition is methodologically aligned with the Data Space setting and is not a benchmark-only corpus.

## Revised benchmark allocation

The total remains 240 queries.

| Source family | Development | Confirmation | Total |
|---|---:|---:|---:|
| structured-data | 12 | 48 | 60 |
| software-documentation | 12 | 48 | 60 |
| institutional-documents | 12 | 48 | 60 |
| open-data-catalogs | 12 | 48 | 60 |
| **Total** | **48** | **192** | **240** |

The six query types remain unchanged. Each type has 8 development and 32 confirmation queries, for 40 queries overall.

Every source-family × query-type cell contains 2 development and 8 confirmation queries. This produces 24 balanced cells.

## Cross-language allocation

The overall benchmark remains 30% cross-language:

- development: 24 cross-language + 24 same-language
- confirmation: 48 cross-language + 144 same-language
- overall: 72 cross-language + 168 same-language

Each cell contains one cross-language development query and two cross-language confirmation queries.

## Metadata-first evidence boundary

Two families use metadata-first RAG evidence by design:

- Sensor Hub datasets are indexed from catalog metadata. Raw observation streams are not copied into the text RAG corpus.
- Open-data catalog datasets are indexed from harvested metadata. External dataset payloads remain linked distributions and are not downloaded solely for benchmark construction.

This preserves the architectural boundary between Data Space metadata and operational/source payloads.

## Capacity gate after expansion

Before any V2 query authoring starts, the revised capacity audit must pass for all four source families. The minimum coarse evidence-diversity ratio remains 0.40 relative to each family's 60-query quota.

This implies at least 24 coarse diversity units per family under the current audit definition. Software documentation uses unique files as diversity units. The other three families use indexed versioned datasets/documents.

## Relevance and statistics

The 0–3 relevance scale, nDCG@10 primary quality metric, frozen profile contrasts, paired bootstrap confidence intervals, paired Wilcoxon tests, rank-biserial effect size, Holm correction, and drift metrics remain unchanged.

The double-annotation target changes from 54 to 48 confirmation queries: exactly two queries from each of the 24 source-family × query-type cells, stratified across language relation where possible.

## Provenance

The machine-readable protocol is `config/rag_benchmark_v2_protocol.json`, revision 2. Final V2 execution remains bound to the frozen catalog snapshot, retrieval-profile hashes, benchmark and judgment file hashes, and Git commit SHA.
