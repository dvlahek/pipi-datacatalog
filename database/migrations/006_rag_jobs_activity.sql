-- PiPi Data Catalog schema migration 006
-- Persistent background RAG indexing jobs and user-visible activity/error log.

CREATE TABLE IF NOT EXISTS rag_index_jobs (
    id BIGSERIAL PRIMARY KEY,
    target_kind VARCHAR NOT NULL,
    target_identifier TEXT NOT NULL,
    label TEXT NULL,
    status VARCHAR NOT NULL DEFAULT 'queued',
    stage VARCHAR NULL,
    message TEXT NULL,
    progress_current INTEGER NULL,
    progress_total INTEGER NULL,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_rag_index_jobs_created_at
    ON rag_index_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_rag_index_jobs_target_status
    ON rag_index_jobs (target_kind, target_identifier, status);

CREATE TABLE IF NOT EXISTS activity_events (
    id BIGSERIAL PRIMARY KEY,
    level VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_activity_events_created_at
    ON activity_events (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_activity_events_level_category
    ON activity_events (level, category);
