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
- tests that do not require the remote FOI test service

The JSON-LD mapping is an initial semantic representation, not yet a claim of full DCAT-AP conformance. Formal SHACL validation and controlled-vocabulary checks are a later milestone.

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
GET  /api/v1/datasets/{deployment_property_id}
GET  /api/v1/datasets/{deployment_property_id}.jsonld
```

The dataset endpoints currently generate catalog records from live Sensor Hub metadata. They fetch detailed source, location, deployment, property, and deployment-property records and join them into the canonical catalog model.

The search endpoint performs a small transparent weighted search over dataset title, observed property, location, source, publisher, semantic URI, and description. It is intentionally dependency-free for the current small catalog and can later be replaced by PostgreSQL full-text/trigram search if persistence becomes necessary.

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

The immediate next steps are live validation of catalog search across the current 25 dataset candidates and semantic validation of representative JSON-LD records. After that, SHACL/DCAT-AP validation is the main semantic milestone. Persistence can be introduced later if the catalog size or deployment model requires it. RAG routing comes after the catalog and search interfaces are stable.
