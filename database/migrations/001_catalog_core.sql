-- PiPi Data Catalog schema migration 001
-- Provider-neutral current-state metadata tables.

CREATE TABLE IF NOT EXISTS catalog_datasets (
    identifier VARCHAR PRIMARY KEY,
    catalog_id VARCHAR NOT NULL UNIQUE,
    source_system VARCHAR NOT NULL,
    external_id VARCHAR NULL,
    title VARCHAR NOT NULL,
    dataset_type VARCHAR NOT NULL,
    payload JSONB NOT NULL,
    harvested_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_catalog_datasets_catalog_id
    ON catalog_datasets (catalog_id);
CREATE INDEX IF NOT EXISTS ix_catalog_datasets_source_system
    ON catalog_datasets (source_system);
CREATE INDEX IF NOT EXISTS ix_catalog_datasets_external_id
    ON catalog_datasets (external_id);
CREATE INDEX IF NOT EXISTS ix_catalog_datasets_title
    ON catalog_datasets (title);
CREATE INDEX IF NOT EXISTS ix_catalog_datasets_dataset_type
    ON catalog_datasets (dataset_type);

CREATE TABLE IF NOT EXISTS catalog_distributions (
    identifier VARCHAR PRIMARY KEY,
    dataset_identifier VARCHAR NOT NULL
        REFERENCES catalog_datasets(identifier) ON DELETE CASCADE,
    title VARCHAR NOT NULL,
    access_url VARCHAR NOT NULL,
    media_type VARCHAR NOT NULL,
    format VARCHAR NULL,
    kind VARCHAR NULL,
    is_live BOOLEAN NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_catalog_distributions_dataset_identifier
    ON catalog_distributions (dataset_identifier);
CREATE INDEX IF NOT EXISTS ix_catalog_distributions_media_type
    ON catalog_distributions (media_type);
CREATE INDEX IF NOT EXISTS ix_catalog_distributions_kind
    ON catalog_distributions (kind);
