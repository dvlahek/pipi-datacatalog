# PiPi Data Catalog

Semantic metadata catalog for the PiPi project (*Podatkovna Infrastruktura i Proširena Inteligencija za održivi razvoj*).

The catalog is separated from source systems. Sensor Hub and future providers keep their operational data, while this service harvests or registers descriptive metadata and exposes a common catalog layer.

## Current scope

The current vertical slice provides:

- FastAPI service with a health endpoint
- configurable Sensor Hub client
- Bearer-token authentication against `POST /auth/tokens`
- paginated metadata retrieval from locations, sources, deployments, properties, and deployment-properties
- metadata-only harvesting without copying sensor readings
- one initial Sensor Hub dataset per deployment-property
- a provider-neutral canonical dataset core with optional domain extensions
- explicit `Distribution` objects for API, file, image, audio, video and future access modes
- stable dataset identifiers such as `urn:pipi:dataset:sensor-hub:deployment-property:51`
- PostgreSQL-backed persistent metadata catalog with idempotent upsert
- immutable catalog version snapshots when normalized metadata or source fingerprints change
- explicit source provenance fields for URL, ETag, Last-Modified, content SHA-256 and provider-native version
- explicit catalog synchronization from configured providers
- DCAT/DCAT-AP-oriented JSON-LD serialization
- QUDT links for known quantity kinds and units
- lightweight text search across heterogeneous catalog metadata
- RDFLib + pySHACL validation against a local PiPi DCAT core profile
- a manually registered external live webcam dataset for Varaždin
- tests that do not require the remote FOI test service

The local `pipi-dcat-core-shacl-v2` profile checks the provider-neutral structural contract used by this catalog, including Dataset, Distribution and optional DataService links. It is a baseline profile. Passing this local profile must not be reported as full DCAT-AP conformance. Validation against the official DCAT-AP profile and controlled-vocabulary requirements remains a later semantic milestone.

## Architecture

```text
Sensor Hub API ---------\
REST/JSON APIs ----------\
CSV/files ----------------> provider adapters --> CanonicalDataset --> version-aware sync/upsert
Text/document sources ---/                                                   |
Audio/video streams ----/                                                    v
Static web resources ---/                                               PostgreSQL
                                                                            |
                                                 +--------------------------+------------------+
                                                 |                          |                  |
                                              catalog API                 search            DCAT/SHACL
                                                                                                |
                                                                                            later RAG
```

Operational content is not copied into the metadata catalog by default. PostgreSQL stores normalized metadata, provenance, version snapshots and distribution descriptors. Sensor readings remain in Sensor Hub, HLS video remains on the external CDN, and future CSV/audio/text payloads can remain at their source unless a provider explicitly implements content ingestion.

For the current Sensor Hub model, each `deployment-property` is treated as one initial dataset candidate because it binds a deployment to one measured property and carries the measurement configuration.

The canonical model is no longer sensor-specific. Sensor metadata is an optional extension. Other providers can describe datasets using the common fields plus one or more distributions, for example JSON API access, CSV download, text document, audio file, HLS video stream or image snapshot.

## Persistent catalog and versioning

Persistence is optional so the service can still run in the earlier live-discovery mode. Enable PostgreSQL in `.env`:

```env
CATALOG_STORE_ENABLED=true
DATABASE_URL=postgresql+psycopg://pipi:pipi_dev@localhost:5432/pipi_catalog
CATALOG_BOOTSTRAP_IF_EMPTY=true
```

The repository includes a local development PostgreSQL service:

```bash
docker compose up -d postgres
```

The store creates three core tables for the MVP:

- `catalog_datasets` - current provider-neutral dataset metadata and provenance
- `catalog_distributions` - current API/file/image/audio/video access representations
- `catalog_dataset_versions` - immutable historical snapshots with SHA-256 fingerprints

`POST /api/v1/catalog/sync` discovers all configured providers and performs a version-aware idempotent upsert. If the canonical snapshot is unchanged, no new version is created. If metadata, distributions or source-version signals change, the current row is updated and a new immutable version snapshot is appended.

For file-like providers such as CSV, text or audio, the provider should compute a SHA-256 of the source bytes and put it into `provenance.content_sha256`. Therefore a CSV can keep the same URL, filename and title while changed rows still produce a new catalog version at the next sync. HTTP providers can additionally preserve `ETag` and `Last-Modified`; provider-native version ids can be stored in `provenance.source_version`.

For continuously changing resources such as an HLS live camera, the stream bytes are deliberately not hashed. Versioning tracks the stable catalog metadata and access configuration instead of creating a new version for every video segment.

If persistence is enabled and the database is empty, `CATALOG_BOOTSTRAP_IF_EMPTY=true` allows the first read to bootstrap the store once. Later refreshes should use the explicit sync endpoint.

## Registered external webcam

The first non-Sensor-Hub provider is a manually registered WhatsUpCams Varaždin webcam. It is represented as one dataset with two distributions:

- live HLS stream: `application/vnd.apple.mpegurl`
- current snapshot: `image/jpeg`

The original player declares the HLS source as `application/x-mpegURL`. The catalog preserves that original media-type declaration as provider metadata while using the standardized HLS media type in the DCAT distribution.

The catalog does not proxy or archive the video. PostgreSQL stores only the normalized webcam metadata and the external access URLs. The license is currently recorded as `unknown` until usage terms are explicitly established.

## Development setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Swagger UI for the catalog will then be available at `http://127.0.0.1:8000/docs`.

## Sensor Hub configuration

The FOI testing service currently exposes the Sensor Hub API below `/api/v1`. Configure credentials only in a local `.env` file or deployment secrets. Do not commit real credentials.

```env
SENSOR_HUB_BASE_URL=http://webtesting.foi.unizg.hr:3000/api/v1
SENSOR_HUB_USERNAME=your-test-user
SENSOR_HUB_PASSWORD=your-test-password
SENSOR_HUB_TIMEOUT_SECONDS=15
```

The `.env` file is ignored by Git.

## Endpoints in this service

```text
GET  /health
GET  /api/v1/providers
GET  /api/v1/catalog/status
POST /api/v1/catalog/sync
GET  /api/v1/providers/sensor-hub/status
GET  /api/v1/providers/sensor-hub/sources
POST /api/v1/harvest/sensor-hub/preview
GET  /api/v1/datasets
GET  /api/v1/search?q=temperature
GET  /api/v1/search?q=camera
GET  /api/v1/semantic/validation
GET  /api/v1/datasets/{dataset_ref}
GET  /api/v1/datasets/{dataset_ref}.jsonld
GET  /api/v1/datasets/{dataset_ref}/validation
GET  /api/v1/datasets/{dataset_ref}/versions
GET  /api/v1/datasets/{dataset_ref}/versions/{version}
```

`dataset_ref` can be a Sensor Hub deployment-property id such as `1`, an external id such as `hr_varazdin1`, or a catalog id such as `webcam:whatsupcams:hr_varazdin1`.

When PostgreSQL is enabled, `/datasets`, `/search`, `/semantic/validation` and individual dataset endpoints read the persisted catalog. `POST /api/v1/catalog/sync` refreshes that catalog from Sensor Hub plus registered external providers. Version endpoints expose the immutable history retained by the store.

The search endpoint performs a small transparent weighted search over title, keywords, observed property, location, source, provider, dataset type, media type and description. It can later be moved to PostgreSQL full-text/trigram indexing without changing the public API.

Live search validation against the original 25 Sensor Hub datasets returned 6 matches for `temperature`, 5 for `humidity`, 16 for `FOI`, and 2 for `ucionica`. The external webcam adds a new heterogeneous dataset without changing the Sensor Hub source system.

The semantic validation endpoints serialize canonical datasets to JSON-LD, parse them into RDF, and validate them with SHACL. `/api/v1/semantic/validation` checks the complete current multi-provider catalog.

The Sensor Hub `GET /readings` endpoint remains paginated as provided by the source system. Dataset-scoped reading filters are not required for the current catalog milestone. The JSON-LD keeps `datasetScopedFilteringAvailable=false` for those distributions so the catalog does not advertise functionality the source API does not provide.

## Tests

```bash
pytest
```

Remote Sensor Hub connectivity can be checked after creating `.env` with valid test credentials:

```bash
python scripts/check_sensor_hub.py
```

## Next milestones

The next architectural step is configuration-driven provider registration and provider-failure isolation so one unavailable external API does not take down catalog synchronization. After that, add concrete providers for CSV/files, generic REST/JSON, text/document sources and audio. Search can move into PostgreSQL full-text/trigram indexing when catalog size justifies it. Official DCAT-AP validation and controlled vocabularies remain the main semantic milestone. RAG routing comes after the provider-neutral catalog and sync interfaces are stable.
