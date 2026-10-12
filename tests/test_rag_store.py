from app.catalog.store import CatalogStore
from app.models.catalog import CanonicalDataset
from app.rag.ingest import TextChunk
from app.rag.store import RagStore


def test_rag_store_indexes_chunks_against_dataset_version(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rag.db'}"
    store = CatalogStore(database_url)
    store.initialize()

    dataset = CanonicalDataset(
        catalog_id="resource:1",
        identifier="urn:pipi:dataset:resource:1",
        title="Example document",
        description="Example text document",
        publisher="PiPi",
        license="unknown",
        dataset_type="text-document",
        source_system="resource-registry",
        external_id="1",
    )
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
        chunks=[
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
        ],
    )

    assert document["dataset_version"] == 1
    assert document["chunk_count"] == 2
    assert rag.document_status(dataset.identifier)["status"] == "indexed"

    chunks = rag.list_chunks(dataset.identifier)
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
    assert chunks[0]["text"] == "first indexed chunk"
