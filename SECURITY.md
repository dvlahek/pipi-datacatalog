# Security notes

The PiPi Data Catalog is designed to be deployable as an authenticated web application. The current MVP uses a small, explicit security boundary instead of assuming a trusted local network.

## Authentication

Set `AUTH_ENABLED=true` for any shared or internet-accessible deployment. Generate an Argon2 password hash and JWT secret locally with:

```bash
python scripts/setup_auth.py
```

Copy the generated values into the deployment secret store or local `.env`. Never commit the real username, password hash, JWT secret, PostgreSQL credentials, or Sensor Hub credentials.

When authentication is enabled, `/api/v1/*` is protected by a short-lived bearer token except the authentication endpoints. The static portal shell contains no catalog data and cannot read or modify the API without a valid token.

The built-in login limiter is intentionally small and process-local. Public deployments should additionally rate-limit login traffic at the reverse proxy or hosting platform edge.

## HTTPS

Internet deployments must terminate HTTPS before the application. Set `SECURITY_HSTS_ENABLED=true` only after HTTPS is working for the final host. Plain HTTP bearer authentication must not be used on an untrusted network.

## External resource ingestion and SSRF

User-registered resources are restricted to `http` and `https`. The application rejects credentials embedded in URLs, localhost, loopback, private, link-local, reserved and other non-public IP ranges. Redirect targets are revalidated and the default accepted destination ports are 80 and 443.

Application-level checks do not fully eliminate DNS-rebinding and network-routing risks. A production deployment should also enforce outbound egress rules so the application container cannot reach cloud metadata endpoints, database management networks, internal RFC1918 services or other private infrastructure except explicitly required trusted providers.

Downloads are bounded by `RESOURCE_FETCH_MAX_BYTES` and `RESOURCE_FETCH_TIMEOUT_SECONDS`. Do not increase these values without considering memory, bandwidth and denial-of-service impact.

## Resource content

The catalog stores metadata, provenance and version fingerprints. It does not automatically archive source content. Downloadable files remain at the source unless a future provider explicitly implements content storage. Live HLS playlist bytes are not treated as dataset versions because the playlist changes continuously.

## Database

PostgreSQL must not be exposed directly to the public internet. Use a private database connection where the hosting platform supports one. Schema changes are applied through immutable numbered SQL migrations whose SHA-256 checksums are recorded in `catalog_schema_migrations`.

## Browser hardening

The API adds a Content Security Policy, frame denial, `nosniff`, a restrictive referrer policy and permissions policy. The portal stores the bearer token in `sessionStorage`, so closing the browser tab removes the browser-side session token. Avoid adding third-party JavaScript to the portal because script execution in the same origin could access that token.
