from __future__ import annotations

from app.catalog.store import CatalogStore
from app.clients.sensor_hub import SensorHubClient
from app.config import Settings
from app.harvesters.sensor_hub import SensorHubHarvester
from app.models.catalog import CanonicalDataset
from app.providers.static_web import StaticWebProvider


async def build_catalog(client: SensorHubClient) -> list[CanonicalDataset]:
    """Discover and normalize datasets from all currently configured providers."""

    sensor_hub = SensorHubHarvester(client)
    static_web = StaticWebProvider()

    sensor_datasets = await sensor_hub.datasets()
    external_datasets = await static_web.datasets()

    datasets = [*sensor_datasets, *external_datasets]
    datasets.sort(key=lambda dataset: dataset.catalog_id)
    return datasets


def catalog_store(settings: Settings) -> CatalogStore | None:
    if not settings.catalog_store_enabled:
        return None
    if not settings.database_url:
        raise RuntimeError(
            "CATALOG_STORE_ENABLED is true but DATABASE_URL is not configured."
        )
    store = CatalogStore(
        settings.database_url,
        admin_url=settings.database_admin_url,
    )
    store.initialize()
    return store


async def sync_catalog(
    client: SensorHubClient,
    settings: Settings,
) -> dict[str, int]:
    """Discover provider metadata and idempotently upsert it into the catalog DB."""

    store = catalog_store(settings)
    if store is None:
        raise RuntimeError("Persistent catalog store is disabled.")

    datasets = await build_catalog(client)
    stats = store.upsert_datasets(datasets)
    stats["stored"] = store.count_datasets()
    return stats


async def load_catalog(
    client: SensorHubClient,
    settings: Settings,
) -> list[CanonicalDataset]:
    """Read the API catalog from PostgreSQL when enabled, otherwise discover live.

    When persistence is enabled and the store is empty, the first read may bootstrap
    it from configured providers. Later provider refreshes are explicit via the sync
    endpoint, so normal reads do not repeatedly hit every upstream source.
    """

    store = catalog_store(settings)
    if store is None:
        return await build_catalog(client)

    datasets = store.list_datasets()
    if datasets or not settings.catalog_bootstrap_if_empty:
        return datasets

    await sync_catalog(client, settings)
    return store.list_datasets()
