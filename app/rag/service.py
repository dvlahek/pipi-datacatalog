from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.catalog.store import CatalogStore
from app.config import Settings
from app.models.catalog import CatalogDistribution, CanonicalDataset
from app.rag.ingest import RagExtractionError, chunk_text, extract_text, text_sha256
from app.rag.store import RagStore
from app.resources.fetcher import (
    ResourceFetchError,
    ResourceProbe,
    detect_resource_type,
    fetch_resource_probe,
)
from app.resources.service import dataset_from_registered_resource
from app.security.url_policy import UnsafeResourceURL


class RagIndexError(RuntimeError):
    pass


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = (_REPOSITORY_ROOT / "data").resolve()
_TEXT_MEDIA_TYPES = {
    "text/csv",
    "text/plain",
    "text/html",
    "application/xhtml+xml",
    "application/json",
    "application/pdf",
}
_TEXT_FORMATS = {"CSV", "JSON", "PDF", "TXT", "TEXT", "HTML"}


def select_text_distribution(dataset: CanonicalDataset) -> CatalogDistribution | None:
    """Return the first distribution that can feed the current text RAG pipeline."""

    for distribution in dataset.distributions:
        media_type = distribution.media_type.lower()
        format_value = (distribution.format or "").upper()
        if media_type.startswith("text/"):
            return distribution
        if media_type in _TEXT_MEDIA_TYPES or media_type.endswith("+json"):
            return distribution
        if format_value in _TEXT_FORMATS:
            return distribution
    return None


def _dataset_by_identifier(store: CatalogStore, dataset_identifier: str) -> CanonicalDataset:
    for dataset in store.list_datasets():
        if dataset.identifier == dataset_identifier:
            return dataset
    raise RagIndexError("Catalog dataset not found.")


def _resource_id_for_dataset(store: CatalogStore, dataset_identifier: str) -> int | None:
    for resource in store.list_resources():
        if resource.get("dataset_identifier") == dataset_identifier:
            return int(resource["id"])
    return None


def _local_catalog_probe(
    distribution: CatalogDistribution,
    settings: Settings,
) -> ResourceProbe | None:
    """Read repository-hosted /files assets directly instead of going through SSRF checks."""

    access_url = str(distribution.access_url)
    parsed = urlparse(access_url)
    base = urlparse(settings.catalog_public_base_url)
    if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
        return None
    if not parsed.path.startswith("/files/"):
        return None

    relative = unquote(parsed.path[len("/files/") :]).lstrip("/")
    path = (_DATA_ROOT / relative).resolve()
    if not path.is_relative_to(_DATA_ROOT) or not path.is_file():
        raise RagIndexError("Catalog-local distribution does not resolve to a valid data file.")

    size = path.stat().st_size
    if size > settings.resource_fetch_max_bytes:
        raise RagIndexError("Dataset exceeds configured maximum indexing size.")

    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    media_type = distribution.media_type.lower()
    detected_type = detect_resource_type(access_url, media_type, content)
    return ResourceProbe(
        final_url=access_url,
        media_type=media_type,
        detected_type=detected_type,
        content_sha256=digest,
        byte_size=len(content),
        etag=None,
        last_modified=None,
        title_hint=path.name,
        content=content,
    )


async def _probe_catalog_distribution(
    distribution: CatalogDistribution,
    settings: Settings,
) -> ResourceProbe:
    local_probe = _local_catalog_probe(distribution, settings)
    if local_probe is not None:
        return local_probe
    return await fetch_resource_probe(str(distribution.access_url), settings)


def _ensure_version_matches_source(dataset: CanonicalDataset, probe: ResourceProbe) -> None:
    expected_hash = dataset.provenance.content_sha256 if dataset.provenance else None
    if expected_hash and probe.content_sha256 and expected_hash != probe.content_sha256:
        raise RagIndexError(
            "Dataset source content changed after the current catalog version was created. "
            "Sync the catalog before indexing so chunks remain bound to the correct version."
        )


def _store_probe_as_rag_document(
    store: CatalogStore,
    dataset: CanonicalDataset,
    probe: ResourceProbe,
    settings: Settings,
) -> dict[str, object]:
    text = extract_text(probe)
    chunks = chunk_text(
        text,
        chunk_size=settings.rag_chunk_size_chars,
        overlap=settings.rag_chunk_overlap_chars,
    )

    rag_store = RagStore(store)
    dataset_version = rag_store.latest_dataset_version(dataset.identifier)
    if dataset_version is None:
        raise RagIndexError("Dataset has no catalog version. Sync the catalog before RAG indexing.")

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
        "dataset_identifier": dataset.identifier,
        "dataset_version": dataset_version,
        "detected_type": probe.detected_type,
        "media_type": probe.media_type,
        "character_count": len(text),
        "chunk_count": len(chunks),
        "document": document,
    }


async def index_catalog_dataset(
    store: CatalogStore,
    dataset_identifier: str,
    settings: Settings,
) -> dict[str, object]:
    """Index a current catalog dataset without forcing it through the resource registry.

    User-registered resources still use their refresh-aware path. Provider-managed
    datasets use an indexable distribution and remain owned by their provider.
    """

    dataset = _dataset_by_identifier(store, dataset_identifier)

    if dataset.source_system == "resource-registry":
        resource_id = _resource_id_for_dataset(store, dataset.identifier)
        if resource_id is None:
            raise RagIndexError("Registered-resource dataset is missing its registry entry.")
        result = await index_registered_resource(store, resource_id, settings)
        return {**result, "index_source": "resource-registry"}

    distribution = select_text_distribution(dataset)
    if distribution is None:
        raise RagIndexError(
            "Dataset has no text-indexable distribution. Its catalog metadata remains searchable."
        )

    try:
        probe = await _probe_catalog_distribution(distribution, settings)
        _ensure_version_matches_source(dataset, probe)
        result = _store_probe_as_rag_document(store, dataset, probe, settings)
        return {**result, "index_source": "catalog-distribution"}
    except (ResourceFetchError, UnsafeResourceURL, RagExtractionError, ValueError) as exc:
        raise RagIndexError(str(exc)) from exc


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

        result = _store_probe_as_rag_document(store, dataset, probe, settings)
        return {
            **result,
            "resource_id": resource_id,
            "catalog_sync": sync,
        }
    except (ResourceFetchError, UnsafeResourceURL, RagExtractionError, ValueError) as exc:
        store.mark_resource_error(resource_id, str(exc))
        raise RagIndexError(str(exc)) from exc
