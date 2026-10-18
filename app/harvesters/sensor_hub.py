from __future__ import annotations

import asyncio
from typing import Any

from app.clients.sensor_hub import SensorHubClient
from app.models.catalog import (
    CatalogAccess,
    CatalogDistribution,
    CatalogLocation,
    CatalogObservedProperty,
    CatalogSource,
    CatalogTemporalCoverage,
    CanonicalDataset,
)


_QUDT_UNIT_URIS = {
    "Cel": "http://qudt.org/vocab/unit/DEG_C",
    "DEG_C": "http://qudt.org/vocab/unit/DEG_C",
    "%": "http://qudt.org/vocab/unit/PERCENT",
    "PERCENT": "http://qudt.org/vocab/unit/PERCENT",
    "Pa": "http://qudt.org/vocab/unit/PA",
    "PA": "http://qudt.org/vocab/unit/PA",
    "hPa": "http://qudt.org/vocab/unit/HectoPA",
    "HectoPA": "http://qudt.org/vocab/unit/HectoPA",
    "m": "http://qudt.org/vocab/unit/M",
    "M": "http://qudt.org/vocab/unit/M",
    "m/s": "http://qudt.org/vocab/unit/M-PER-SEC",
    "M-PER-SEC": "http://qudt.org/vocab/unit/M-PER-SEC",
}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


class SensorHubHarvester:
    """Harvest descriptive Sensor Hub metadata without copying readings."""

    def __init__(self, client: SensorHubClient) -> None:
        self.client = client

    async def harvest_metadata(self) -> dict[str, list[dict[str, Any]]]:
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
            "locations": locations,
            "sources": sources,
            "deployments": deployments,
            "properties": properties,
            "deployment_properties": deployment_properties,
        }

    async def preview(self) -> dict[str, Any]:
        metadata = await self.harvest_metadata()
        return {
            "provider": "sensor-hub",
            "counts": {key: len(value) for key, value in metadata.items()},
            "dataset_candidates": len(metadata["deployment_properties"]),
            "readings_harvested": False,
        }

    async def datasets(self) -> list[CanonicalDataset]:
        metadata = await self.harvest_metadata()
        candidate_ids = sorted(
            int(item["id"]) for item in metadata["deployment_properties"]
        )

        deployment_properties = await self._fetch_details(
            "deployment-properties", candidate_ids
        )
        deployments = await self._fetch_details(
            "deployments",
            {int(item["deployment_id"]) for item in deployment_properties.values()},
        )
        properties = await self._fetch_details(
            "properties",
            {int(item["property_id"]) for item in deployment_properties.values()},
        )
        sources = await self._fetch_details(
            "sources",
            {int(item["source_id"]) for item in deployments.values()},
        )
        locations = await self._fetch_details(
            "locations",
            {int(item["location_id"]) for item in deployments.values()},
        )

        datasets: list[CanonicalDataset] = []
        for candidate_id in candidate_ids:
            deployment_property = deployment_properties[candidate_id]
            deployment = deployments[int(deployment_property["deployment_id"])]
            prop = properties[int(deployment_property["property_id"])]
            source = sources[int(deployment["source_id"])]
            location = locations[int(deployment["location_id"])]
            datasets.append(
                self._to_dataset(
                    deployment_property=deployment_property,
                    deployment=deployment,
                    prop=prop,
                    source=source,
                    location=location,
                )
            )

        return datasets

    async def _fetch_details(
        self,
        resource: str,
        ids: set[int] | list[int],
        *,
        concurrency: int = 10,
    ) -> dict[int, dict[str, Any]]:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch(resource_id: int) -> tuple[int, dict[str, Any]]:
            async with semaphore:
                detail = await self.client.get_detail(resource, resource_id)
                return resource_id, detail

        pairs = await asyncio.gather(*(fetch(resource_id) for resource_id in ids))
        return dict(pairs)

    def _to_dataset(
        self,
        *,
        deployment_property: dict[str, Any],
        deployment: dict[str, Any],
        prop: dict[str, Any],
        source: dict[str, Any],
        location: dict[str, Any],
    ) -> CanonicalDataset:
        deployment_property_id = int(deployment_property["id"])
        identifier = (
            "urn:pipi:dataset:sensor-hub:deployment-property:"
            f"{deployment_property_id}"
        )
        property_label = str(prop["name"]).replace("_", " ")
        title = f"{property_label} - {location['name']} - {source['name']}"

        description_parts = [
            _optional_text(prop.get("description")),
            _optional_text(deployment.get("purpose")),
            _optional_text(deployment_property.get("observation_target")),
        ]
        description = " ".join(part for part in description_parts if part)
        if not description:
            description = (
                f"{property_label} observations from {source['name']} "
                f"at {location['name']}."
            )

        unit_code = _optional_text(deployment_property.get("unit")) or _optional_text(
            prop.get("default_unit")
        )
        base_url = self.client.base_url.rstrip("/")
        service_root = base_url.rsplit("/api/v1", 1)[0]
        readings_url = f"{base_url}/readings"
        data_service_identifier = "urn:pipi:dataservice:sensor-hub"

        active_from = _optional_text(deployment.get("active_from"))
        active_to = _optional_text(deployment.get("active_to"))
        is_active_raw = deployment_property.get("is_active")

        property_name = str(prop["name"])
        keywords = [
            "sensor",
            property_label,
            str(location["name"]),
            str(source["name"]),
        ]

        distribution = CatalogDistribution(
            identifier=f"{identifier}:distribution:api",
            title="Sensor Hub API access",
            access_url=readings_url,
            media_type="application/json",
            format="JSON",
            access_service_identifier=data_service_identifier,
            endpoint_url=base_url,
            endpoint_description=f"{service_root}/docs/",
            kind="api",
        )

        return CanonicalDataset(
            catalog_id=f"sensor-hub:deployment-property:{deployment_property_id}",
            identifier=identifier,
            title=title,
            description=description,
            publisher=str(source.get("provider") or source.get("owner") or "Unknown"),
            license=str(source.get("license") or "unknown"),
            dataset_type="sensor-observation",
            source_system="sensor-hub",
            external_id=str(deployment_property_id),
            keywords=keywords,
            source=CatalogSource.model_validate(source),
            location=CatalogLocation.model_validate(location),
            temporal=CatalogTemporalCoverage(start=active_from, end=active_to),
            distributions=[distribution],
            observed_property=CatalogObservedProperty(
                id=int(prop["id"]),
                name=property_name,
                description=_optional_text(prop.get("description")),
                quantity_kind=_optional_text(prop.get("quantity_kind")),
                semantic_uri=_optional_text(prop.get("semantic_uri")),
                data_type=_optional_text(prop.get("data_type")),
                unit_code=unit_code,
                unit_uri=_QUDT_UNIT_URIS.get(unit_code) if unit_code else None,
            ),
            sampling_interval_seconds=_optional_int(
                deployment_property.get("sampling_interval")
            ),
            resolution=_optional_float(deployment_property.get("resolution")),
            uncertainty=_optional_text(deployment_property.get("uncertainty")),
            min_value=_optional_float(deployment_property.get("min_value")),
            max_value=_optional_float(deployment_property.get("max_value")),
            is_active=(bool(is_active_raw) if is_active_raw is not None else None),
            observation_target=_optional_text(
                deployment_property.get("observation_target")
            ),
            access=CatalogAccess(
                provider="sensor-hub",
                data_service_identifier=data_service_identifier,
                endpoint_url=base_url,
                endpoint_description=f"{service_root}/docs/",
                readings_url=readings_url,
                deployment_property_id=deployment_property_id,
                dataset_scoped_filtering_available=False,
            ),
            extensions={
                "sensor_hub": {
                    "deployment_id": deployment.get("id"),
                    "property_id": prop.get("id"),
                }
            },
        )
