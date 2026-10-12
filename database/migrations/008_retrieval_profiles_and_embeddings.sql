-- PiPi Data Catalog schema migration 008
-- Versioned retrieval profiles, parallel embedding representations and retrieval run provenance.
--
-- Migration 007 stored one active vector directly on rag_chunks. This migration keeps
-- those columns intact for backward compatibility, but introduces a normalized table
-- so the same chunk can retain multiple embedding representations simultaneously.

CREATE TABLE IF NOT EXISTS rag_retrieval_profiles (
    profile_id VARCHAR PRIMARY KEY,
    profile_version INTEGER NOT NULL,
    label VARCHAR NOT NULL,
    mode VARCHAR NOT NULL,
    description TEXT NULL,
    config JSONB NOT NULL,
    config_hash CHAR(64) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_rag_retrieval_profiles_mode
        CHECK (mode IN ('lexical', 'vector', 'hybrid'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_rag_retrieval_profiles_config_hash
    ON rag_retrieval_profiles (config_hash);

CREATE TABLE IF NOT EXISTS rag_chunk_embeddings (
    chunk_id INTEGER NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
    embedding_identity VARCHAR NOT NULL,
    embedding_provider VARCHAR NOT NULL,
    embedding_model VARCHAR NOT NULL,
    embedding_revision VARCHAR NULL,
    input_profile VARCHAR NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding vector NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chunk_id, embedding_identity)
);

CREATE INDEX IF NOT EXISTS ix_rag_chunk_embeddings_identity
    ON rag_chunk_embeddings (embedding_identity);

-- Preserve the currently active migration-007 representation. Earlier representations
-- that were already overwritten cannot be reconstructed by SQL and are intentionally
-- rebuilt later as separate profile embeddings.
INSERT INTO rag_chunk_embeddings (
    chunk_id,
    embedding_identity,
    embedding_provider,
    embedding_model,
    embedding_revision,
    input_profile,
    dimensions,
    embedding,
    embedded_at
)
SELECT
    id,
    embedding_model,
    'legacy-migrated',
    embedding_model,
    NULL,
    CASE
        WHEN embedding_model LIKE '%#metadata-v1' THEN 'metadata-v1'
        ELSE 'content-v1'
    END,
    embedding_dimensions,
    embedding,
    COALESCE(embedded_at, CURRENT_TIMESTAMP)
FROM rag_chunks
WHERE embedding IS NOT NULL
  AND embedding_model IS NOT NULL
  AND embedding_dimensions IS NOT NULL
ON CONFLICT (chunk_id, embedding_identity) DO NOTHING;

CREATE TABLE IF NOT EXISTS rag_retrieval_runs (
    id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    profile_id VARCHAR NULL REFERENCES rag_retrieval_profiles(profile_id),
    profile_hash CHAR(64) NULL,
    catalog_snapshot_hash CHAR(64) NOT NULL,
    retrieval VARCHAR NOT NULL,
    top_k INTEGER NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_rag_retrieval_runs_created_at
    ON rag_retrieval_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS ix_rag_retrieval_runs_profile_id
    ON rag_retrieval_runs (profile_id);
