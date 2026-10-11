from __future__ import annotations

from typing import Protocol

from app.models.catalog import CanonicalDataset


class CatalogProvider(Protocol):
    """Minimal provider contract for adding heterogeneous catalog sources."""

    name: str

    async def datasets(self) -> list[CanonicalDataset]:
        ...
