from __future__ import annotations

from typing import Any

from app.catalog.store import CatalogStore
from app.config import Settings
from app.models.catalog import CanonicalDataset
from app.rag.ingest import TextChunk, chunk_text, text_sha256
from app.rag.store import RagStore


_METADATA_MEDIA_TYPE = "application/vnd.pipi.catalog-metadata+text"


def metadata_index_family(dataset: CanonicalDataset) -> str | None:
    """Return the benchmark family for datasets that should be indexed from metadata.

    Sensor Hub observations remain metadata-first because PiPi does not copy raw
    time-series readings into the text RAG index. Open-data catalogs are also
    metadata-first: PiPi indexes the harvested catalog record and keeps payload
    distributions as access links.
    """

    if dataset.source_system == "sensor-hub" or dataset.dataset_type == "sensor-observation":
        return "structured-data"
    if dataset.source_system.startswith("open-data:"):
        return "open-data-catalogs"
    return None


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _join(values: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _clean(value)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return ", ".join(ordered)


def render_catalog_metadata_text(dataset: CanonicalDataset) -> str:
    """Render one stable, human-readable metadata evidence record.

    The rendering intentionally contains descriptive metadata rather than source
    payload values. This makes Sensor Hub and external catalog datasets searchable
    without turning live readings or large downloads into synthetic text corpora.
    """

    lines = [
        f"Dataset title: {dataset.title}",
        f"Description: {dataset.description}",
        f"Publisher: {dataset.publisher}",
        f"License: {dataset.license}",
        f"Dataset type: {dataset.dataset_type}",
        f"Source system: {dataset.source_system}",
    ]

    if dataset.external_id:
        lines.append(f"External identifier: {dataset.external_id}")
    if dataset.keywords:
        lines.append(f"Keywords: {_join(dataset.keywords)}")

    if dataset.source is not None:
        source_bits = [dataset.source.name, dataset.source.provider or "", dataset.source.owner or ""]
        source_text = _join(source_bits)
        if source_text:
            lines.append(f"Source: {source_text}")

    if dataset.location is not None:
        location_bits = [dataset.location.name, dataset.location.address or ""]
        location_text = _join(location_bits)
        if location_text:
            lines.append(f"Location: {location_text}")

    if dataset.temporal is not None and (dataset.temporal.start or dataset.temporal.end):
        lines.append(
            "Temporal coverage: "
            f"{dataset.temporal.start or 'unknown'} to {dataset.temporal.end or 'unknown'}"
        )

    if dataset.observed_property is not None:
        observed = dataset.observed_property
        lines.append(f"Observed property: {observed.name}")
        if observed.description:
            lines.append(f"Observed property description: {observed.description}")
        if observed.unit_code:
            lines.append(f"Unit: {observed.unit_code}")
        if observed.quantity_kind:
            lines.append(f"Quantity kind: {observed.quantity_kind}")

    formats = _join(
        [
            distribution.format or distribution.media_type
            for distribution in dataset.distributions
            if distribution.format or distribution.media_type
        ]
    )
    if formats:
        lines.append(f"Available formats: {formats}")

    distribution_titles = _join([distribution.title for distribution in dataset.distributions])
    if distribution_titles:
        lines.append(f"Available distributions: {distribution_titles}")

    open_data = dataset.extensions.get("open_data_catalog")
    if isinstance(open_data, dict):
        catalog_id = _clean(open_data.get("catalog_id"))
        catalog_type = _clean(open_data.get("catalog_type"))
        groups = open_data.get("groups")
        if catalog_id:
            lines.append(f"Source catalog: {catalog_id}")
        if catalog_type:
            lines.append(f"Catalog type: {catalog_type}")
        if isinstance(groups, list) and groups:
            lines.append(f"Catalog groups: {_join([_clean(item) for item in groups])}")

    return "\n".join(line for line in lines if line.strip())


def _source_url(dataset: CanonicalDataset) -> str:
    if dataset.provenance is not None and dataset.provenance.source_url:
        return dataset.provenance.source_url
    if dataset.distributions:
        return str(dataset.distributions[0].access_url)
    return dataset.identifier


def index_catalog_metadata_dataset(
    store: CatalogStore,
    dataset: CanonicalDataset,
    settings: Settings,
) -> dict[str, object]:
    """Index a metadata-first catalog dataset without fetching its payload."""

    family = metadata_index_family(dataset)
    if family is None:
        raise ValueError(f"Dataset {dataset.identifier!r} is not metadata-first indexable.")

    text = render_catalog_metadata_text(dataset)
    base_chunks = chunk_text(
        text,
        chunk_size=settings.rag_chunk_size_chars,
        overlap=settings.rag_chunk_overlap_chars,
    )
    chunks = [
        TextChunk(
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            metadata={
                **chunk.metadata,
                "structure": "catalog-metadata",
                "source_family": family,
                "source_system": dataset.source_system,
                "external_id": dataset.external_id,
            },
        )
        for chunk in base_chunks
    ]

    rag_store = RagStore(store)
    dataset_version = rag_store.latest_dataset_version(dataset.identifier)
    if dataset_version is None:
        raise RuntimeError("Dataset has no catalog version. Sync the catalog before metadata indexing.")

    digest = text_sha256(text)
    document = rag_store.replace_document_index(
        dataset_identifier=dataset.identifier,
        dataset_version=dataset_version,
        source_url=_source_url(dataset),
        media_type=_METADATA_MEDIA_TYPE,
        content_sha256=digest,
        extracted_text_sha256=digest,
        character_count=len(text),
        chunks=chunks,
    )
    return {
        "status": "indexed",
        "index_source": "catalog-metadata",
        "source_family": family,
        "dataset_identifier": dataset.identifier,
        "dataset_version": dataset_version,
        "character_count": len(text),
        "chunk_count": len(chunks),
        "document": document,
    }
