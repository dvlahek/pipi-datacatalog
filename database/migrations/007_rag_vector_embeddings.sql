-- PiPi Data Catalog schema migration 007
-- pgvector-backed embeddings for RAG chunks.
--
-- The embedding column intentionally has no fixed typmod. Model name and
-- dimensions are stored beside each vector so a future embedding model can be
-- introduced without rewriting catalog/document history. Retrieval always
-- filters by the configured model.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS embedding vector NULL;

ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR NULL;

ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS embedding_dimensions INTEGER NULL;

ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_model
    ON rag_chunks (embedding_model)
    WHERE embedding IS NOT NULL;
