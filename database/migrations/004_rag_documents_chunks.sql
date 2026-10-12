-- PiPi Data Catalog schema migration 004
-- Version-aware RAG document and chunk storage. Embeddings are added later.

CREATE TABLE IF NOT EXISTS rag_documents (
    id BIGSERIAL PRIMARY KEY,
    dataset_identifier VARCHAR NOT NULL
        REFERENCES catalog_datasets(identifier) ON DELETE CASCADE,
    dataset_version INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    media_type VARCHAR NOT NULL,
    content_sha256 CHAR(64) NULL,
    extracted_text_sha256 CHAR(64) NOT NULL,
    character_count INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'indexed',
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (dataset_identifier, dataset_version)
);

CREATE INDEX IF NOT EXISTS ix_rag_documents_dataset_identifier
    ON rag_documents (dataset_identifier);
CREATE INDEX IF NOT EXISTS ix_rag_documents_dataset_version
    ON rag_documents (dataset_identifier, dataset_version);
CREATE INDEX IF NOT EXISTS ix_rag_documents_content_sha256
    ON rag_documents (content_sha256);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL
        REFERENCES rag_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS ix_rag_chunks_document_id
    ON rag_chunks (document_id);
