-- PiPi Data Catalog schema migration 003
-- Persistent registry for user-managed external resources.

CREATE TABLE IF NOT EXISTS catalog_resources (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR NULL,
    source_url VARCHAR NOT NULL UNIQUE,
    requested_type VARCHAR NOT NULL DEFAULT 'auto',
    detected_type VARCHAR NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    refresh_policy VARCHAR NOT NULL DEFAULT 'manual',
    dataset_identifier VARCHAR NULL
        REFERENCES catalog_datasets(identifier) ON DELETE SET NULL,
    last_media_type VARCHAR NULL,
    last_etag VARCHAR NULL,
    last_modified VARCHAR NULL,
    last_content_sha256 VARCHAR(64) NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ NULL,
    last_success_at TIMESTAMPTZ NULL,
    last_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_catalog_resources_enabled
    ON catalog_resources (enabled);
CREATE INDEX IF NOT EXISTS ix_catalog_resources_detected_type
    ON catalog_resources (detected_type);
CREATE INDEX IF NOT EXISTS ix_catalog_resources_dataset_identifier
    ON catalog_resources (dataset_identifier);
