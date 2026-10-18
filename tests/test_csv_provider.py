import asyncio
import json

from app.providers.csv_file import CsvFileProvider
from app.semantic.dcat import dataset_to_jsonld
from app.semantic.shacl import validate_dataset_jsonld


def _write_config(root, csv_path) -> None:
    config = {
        "datasets": [
            {
                "id": "example-csv",
                "file_path": str(csv_path.relative_to(root)).replace("\\", "/"),
                "title": "Example CSV",
                "description": "Synthetic CSV used by the provider unit test.",
                "publisher": "PiPi test",
                "license": "unknown",
                "synthetic": True,
                "keywords": ["CSV", "test"],
            }
        ]
    }
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")


def test_csv_provider_builds_dataset_and_detects_content_change(tmp_path) -> None:
    data_dir = tmp_path / "data" / "csv"
    data_dir.mkdir(parents=True)
    csv_path = data_dir / "example.csv"
    csv_path.write_text("id,value\n1,10\n2,20\n", encoding="utf-8")
    _write_config(tmp_path, csv_path)

    provider = CsvFileProvider(
        "config.json",
        "http://catalog.test",
        root_dir=tmp_path,
    )
    first = asyncio.run(provider.datasets())[0]

    assert first.identifier == "urn:pipi:dataset:csv:example-csv"
    assert first.dataset_type == "tabular-data"
    assert first.distributions[0].media_type == "text/csv"
    assert first.distributions[0].access_url == (
        "http://catalog.test/files/csv/example.csv"
    )
    assert first.extensions["csv"]["columns"] == ["id", "value"]
    assert first.extensions["csv"]["row_count"] == 2
    assert len(first.provenance.content_sha256) == 64

    first_hash = first.provenance.content_sha256
    csv_path.write_text("id,value\n1,10\n2,21\n", encoding="utf-8")
    second = asyncio.run(provider.datasets())[0]

    assert second.identifier == first.identifier
    assert second.provenance.content_sha256 != first_hash


def test_csv_provider_dataset_conforms_to_local_shacl_profile(tmp_path) -> None:
    data_dir = tmp_path / "data" / "csv"
    data_dir.mkdir(parents=True)
    csv_path = data_dir / "example.csv"
    csv_path.write_text("id,value\n1,10\n", encoding="utf-8")
    _write_config(tmp_path, csv_path)

    dataset = asyncio.run(
        CsvFileProvider(
            "config.json",
            "http://catalog.test",
            root_dir=tmp_path,
        ).datasets()
    )[0]

    validation = validate_dataset_jsonld(dataset_to_jsonld(dataset))
    assert validation["conforms"] is True
