from app.catalog.store import CatalogStore
from app.models.catalog import CanonicalDataset
from app.rag.ingest import TextChunk
from app.rag.store import RagStore


def _dataset(title: str = "Example document") -> CanonicalDataset:
    return CanonicalDataset(
        catalog_id="resource:1",
        identifier="urn:pipi:dataset:resource:1",
        title=title,
        description="Example text document",
        publisher="PiPi",
        license="unknown",
        dataset_type="text-document",
        source_system="resource-registry",
        external_id="1",
    )


def _chunks() -> list[TextChunk]:
    return [
        TextChunk(
            chunk_index=0,
            text="first indexed chunk",
            char_start=0,
            char_end=19,
            metadata={"character_count": 19},
        ),
        TextChunk(
            chunk_index=1,
            text="second indexed chunk",
            char_start=15,
            char_end=35,
            metadata={"character_count": 20},
        ),
    ]


def test_rag_store_indexes_chunks_against_dataset_version(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rag.db'}"
    store = CatalogStore(database_url)
    store.initialize()

    dataset = _dataset()
    store.upsert_datasets([dataset])

    rag = RagStore(store)
    version = rag.latest_dataset_version(dataset.identifier)
    assert version == 1

    document = rag.replace_document_index(
        dataset_identifier=dataset.identifier,
        dataset_version=version,
        source_url="https://example.com/doc.txt",
        media_type="text/plain",
        content_sha256="a" * 64,
        extracted_text_sha256="b" * 64,
        character_count=23,
        chunks=_chunks(),
    )

    assert document["dataset_version"] == 1
    assert document["chunk_count"] == 2
    assert rag.document_status(dataset.identifier)["status"] == "indexed"

    status = rag.index_status(dataset.identifier)
    assert status["status"] == "indexed"
    assert status["catalog_version"] == 1
    assert status["indexed_version"] == 1

    chunks = rag.list_chunks(dataset.identifier)
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
    assert chunks[0]["text"] == "first indexed chunk"


def test_rag_index_becomes_stale_when_catalog_version_advances(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rag_stale.db'}"
    store = CatalogStore(database_url)
    store.initialize()

    dataset = _dataset()
    store.upsert_datasets([dataset])
    rag = RagStore(store)
    rag.replace_document_index(
        dataset_identifier=dataset.identifier,
        dataset_version=1,
        source_url="https://example.com/doc.txt",
        media_type="text/plain",
        content_sha256="a" * 64,
        extracted_text_sha256="b" * 64,
        character_count=23,
        chunks=_chunks(),
    )

    store.upsert_datasets([_dataset(title="Example document - revised")])

    status = rag.index_status(dataset.identifier)
    assert status["status"] == "stale"
    assert status["catalog_version"] == 2
    assert status["indexed_version"] == 1

    bulk = {item["dataset_identifier"]: item for item in rag.list_index_statuses()}
    assert bulk[dataset.identifier]["status"] == "stale"

    # Stale chunks stay preserved for audit/history but are not used for retrieval.
    assert rag.list_chunks(dataset.identifier)
    assert rag.search_chunks("first indexed") == []

    rag.replace_document_index(
        dataset_identifier=dataset.identifier,
        dataset_version=2,
        source_url="https://example.com/doc.txt",
        media_type="text/plain",
        content_sha256="a" * 64,
        extracted_text_sha256="b" * 64,
        character_count=23,
        chunks=_chunks(),
    )

    refreshed = rag.index_status(dataset.identifier)
    assert refreshed["status"] == "indexed"
    assert refreshed["catalog_version"] == 2
    assert refreshed["indexed_version"] == 2
    assert rag.search_chunks("first indexed")
