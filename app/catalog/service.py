from __future__ import annotations

from functools import lru_cache

from app.catalog.store import CatalogStore
from app.clients.sensor_hub import SensorHubClient
from app.config import Settings
from app.models.catalog import CanonicalDataset
from app.providers.base import CatalogProvider
from app.providers.csv_file import CsvFileProvider
from app.providers.foi_documents import FoiDocumentsProvider
from app.providers.registry import ProviderStatus, discover_from_providers
from app.providers.sensor_hub import SensorHubProvider
from app.providers.static_web import StaticWebProvider


def configured_providers(
    client: SensorHubClient,
    settings: Settings,
) -> list[CatalogProvider]:
    """Build the enabled provider set from application configuration."""

    providers: list[CatalogProvider] = []
    if settings.provider_sensor_hub_enabled:
        providers.append(SensorHubProvider(client))
    if settings.provider_static_web_enabled:
        providers.append(StaticWebProvider())
    if settings.provider_csv_enabled:
        providers.append(
            CsvFileProvider(
                settings.csv_datasets_config,
                settings.catalog_public_base_url,
            )
        )
    if settings.provider_foi_documents_enabled:
        providers.append(
            FoiDocumentsProvider(
                settings.foi_documents_base_url,
                settings.foi_documents_timeout_seconds,
            )
        )

    if not providers:
        raise RuntimeError("No catalog providers are enabled.")
    return providers


async def discover_catalog(
    client: SensorHubClient,
    settings: Settings,
) -> tuple[list[CanonicalDataset], list[ProviderStatus]]:
    """Discover normalized datasets and per-provider status."""

    return await discover_from_providers(configured_providers(client, settings))


async def build_catalog(
    client: SensorHubClient,
    settings: Settings | None = None,
) -> list[CanonicalDataset]:
    """Compatibility helper returning only discovered datasets."""

    active_settings = settings or Settings()
    datasets, _ = await discover_catalog(client, active_settings)
    return datasets


@lru_cache(maxsize=4)
def _initialized_store(database_url: str, admin_url: str | None) -> CatalogStore:
    store = CatalogStore(database_url, admin_url=admin_url)
    store.initialize()
    return store


def catalog_store(settings: Settings) -> CatalogStore | None:
    if not settings.catalog_store_enabled:
        return None
    if not settings.database_url:
        raise RuntimeError(
            "CATALOG_STORE_ENABLED is true but DATABASE_URL is not configured."
        )
    return _initialized_store(settings.database_url, settings.database_admin_url)


async def sync_catalog(
    client: SensorHubClient,
    settings: Settings,
) -> dict[str, object]:
    """Discover healthy providers and version-aware upsert their metadata."""

    store = catalog_store(settings)
    if store is None:
        raise RuntimeError("Persistent catalog store is disabled.")

    datasets, provider_statuses = await discover_catalog(client, settings)
    stats: dict[str, object] = store.upsert_datasets(datasets)
    stats["stored"] = store.count_datasets()
    stats["providers"] = [status.model_dump() for status in provider_statuses]
    stats["provider_errors"] = sum(
        1 for status in provider_statuses if status.status == "error"
    )
    return stats


async def load_catalog(
    client: SensorHubClient,
    settings: Settings,
) -> list[CanonicalDataset]:
    """Read PostgreSQL when enabled, otherwise discover providers live.

    When persistence is enabled and the store is empty, the first read may bootstrap
    it from configured providers. Later provider refreshes are explicit via the sync
    endpoint, so normal reads do not repeatedly hit every upstream source.
    """

    store = catalog_store(settings)
    if store is None:
        return await build_catalog(client, settings)

    datasets = store.list_datasets()
    if datasets or not settings.catalog_bootstrap_if_empty:
        return datasets

    await sync_catalog(client, settings)
    return store.list_datasets()
