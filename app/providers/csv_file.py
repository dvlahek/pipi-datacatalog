from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from app.models.catalog import (
    CatalogDistribution,
    CatalogProvenance,
    CatalogSource,
    CanonicalDataset,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash file bytes without loading the complete file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class CsvFileProvider:
    """Register project-local CSV files as version-aware catalog datasets."""

    name = "csv-files"

    def __init__(
        self,
        config_path: str | Path,
        public_base_url: str,
        *,
        root_dir: str | Path | None = None,
    ) -> None:
        self.root_dir = Path(root_dir or REPOSITORY_ROOT).resolve()
        self.data_dir = (self.root_dir / "data").resolve()
        raw_config_path = Path(config_path)
        if not raw_config_path.is_absolute():
            raw_config_path = self.root_dir / raw_config_path
        self.config_path = raw_config_path.resolve()
        self.public_base_url = public_base_url.rstrip("/")

    async def datasets(self) -> list[CanonicalDataset]:
        entries = self._load_entries()
        return [self._dataset(entry) for entry in entries]

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"CSV provider config not found: {self.config_path}")

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        entries = payload.get("datasets") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise ValueError("CSV provider config must contain a 'datasets' list.")
        return entries

    def _resolve_data_file(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.root_dir / path
        path = path.resolve()

        if not path.is_relative_to(self.data_dir):
            raise ValueError(
                f"CSV source must be inside the project data directory: {path}"
            )
        if not path.is_file():
            raise FileNotFoundError(f"CSV source not found: {path}")
        return path

    def _inspect_csv(
        self,
        path: Path,
        *,
        delimiter: str,
        encoding: str,
    ) -> tuple[list[str], int]:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            header = next(reader, None)
            if not header:
                raise ValueError(f"CSV source has no header: {path}")
            row_count = sum(1 for _ in reader)
        return header, row_count

    def _dataset(self, entry: dict[str, Any]) -> CanonicalDataset:
        external_id = str(entry["id"])
        file_path = self._resolve_data_file(str(entry["file_path"]))
        delimiter = str(entry.get("delimiter", ","))
        encoding = str(entry.get("encoding", "utf-8"))
        columns, row_count = self._inspect_csv(
            file_path,
            delimiter=delimiter,
            encoding=encoding,
        )

        relative_data_path = file_path.relative_to(self.data_dir).as_posix()
        access_url = f"{self.public_base_url}/files/{relative_data_path}"
        identifier = f"urn:pipi:dataset:csv:{external_id}"
        publisher = str(entry.get("publisher", "PiPi"))
        license_value = str(entry.get("license", "unknown"))
        title = str(entry["title"])

        return CanonicalDataset(
            catalog_id=f"csv:{external_id}",
            identifier=identifier,
            title=title,
            description=str(entry["description"]),
            publisher=publisher,
            license=license_value,
            dataset_type=str(entry.get("dataset_type", "tabular-data")),
            source_system=str(entry.get("source_system", "csv-file")),
            external_id=external_id,
            keywords=[str(item) for item in entry.get("keywords", [])],
            provenance=CatalogProvenance(
                source_url=access_url,
                content_sha256=sha256_file(file_path),
            ),
            source=CatalogSource(
                id=external_id,
                code=external_id,
                name=title,
                provider=publisher,
                license=license_value,
            ),
            distributions=[
                CatalogDistribution(
                    identifier=f"{identifier}:distribution:csv",
                    title="CSV file",
                    access_url=access_url,
                    download_url=access_url,
                    media_type="text/csv",
                    format="CSV",
                    kind="file",
                    is_live=False,
                )
            ],
            extensions={
                "csv": {
                    "file_name": file_path.name,
                    "columns": columns,
                    "row_count": row_count,
                    "byte_size": file_path.stat().st_size,
                    "delimiter": delimiter,
                    "encoding": encoding,
                    "synthetic": bool(entry.get("synthetic", False)),
                }
            },
        )
