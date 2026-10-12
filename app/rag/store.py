from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, delete, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.catalog.store import Base, CatalogStore, DatasetVersionRow, ResourceRow
from app.rag.ingest import TextChunk
from app.rag.retrieval import rank_chunk_candidates


class RagDocumentRow(Base):
    __tablename__ = "rag_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_identifier: Mapped[str] = mapped_column(
        ForeignKey("catalog_datasets.identifier", ondelete="CASCADE"), index=True
    )
    dataset_version: Mapped[int] = mapped_column(Integer, index=True)
    source_url: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    extracted_text_sha256: Mapped[str] = mapped_column(String(64))
    character_count: Mapped[int] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="indexed")
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RagChunkRow(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class RagStore:
    def __init__(self, catalog_store: CatalogStore) -> None:
        self.catalog_store = catalog_store
        self.engine = catalog_store.engine

    def latest_dataset_version(self, dataset_identifier: str) -> int | None:
        with Session(self.engine) as session:
            row = session.scalars(
                select(DatasetVersionRow)
                .where(DatasetVersionRow.dataset_identifier == dataset_identifier)
                .order_by(DatasetVersionRow.version.desc())
                .limit(1)
            ).first()
            return None if row is None else row.version

    def replace_document_index(
        self,
        *,
        dataset_identifier: str,
        dataset_version: int,
        source_url: str,
        media_type: str,
        content_sha256: str | None,
        extracted_text_sha256: str,
        character_count: int,
        chunks: list[TextChunk],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            existing = session.scalars(
                select(RagDocumentRow).where(
                    RagDocumentRow.dataset_identifier == dataset_identifier,
                    RagDocumentRow.dataset_version == dataset_version,
                )
            ).first()
            if existing is not None:
                session.execute(delete(RagChunkRow).where(RagChunkRow.document_id == existing.id))
                session.delete(existing)
                session.flush()

            document = RagDocumentRow(
                dataset_identifier=dataset_identifier,
                dataset_version=dataset_version,
                source_url=source_url,
                media_type=media_type,
                content_sha256=content_sha256,
                extracted_text_sha256=extracted_text_sha256,
                character_count=character_count,
                chunk_count=len(chunks),
                status="indexed",
                indexed_at=now,
            )
            session.add(document)
            session.flush()

            session.add_all(
                [
                    RagChunkRow(
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        metadata_json=chunk.metadata,
                    )
                    for chunk in chunks
                ]
            )
            session.commit()
            session.refresh(document)
            return self._document_dict(document)

    def document_status(self, dataset_identifier: str) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.scalars(
                select(RagDocumentRow)
                .where(RagDocumentRow.dataset_identifier == dataset_identifier)
                .order_by(RagDocumentRow.dataset_version.desc())
                .limit(1)
            ).first()
            return None if row is None else self._document_dict(row)

    def index_status(self, dataset_identifier: str) -> dict[str, Any]:
        """Compare the latest catalog version with the latest indexed RAG version."""

        catalog_version = self.latest_dataset_version(dataset_identifier)
        document = self.document_status(dataset_identifier)
        indexed_version = None if document is None else int(document["dataset_version"])

        if document is None:
            status = "not_indexed"
        elif catalog_version is not None and indexed_version == catalog_version:
            status = "indexed"
        else:
            status = "stale"

        return {
            "dataset_identifier": dataset_identifier,
            "status": status,
            "catalog_version": catalog_version,
            "indexed_version": indexed_version,
            "document": document,
        }

    def list_index_statuses(self) -> list[dict[str, Any]]:
        """Return freshness status for all versioned catalog datasets in two queries."""

        with Session(self.engine) as session:
            version_rows = session.scalars(
                select(DatasetVersionRow).order_by(
                    DatasetVersionRow.dataset_identifier,
                    DatasetVersionRow.version.desc(),
                )
            ).all()
            document_rows = session.scalars(
                select(RagDocumentRow).order_by(
                    RagDocumentRow.dataset_identifier,
                    RagDocumentRow.dataset_version.desc(),
                )
            ).all()

        latest_versions: dict[str, int] = {}
        for row in version_rows:
            latest_versions.setdefault(row.dataset_identifier, row.version)

        latest_documents: dict[str, RagDocumentRow] = {}
        for row in document_rows:
            latest_documents.setdefault(row.dataset_identifier, row)

        statuses: list[dict[str, Any]] = []
        for dataset_identifier, catalog_version in latest_versions.items():
            document = latest_documents.get(dataset_identifier)
            indexed_version = None if document is None else document.dataset_version
            if document is None:
                status = "not_indexed"
            elif indexed_version == catalog_version:
                status = "indexed"
            else:
                status = "stale"

            statuses.append(
                {
                    "dataset_identifier": dataset_identifier,
                    "status": status,
                    "catalog_version": catalog_version,
                    "indexed_version": indexed_version,
                    "document": None if document is None else self._document_dict(document),
                }
            )

        return statuses

    def list_chunks(
        self,
        dataset_identifier: str,
        dataset_version: int | None = None,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            document_query = select(RagDocumentRow).where(
                RagDocumentRow.dataset_identifier == dataset_identifier
            )
            if dataset_version is not None:
                document_query = document_query.where(
                    RagDocumentRow.dataset_version == dataset_version
                )
            document = session.scalars(
                document_query.order_by(RagDocumentRow.dataset_version.desc()).limit(1)
            ).first()
            if document is None:
                return []

            rows = session.scalars(
                select(RagChunkRow)
                .where(RagChunkRow.document_id == document.id)
                .order_by(RagChunkRow.chunk_index)
                .offset(offset)
                .limit(limit)
            ).all()
            return [
                {
                    "chunk_index": row.chunk_index,
                    "text": row.text,
                    "char_start": row.char_start,
                    "char_end": row.char_end,
                    "metadata": dict(row.metadata_json or {}),
                    "dataset_version": document.dataset_version,
                }
                for row in rows
            ]

    def search_chunks(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Search only chunks whose index matches the current catalog version.

        Disabled user-registered resources remain preserved in catalog/version history,
        but their previously indexed chunks are excluded from retrieval. A RAG index
        also becomes ineligible as soon as a newer catalog version exists. This avoids
        silently answering from stale content while a re-index is pending.
        """
        with Session(self.engine) as session:
            disabled_resource_datasets = set(
                session.scalars(
                    select(ResourceRow.dataset_identifier).where(
                        ResourceRow.enabled.is_(False),
                        ResourceRow.dataset_identifier.is_not(None),
                    )
                ).all()
            )

            version_rows = session.scalars(
                select(DatasetVersionRow).order_by(
                    DatasetVersionRow.dataset_identifier,
                    DatasetVersionRow.version.desc(),
                )
            ).all()
            latest_catalog_versions: dict[str, int] = {}
            for version_row in version_rows:
                latest_catalog_versions.setdefault(
                    version_row.dataset_identifier,
                    version_row.version,
                )

            documents = session.scalars(
                select(RagDocumentRow).order_by(
                    RagDocumentRow.dataset_identifier,
                    RagDocumentRow.dataset_version.desc(),
                )
            ).all()

            latest_documents: dict[str, RagDocumentRow] = {}
            for document in documents:
                if document.dataset_identifier in disabled_resource_datasets:
                    continue
                if latest_catalog_versions.get(document.dataset_identifier) != document.dataset_version:
                    continue
                latest_documents.setdefault(document.dataset_identifier, document)

            if not latest_documents:
                return []

            document_ids = [document.id for document in latest_documents.values()]
            rows = session.execute(
                select(RagChunkRow, RagDocumentRow)
                .join(RagDocumentRow, RagChunkRow.document_id == RagDocumentRow.id)
                .where(RagChunkRow.document_id.in_(document_ids))
            ).all()

            candidates = [
                {
                    "dataset_identifier": document.dataset_identifier,
                    "dataset_version": document.dataset_version,
                    "source_url": document.source_url,
                    "media_type": document.media_type,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "metadata": dict(chunk.metadata_json or {}),
                }
                for chunk, document in rows
            ]

        return rank_chunk_candidates(query, candidates, limit=limit)

    @staticmethod
    def _document_dict(row: RagDocumentRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "dataset_identifier": row.dataset_identifier,
            "dataset_version": row.dataset_version,
            "source_url": row.source_url,
            "media_type": row.media_type,
            "content_sha256": row.content_sha256,
            "extracted_text_sha256": row.extracted_text_sha256,
            "character_count": row.character_count,
            "chunk_count": row.chunk_count,
            "status": row.status,
            "indexed_at": row.indexed_at,
        }
