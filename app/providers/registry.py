from __future__ import annotations

from dataclasses import asdict, dataclass

from app.models.catalog import CanonicalDataset
from app.providers.base import CatalogProvider


@dataclass(slots=True)
class ProviderStatus:
    name: str
    status: str
    dataset_count: int = 0
    error: str | None = None

    def model_dump(self) -> dict[str, object]:
        return asdict(self)


async def discover_from_providers(
    providers: list[CatalogProvider],
) -> tuple[list[CanonicalDataset], list[ProviderStatus]]:
    """Discover datasets while isolating provider failures.

    A failing provider is reported in the status list and does not prevent healthy
    providers from contributing datasets. Existing persisted rows are not deleted
    by sync, so a transient provider outage does not erase previously known data.
    """

    datasets: list[CanonicalDataset] = []
    statuses: list[ProviderStatus] = []

    for provider in providers:
        try:
            provider_datasets = await provider.datasets()
        except Exception as exc:  # provider boundary: isolate external failures
            statuses.append(
                ProviderStatus(
                    name=provider.name,
                    status="error",
                    dataset_count=0,
                    error=str(exc),
                )
            )
            continue

        datasets.extend(provider_datasets)
        statuses.append(
            ProviderStatus(
                name=provider.name,
                status="ok",
                dataset_count=len(provider_datasets),
            )
        )

    datasets.sort(key=lambda dataset: dataset.catalog_id)
    return datasets, statuses
