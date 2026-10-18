-- PiPi Data Catalog schema migration 005
-- Persistent harvest/refresh run history for provider sync and user resource refresh.

CREATE TABLE IF NOT EXISTS harvest_runs (
    id BIGSERIAL PRIMARY KEY,
    run_kind VARCHAR NOT NULL,
    trigger VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ NULL,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_harvest_runs_started_at
    ON harvest_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS ix_harvest_runs_kind_status
    ON harvest_runs (run_kind, status);
