from __future__ import annotations

from app.clients.sensor_hub import SensorHubClient
from app.harvesters.sensor_hub import SensorHubHarvester
from app.models.catalog import CanonicalDataset


class SensorHubProvider:
    """Provider adapter exposing Sensor Hub through the common provider contract."""

    name = "sensor-hub"
    kind = "api"

    def __init__(self, client: SensorHubClient) -> None:
        self._harvester = SensorHubHarvester(client)

    async def datasets(self) -> list[CanonicalDataset]:
        return await self._harvester.datasets()
