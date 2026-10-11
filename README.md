# PiPi Data Catalog

Semantic metadata catalog for the PiPi project (*Podatkovna Infrastruktura i Proširena Inteligencija za održivi razvoj*).

The catalog is intentionally separated from source systems. Sensor Hub and future providers keep their operational data, while this service harvests descriptive metadata and exposes a common catalog layer. The first provider is the PiPi Sensor Hub REST API.

## Current scope

The first vertical slice provides:

- FastAPI service with a health endpoint
- configurable Sensor Hub client
- Bearer-token authentication against `POST /auth/tokens`
- paginated metadata retrieval from locations, sources, deployments, properties, and deployment-properties
- a harvest preview endpoint that reports discovered metadata without copying sensor readings
- unit tests that do not require the remote FOI test service

The semantic layer (DCAT-AP, SOSA/SSN, QUDT and JSON-LD serialization) will be added on top of this provider-neutral harvesting boundary.

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
canonical catalog model
        |
        +--> DCAT-AP / JSON-LD
        +--> catalog search
        +--> later RAG retrieval/routing
```

Operational measurements are not copied into the metadata catalog. The catalog stores and indexes descriptions of available datasets and how to access them.

## Development setup

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
```

The preview endpoint authenticates to Sensor Hub and reads all pages of metadata resources. It deliberately does not retrieve `/readings`.

## Tests

```bash
pytest
```

Remote connectivity can be checked after creating `.env` with valid test credentials:

```bash
python scripts/check_sensor_hub.py
```

## Next milestone

Transform harvested Sensor Hub metadata into a provider-neutral catalog model and serialize the first datasets as DCAT-AP-compatible JSON-LD, with SOSA/SSN links for sensing concepts and QUDT URIs for quantity kinds and units.
