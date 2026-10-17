import asyncio
import json

from app.models.catalog import CatalogDistribution, CanonicalDataset
from app.providers.csv_file import CsvFileProvider
from app.providers.static_web import StaticWebProvider
from app.rag.service import select_text_distribution


def _write_csv_provider_config(root, csv_path) -> None:
    payload = {
        "datasets": [
            {
                "id": "rag-csv",
                "file_path": str(csv_path.relative_to(root)).replace("\\", "/"),
                "title": "RAG CSV",
                "description": "Synthetic CSV for catalog RAG indexing tests.",
                "publisher": "PiPi test",
                "license": "unknown",
                "synthetic": True,
            }
        ]
    }
    (root / "config.json").write_text(json.dumps(payload), encoding="utf-8")


def test_provider_managed_csv_is_text_indexable(tmp_path) -> None:
    data_dir = tmp_path / "data" / "csv"
    data_dir.mkdir(parents=True)
    csv_path = data_dir / "rag.csv"
    csv_path.write_text("site,metric,value\nA,temperature,20.1\n", encoding="utf-8")
    _write_csv_provider_config(tmp_path, csv_path)

    dataset = asyncio.run(
        CsvFileProvider(
            "config.json",
            "http://127.0.0.1:8000",
            root_dir=tmp_path,
        ).datasets()
    )[0]

    distribution = select_text_distribution(dataset)
    assert distribution is not None
    assert distribution.media_type == "text/csv"


def test_live_webcam_is_not_text_indexable() -> None:
    dataset = asyncio.run(StaticWebProvider().datasets())[0]
    assert dataset.dataset_type == "live-video-stream"
    assert select_text_distribution(dataset) is None


def test_sensor_observation_stays_metadata_first_even_with_json_distribution() -> None:
    dataset = CanonicalDataset(
        catalog_id="sensor:test",
        identifier="urn:pipi:dataset:sensor:test",
        title="Sensor test",
        description="Synthetic sensor observation.",
        publisher="PiPi test",
        license="unknown",
        dataset_type="sensor-observation",
        source_system="sensor-hub",
        distributions=[
            CatalogDistribution(
                identifier="urn:pipi:dataset:sensor:test:distribution:json",
                title="Sensor readings",
                access_url="https://example.org/readings",
                media_type="application/json",
                format="JSON",
            )
        ],
    )

    assert select_text_distribution(dataset) is None
