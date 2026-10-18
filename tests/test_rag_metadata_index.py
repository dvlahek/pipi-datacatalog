from app.catalog.store import CatalogStore
from app.config import Settings
from app.models.catalog import (
    CatalogDistribution,
    CatalogObservedProperty,
    CanonicalDataset,
)
from app.rag.metadata_index import (
    index_catalog_metadata_dataset,
    metadata_index_family,
    render_catalog_metadata_text,
)
from app.rag.store import RagStore


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        rag_chunk_size_chars=4000,
        rag_chunk_overlap_chars=100,
    )


def test_sensor_hub_metadata_is_indexed_without_reading_payload() -> None:
    store = CatalogStore("sqlite+pysqlite:///:memory:")
    store.initialize()
    dataset = CanonicalDataset(
        catalog_id="sensor:test",
        identifier="urn:pipi:dataset:sensor-hub:deployment-property:1",
        title="Outdoor temperature",
        description="Temperature observations for the outdoor demo deployment.",
        publisher="FOI Sensor Hub",
        license="unknown",
        dataset_type="sensor-observation",
        source_system="sensor-hub",
        keywords=["temperature", "sensor"],
        observed_property=CatalogObservedProperty(
            id=1,
            name="Temperature",
            unit_code="Cel",
        ),
        distributions=[
            CatalogDistribution(
                identifier="urn:test:readings",
                title="Readings API",
                access_url="https://example.org/readings",
                media_type="application/json",
                format="JSON",
            )
        ],
    )
    store.upsert_datasets([dataset])

    assert metadata_index_family(dataset) == "structured-data"
    result = index_catalog_metadata_dataset(store, dataset, _settings())
    assert result["index_source"] == "catalog-metadata"
    assert result["chunk_count"] == 1

    chunks = RagStore(store).list_chunks(dataset.identifier, limit=10)
    assert len(chunks) == 1
    assert "Observed property: Temperature" in chunks[0]["text"]
    assert "https://example.org/readings" not in chunks[0]["text"]
    assert chunks[0]["metadata"]["structure"] == "catalog-metadata"


def test_open_data_metadata_render_keeps_catalog_context() -> None:
    dataset = CanonicalDataset(
        catalog_id="open-data:test:air",
        identifier="urn:pipi:dataset:open-data:test:air",
        title="Air quality",
        description="Air-quality measurements published as open data.",
        publisher="Open Data Publisher",
        license="CC BY 4.0",
        dataset_type="open-data-catalog",
        source_system="open-data:test",
        external_id="air",
        keywords=["air", "environment"],
        distributions=[
            CatalogDistribution(
                identifier="urn:test:csv",
                title="CSV download",
                access_url="https://example.org/air.csv",
                media_type="text/csv",
                format="CSV",
            )
        ],
        extensions={
            "open_data_catalog": {
                "catalog_id": "test",
                "catalog_type": "ckan",
                "groups": ["Environment"],
            }
        },
    )

    assert metadata_index_family(dataset) == "open-data-catalogs"
    text = render_catalog_metadata_text(dataset)
    assert "Dataset title: Air quality" in text
    assert "Available formats: CSV" in text
    assert "Source catalog: test" in text
    assert "Catalog groups: Environment" in text
