# PiPi Data Catalog

Semantic metadata catalog for the PiPi project (*Podatkovna Infrastruktura i Proširena Inteligencija za održivi razvoj*).

The catalog is intentionally separated from source systems. Sensor Hub and future providers keep their operational data, while this service harvests descriptive metadata and exposes a common catalog layer. The first provider is the PiPi Sensor Hub REST API.

## Current scope

The current vertical slice provides:

- FastAPI service with a health endpoint
- configurable Sensor Hub client
- Bearer-token authentication against `POST /auth/tokens`
- paginated metadata retrieval from locations, sources, deployments, properties, and deployment-properties
- metadata-only harvest preview without copying sensor readings
- one canonical catalog dataset per Sensor Hub deployment-property
- stable dataset identifiers such as `urn:pipi:dataset:sensor-hub:deployment-property:51`
- DCAT/DCAT-AP-oriented JSON-LD serialization
- QUDT links for known quantity kinds and units
- lightweight text search across canonical dataset metadata
- RDFLib + pySHACL validation against a local PiPi DCAT core profile
- tests that do not require the remote FOI test service

The local `pipi-dcat-core-shacl-v1` profile checks the structural semantic contract used by this catalog, including Dataset, Distribution and DataService links. It is intentionally a baseline profile and is not yet a claim of full official DCAT-AP conformance. Full DCAT-AP profile validation and controlled-vocabulary checks remain a later semantic milestone.

## Architecture

```text
PiPi Sensor Hub (GitLab / FOI)
        |
        | REST API
        v
SensorHubClient
        |
        v
SensorHubHarvester
        |
        v
CanonicalDataset
        |
        +--> DCAT / DCAT-AP-oriented JSON-LD
        +--> SHACL baseline validation
        +--> catalog API
        +--> lightweight catalog search
        +--> later RAG retrieval/routing
```

Operational measurements are not copied into the metadata catalog. The catalog stores and searches descriptions of available datasets and how to access them.

For the current Sensor Hub model, each `deployment-property` is treated as one initial dataset candidate because it binds a deployment to one measured property and carries the measurement configuration.

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
GET  /api/v1/providers/sensor-hub/status
GET  /api/v1/providers/sensor-hub/sources
POST /api/v1/harvest/sensor-hub/preview
GET  /api/v1/datasets
GET  /api/v1/search?q=temperature
GET  /api/v1/semantic/validation
GET  /api/v1/datasets/{deployment_property_id}
GET  /api/v1/datasets/{deployment_property_id}.jsonld
GET  /api/v1/datasets/{deployment_property_id}/validation
```

The dataset endpoints currently generate catalog records from live Sensor Hub metadata. They fetch detailed source, location, deployment, property, and deployment-property records and join them into the canonical catalog model.

The search endpoint performs a small transparent weighted search over dataset title, observed property, location, source, publisher, semantic URI, and description. It is intentionally dependency-light for the current small catalog and can later be replaced by PostgreSQL full-text/trigram search if persistence becomes necessary.

The semantic validation endpoints serialize canonical datasets to JSON-LD, parse them into RDF, and validate them with SHACL. `/api/v1/semantic/validation` checks all current catalog datasets and returns a compact per-dataset conformance report. The dataset-specific validation endpoint returns the detailed result for one deployment-property dataset.

The Sensor Hub `GET /readings` endpoint remains paginated as provided by the source system. Dataset-scoped reading filters are not required for the current catalog milestone. The JSON-LD records the Sensor Hub readings service as the access service and keeps `datasetScopedFilteringAvailable` as `false` so that the catalog does not advertise functionality that the source API does not provide.

## Tests

```bash
pytest
```

Remote connectivity can be checked after creating `.env` with valid test credentials:

```bash
python scripts/check_sensor_hub.py
```

## Next milestones

The current live search over the 25 Sensor Hub dataset candidates has been validated for representative queries such as `temperature`, `humidity`, `FOI`, and `ucionica`. The next live check is the SHACL baseline report across all current datasets. After that, the main semantic step is validation against the official DCAT-AP profile and controlled vocabularies. Persistence can be introduced later if the catalog size or deployment model requires it. RAG routing comes after the catalog and search interfaces are stable.
