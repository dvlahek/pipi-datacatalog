-- PiPi Data Catalog schema migration 002
-- Immutable dataset snapshots used for source/content change tracking.

CREATE TABLE IF NOT EXISTS catalog_dataset_versions (
    dataset_identifier VARCHAR NOT NULL
        REFERENCES catalog_datasets(identifier) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (dataset_identifier, version)
);

CREATE INDEX IF NOT EXISTS ix_catalog_dataset_versions_fingerprint
    ON catalog_dataset_versions (fingerprint);
CREATE INDEX IF NOT EXISTS ix_catalog_dataset_versions_created_at
    ON catalog_dataset_versions (created_at);
