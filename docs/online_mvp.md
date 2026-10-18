# Online PiPi dataspace MVP

The current branch supports an authenticated single-application prototype suitable for deployment behind HTTPS.

## User flow

1. Open `/portal/`.
2. Sign in with the configured administrator credentials.
3. Browse and search the persisted catalog.
4. Submit a public resource URL.
5. The server validates the URL against the resource security policy.
6. The server fetches the resource within configured timeout and size limits.
7. The resource type is detected and normalized to `CanonicalDataset` metadata.
8. Source provenance is recorded, including content SHA-256 for bounded file-like content.
9. The normalized dataset is upserted into PostgreSQL and receives immutable version history.
10. Refreshing the registered resource repeats the probe. A meaningful source change creates a new dataset version.

Registered resources can be disabled without deleting their catalog metadata or version history.

## Resource API

```text
GET    /api/v1/resources
POST   /api/v1/resources
GET    /api/v1/resources/{id}
POST   /api/v1/resources/{id}/refresh
POST   /api/v1/resources/{id}/enable
DELETE /api/v1/resources/{id}
```

All `/api/v1/*` endpoints except the authentication endpoints require a bearer token when `AUTH_ENABLED=true`.

## Authentication setup

Install dependencies and generate local credentials:

```bash
python -m pip install -r requirements.txt
python scripts/setup_auth.py
```

Copy the generated values into `.env`. The script never writes a plaintext password to the repository. Authentication is enabled by default. Application startup fails if authentication is enabled but the username, Argon2 password hash or JWT secret is missing.

## Database update

The resource registry is schema migration `003_resource_registry.sql`. Existing PostgreSQL databases update automatically on application initialization, or explicitly with:

```bash
python scripts/init_database.py
```

## Deployment model

GitHub contains source code and CI. It is not the runtime for FastAPI/PostgreSQL. The repository includes a `Dockerfile` so the same application can run on a container host. A hosted deployment needs:

- HTTPS
- PostgreSQL, preferably on a private network
- deployment secrets for authentication, PostgreSQL and Sensor Hub credentials
- `CATALOG_PUBLIC_BASE_URL` set to the public HTTPS origin
- `SECURITY_HSTS_ENABLED=true` after HTTPS is confirmed
- outbound egress restrictions in addition to the application URL validation
- login rate limiting at the platform edge or reverse proxy

See `SECURITY.md` for the security boundary and remaining production requirements.
