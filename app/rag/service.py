from __future__ import annotations

from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.ingest import RagExtractionError, chunk_text, extract_text, text_sha256
from app.rag.store import RagStore
from app.resources.fetcher import ResourceFetchError, fetch_resource_probe
from app.resources.service import dataset_from_registered_resource
from app.security.url_policy import UnsafeResourceURL


class RagIndexError(RuntimeError):
    pass


async def index_registered_resource(
    store: CatalogStore,
    resource_id: int,
    settings: Settings,
) -> dict[str, object]:
    resource = store.get_resource(resource_id)
    if resource is None:
        raise KeyError(resource_id)
    if not resource["enabled"]:
        raise RagIndexError("Disabled resources cannot be indexed.")

    try:
        probe = await fetch_resource_probe(str(resource["source_url"]), settings)
        dataset = dataset_from_registered_resource(resource, probe)
        sync = store.upsert_datasets([dataset])
        store.mark_resource_success(
            resource_id,
            detected_type=probe.detected_type,
            dataset_identifier=dataset.identifier,
            media_type=probe.media_type,
            etag=probe.etag,
            last_modified=probe.last_modified,
            content_sha256=probe.content_sha256,
        )

        text = extract_text(probe)
        chunks = chunk_text(
            text,
            chunk_size=settings.rag_chunk_size_chars,
            overlap=settings.rag_chunk_overlap_chars,
        )

        rag_store = RagStore(store)
        dataset_version = rag_store.latest_dataset_version(dataset.identifier)
        if dataset_version is None:
            raise RagIndexError("Dataset version was not created before RAG indexing.")

        document = rag_store.replace_document_index(
            dataset_identifier=dataset.identifier,
            dataset_version=dataset_version,
            source_url=probe.final_url,
            media_type=probe.media_type,
            content_sha256=probe.content_sha256,
            extracted_text_sha256=text_sha256(text),
            character_count=len(text),
            chunks=chunks,
        )

        return {
            "status": "indexed",
            "resource_id": resource_id,
            "dataset_identifier": dataset.identifier,
            "dataset_version": dataset_version,
            "detected_type": probe.detected_type,
            "media_type": probe.media_type,
            "character_count": len(text),
            "chunk_count": len(chunks),
            "catalog_sync": sync,
            "document": document,
        }
    except (ResourceFetchError, UnsafeResourceURL, RagExtractionError, ValueError) as exc:
        store.mark_resource_error(resource_id, str(exc))
        raise RagIndexError(str(exc)) from exc
