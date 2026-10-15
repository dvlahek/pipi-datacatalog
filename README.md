# PiPi Data Catalog

Semantic Data Space catalog and reproducible RAG research prototype for the PiPi project (*Podatkovna Infrastruktura i Proširena Inteligencija za održivi razvoj*).

PiPi keeps source systems independent. Providers keep their operational data, while the catalog harvests or registers descriptive metadata, versions the catalog state, exposes common DCAT-oriented metadata, and supports retrieval over heterogeneous resources.

## Current scope

The branch `feature/sensor-hub-bootstrap` currently includes:

- FastAPI catalog API and browser portal
- provider-neutral `CanonicalDataset` and `Distribution` models
- Sensor Hub, CSV/file, document, static-web and registered external-resource ingestion
- PostgreSQL persistence with immutable dataset-version history
- source provenance fields for URL, ETag, Last-Modified, content SHA-256 and provider-native versions
- versioned SQL migrations with checksum protection
- authenticated resource registration and refresh
- bounded remote fetching and SSRF-oriented URL validation
- DCAT/DCAT-AP-oriented JSON-LD
- QUDT links for known quantities and units
- local SHACL validation against the PiPi DCAT core profile
- RAG document/chunk storage
- lexical, dense-vector and hybrid retrieval
- immutable retrieval profiles and embedding identities
- exact pgvector cosine retrieval and deterministic RRF fusion
- retrieval ledgers and strict replay checks
- PiPi Benchmark V2 for retrieval-provenance and answer-drift experiments

The local `pipi-dcat-core-shacl-v2` profile is a project structural profile. Passing it must not be reported as full DCAT-AP conformance.

## Architecture

```text
Sensor Hub API ---------\
REST/JSON APIs ----------\
CSV/files ----------------> provider adapters --> CanonicalDataset --> version-aware catalog
Documents/web ----------/                                             |
External resources -----/                                              v
                                                                  PostgreSQL
                                                                      |
                        +----------------------+-----------------------+------------------+
                        |                      |                       |                  |
                   catalog API             DCAT/SHACL             RAG chunks       provenance
                                                                      |
                                             +------------------------+------------------+
                                             |                        |                  |
                                          lexical                 dense vector        hybrid RRF
                                             \                        |                  /
                                              +---- immutable RetrievalProfile --------+
                                                                 |
                                                           retrieval ledger
                                                                 |
                                                           grounded context
```

A central research principle of this repository is that reproducible RAG requires provenance for the retrieval configuration that selected the evidence, not only provenance for the underlying data.

## Database migrations

Applied migrations are immutable. A changed applied migration is treated as an error instead of silently rewriting schema history.

Current migration chain:

```text
001_catalog_core.sql
002_catalog_versions.sql
003_resource_registry.sql
004_rag_documents_chunks.sql
005_harvest_runs.sql
006_rag_jobs_activity.sql
007_rag_vector_embeddings.sql
008_retrieval_profiles_and_embeddings.sql
```

Initialize or update the local database with:

```bash
python scripts/init_database.py
```

Typical local configuration:

```env
CATALOG_STORE_ENABLED=true
DATABASE_URL=postgresql+psycopg://pipi:pipi_dev@localhost:5432/pipi_catalog
CATALOG_BOOTSTRAP_IF_EMPTY=true
```

Keep administrator credentials and provider credentials only in `.env` or deployment secrets. Do not commit them.

## Development setup

Python 3.11+ is recommended for the application.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python scripts/init_database.py
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
python .\scripts\init_database.py
uvicorn app.main:app --reload
```

Swagger UI is available at `http://127.0.0.1:8000/docs`.

Embedding experiments use the separate dependency file:

```bash
python -m pip install -r requirements-embeddings.txt
```

## Catalog and RAG

Catalog synchronization is version-aware and idempotent. A changed normalized dataset snapshot creates a new immutable dataset version. File-like providers can use `provenance.content_sha256` so changed bytes create a new version even when the URL and filename do not change.

RAG storage is separated from the canonical catalog. Documents and chunks retain the dataset/version identity from which they were derived. Embeddings are keyed by an explicit embedding identity, allowing multiple representations and embedding families to coexist for the same chunk.

The frozen Benchmark V2 E5 profiles compare:

- lexical retrieval
- dense vector retrieval over content
- dense vector retrieval over content plus semantic/catalog metadata
- hybrid lexical + vector retrieval over content
- hybrid lexical + vector retrieval over content plus semantic/catalog metadata

Hybrid retrieval uses deterministic reciprocal-rank fusion and a source/file soft cap. Retrieval profiles are versioned and hashed.

## PiPi Benchmark V2

The frozen confirmation benchmark contains 192 queries over a heterogeneous 274-dataset / 3,974-chunk corpus spanning structured sensor data, software documentation, institutional documents and Croatian open-data records.

Primary E5 confirmation results:

| Profile | nDCG@10 |
|---|---:|
| lexical | 0.4891 |
| vector content | 0.7013 |
| hybrid content | 0.6712 |
| vector metadata | **0.7759** |
| hybrid metadata | **0.6996** |

The preregistered hybrid metadata-minus-content contrast was:

- ΔnDCG@10 = **+0.0284**
- 95% bootstrap CI = **[+0.0134, +0.0441]**
- Wilcoxon p = **0.000967**
- rank-biserial = **0.369**

Strict replay reproduced the exact ordered evidence set for **960/960** frozen retrieval runs.

Across three local generator families, changing only the frozen retrieval profile produced material semantic answer differences in approximately **10.4–11.5%** of confirmation queries, while same-evidence deterministic controls were exact in **144/144** runs.

### BGE-M3 robustness

A post-hoc robustness analysis repeated the representation comparison using a second multilingual embedding family, `BAAI/bge-m3`, while preserving the frozen corpus, 192 confirmation queries, evaluation depth, diversity rule and hybrid RRF parameters.

| Backbone | Retrieval | Content nDCG@10 | Metadata nDCG@10 | Δ metadata-content |
|---|---|---:|---:|---:|
| E5 | vector | 0.7013 | 0.7759 | +0.0745 |
| E5 | hybrid | 0.6712 | 0.6996 | +0.0284 |
| BGE-M3 | vector | 0.7393 | **0.8330** | **+0.0937** |
| BGE-M3 | hybrid | 0.6686 | **0.7035** | **+0.0349** |

For BGE-M3, the vector contrast had a 95% bootstrap CI of `[+0.0678, +0.1209]` and the hybrid contrast `[+0.0217, +0.0484]`. The BGE-M3 analysis is explicitly post-hoc robustness evidence. It does not replace the frozen E5 confirmation experiment.

See:

- `docs/benchmark_v2_results_ready_synthesis_20261015.md`
- `docs/benchmark_v2_reproducibility_20261015.md`
- `config/rag_benchmark_v2_bge_m3_robustness.json`
- `scripts/run_benchmark_v2_bge_m3_robustness.py`
- `data/benchmark_v2/`

## Reproducibility boundaries

The repository separates three evidence layers:

1. **Primary frozen confirmation** — preregistered E5 retrieval profiles, frozen query set, frozen qrels and strict replay.
2. **Answer-drift replication** — three local generator families under deterministic generation settings.
3. **Post-hoc robustness** — BGE-M3 second-backbone retrieval analysis.

The semantic-drift endpoint is symmetric: it establishes that the answer changed materially, not that one answer was necessarily more correct.

The benchmark is still based on one deployed heterogeneous Data Space. BGE-M3 reduces dependence on one embedding family but does not establish corpus-independent generalization.

## Tests

```bash
pytest
```

Remote provider checks require local credentials and are intentionally separate from the offline test suite.

## Research roadmap

The current paper line focuses on retrieval provenance and reproducible RAG over an evolving Data Space.

The next research phase is a controlled executable-analytics layer:

```text
natural-language request
    -> Data Space discovery
    -> dataset/schema selection
    -> versioned analysis specification
    -> sandboxed SQL/Python execution
    -> result hash and computational provenance
    -> grounded answer
```

This phase will extend the provenance chain from data and retrieval provenance to computational provenance, including aggregation, statistical analysis and controlled machine-learning tasks. Generated code will not execute directly against the Data Space without validation, resource limits and an isolated execution environment.

## Security

Read `SECURITY.md` before deploying the service. Production deployment should use HTTPS, secret storage, private database networking and network-level outbound-egress controls in addition to application-level URL checks.
