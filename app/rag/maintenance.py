from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.embeddings import EmbeddingError, embed_dataset_chunks
from app.rag.service import RagIndexError, index_catalog_dataset
from app.rag.store import RagStore


def _disabled_resource_datasets(store: CatalogStore) -> set[str]:
    disabled: set[str] = set()
    for resource in store.list_resources():
        identifier = resource.get("dataset_identifier")
        if identifier and not resource.get("enabled", True):
            disabled.add(str(identifier))
    return disabled


async def reindex_stale_datasets(
    store: CatalogStore,
    settings: Settings,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Re-index only datasets that were indexed before and are now stale.

    Never-indexed datasets remain untouched. Disabled registered resources are skipped.
    A per-run limit prevents a provider refresh from causing an unbounded download burst.
    Current chunks are re-embedded after successful text indexing when vector settings
    are configured and pgvector is available.
    """

    effective_limit = max(0, int(limit if limit is not None else settings.rag_auto_reindex_limit))
    if not settings.rag_auto_reindex_enabled or effective_limit == 0:
        return {
            "status": "disabled",
            "candidates": 0,
            "attempted": 0,
            "reindexed": 0,
            "skipped_disabled": 0,
            "deferred": 0,
            "errors": 0,
            "data": [],
        }

    rag_store = RagStore(store)
    statuses = rag_store.list_index_statuses()
    stale = [
        item
        for item in statuses
        if item.get("status") == "stale" and item.get("indexed_version") is not None
    ]
    stale.sort(key=lambda item: str(item.get("dataset_identifier") or ""))

    disabled_identifiers = _disabled_resource_datasets(store)
    eligible = [
        item
        for item in stale
        if str(item["dataset_identifier"]) not in disabled_identifiers
    ]
    skipped_disabled = len(stale) - len(eligible)
    selected = eligible[:effective_limit]
    deferred = max(0, len(eligible) - len(selected))

    results: list[dict[str, Any]] = []
    reindexed = 0
    errors = 0

    for item in selected:
        dataset_identifier = str(item["dataset_identifier"])
        try:
            result = await index_catalog_dataset(store, dataset_identifier, settings)
            embedding: dict[str, Any] | None = None
            if getattr(settings, "rag_embedding_provider", None):
                try:
                    embedding = embed_dataset_chunks(store, settings, dataset_identifier)
                except (EmbeddingError, RuntimeError, ValueError, SQLAlchemyError) as exc:
                    embedding = {"status": "error", "error": str(exc)}
            reindexed += 1
            results.append(
                {
                    "dataset_identifier": dataset_identifier,
                    "status": "ok",
                    "from_version": item.get("indexed_version"),
                    "to_version": result.get("dataset_version"),
                    "chunk_count": result.get("chunk_count"),
                    "embedding": embedding,
                }
            )
        except (RagIndexError, KeyError, ValueError) as exc:
            errors += 1
            results.append(
                {
                    "dataset_identifier": dataset_identifier,
                    "status": "error",
                    "from_version": item.get("indexed_version"),
                    "catalog_version": item.get("catalog_version"),
                    "error": str(exc),
                }
            )

    return {
        "status": "partial" if errors else "ok",
        "candidates": len(stale),
        "attempted": len(selected),
        "reindexed": reindexed,
        "skipped_disabled": skipped_disabled,
        "deferred": deferred,
        "errors": errors,
        "data": results,
    }
