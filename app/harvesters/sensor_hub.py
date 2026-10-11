from __future__ import annotations

import asyncio
from typing import Any

from app.clients.sensor_hub import SensorHubClient


class SensorHubHarvester:
    """Harvest descriptive Sensor Hub metadata without copying readings."""

    def __init__(self, client: SensorHubClient) -> None:
        self.client = client

    async def preview(self) -> dict[str, Any]:
        await self.client.authenticate()

        (
            locations,
            sources,
            deployments,
            properties,
            deployment_properties,
        ) = await asyncio.gather(
            self.client.list_locations(),
            self.client.list_sources(),
            self.client.list_deployments(),
            self.client.list_properties(),
            self.client.list_deployment_properties(),
        )

        return {
            "provider": "sensor-hub",
            "counts": {
                "locations": len(locations),
                "sources": len(sources),
                "deployments": len(deployments),
                "properties": len(properties),
                "deployment_properties": len(deployment_properties),
            },
            "dataset_candidates": len(deployment_properties),
            "readings_harvested": False,
        }
