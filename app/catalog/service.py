from __future__ import annotations

from app.clients.sensor_hub import SensorHubClient
from app.harvesters.sensor_hub import SensorHubHarvester
from app.models.catalog import CanonicalDataset
from app.providers.static_web import StaticWebProvider


async def build_catalog(client: SensorHubClient) -> list[CanonicalDataset]:
    """Combine all currently configured providers into one catalog."""

    sensor_hub = SensorHubHarvester(client)
    static_web = StaticWebProvider()

    sensor_datasets = await sensor_hub.datasets()
    external_datasets = await static_web.datasets()

    datasets = [*sensor_datasets, *external_datasets]
    datasets.sort(key=lambda dataset: dataset.catalog_id)
    return datasets
