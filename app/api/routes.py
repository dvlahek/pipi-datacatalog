from fastapi import APIRouter, HTTPException, Query

from app.clients.sensor_hub import (
    SensorHubAuthenticationError,
    SensorHubClient,
    SensorHubConfigurationError,
    SensorHubError,
)
from app.config import get_settings
from app.harvesters.sensor_hub import SensorHubHarvester
from app.models.catalog import CanonicalDataset
from app.search.catalog import search_datasets
from app.semantic.dcat import dataset_to_jsonld
from app.semantic.shacl import validate_dataset_jsonld

router = APIRouter()


def _client() -> SensorHubClient:
    settings = get_settings()
    return SensorHubClient(
        base_url=settings.sensor_hub_base_url,
        username=settings.sensor_hub_username,
        password=settings.sensor_hub_password,
        timeout_seconds=settings.sensor_hub_timeout_seconds,
    )


def _raise_http(exc: SensorHubError) -> None:
    if isinstance(exc, SensorHubConfigurationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, SensorHubAuthenticationError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _datasets() -> list[CanonicalDataset]:
    async with _client() as client:
        harvester = SensorHubHarvester(client)
        return await harvester.datasets()


async def _dataset(dataset_id: int) -> CanonicalDataset:
    datasets = await _datasets()
    for dataset in datasets:
        if dataset.access.deployment_property_id == dataset_id:
            return dataset
    raise HTTPException(status_code=404, detail="Dataset not found.")


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/api/v1/providers/sensor-hub/status")
async def sensor_hub_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "provider": "sensor-hub",
        "base_url": settings.sensor_hub_base_url,
        "configured": settings.sensor_hub_configured,
    }


@router.get("/api/v1/providers/sensor-hub/sources")
async def sensor_hub_sources() -> dict[str, object]:
    try:
        async with _client() as client:
            sources = await client.list_sources()
        return {"provider": "sensor-hub", "count": len(sources), "data": sources}
    except SensorHubError as exc:
        _raise_http(exc)


@router.post("/api/v1/harvest/sensor-hub/preview")
async def sensor_hub_harvest_preview() -> dict[str, object]:
    try:
        async with _client() as client:
            harvester = SensorHubHarvester(client)
            return await harvester.preview()
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets")
async def list_datasets() -> dict[str, object]:
    try:
        datasets = await _datasets()
        return {
            "count": len(datasets),
            "data": [dataset.model_dump() for dataset in datasets],
        }
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/search")
async def search_catalog(
    q: str = Query(min_length=1, max_length=200),
) -> dict[str, object]:
    try:
        datasets = await _datasets()
        results = search_datasets(datasets, q)
        return {"query": q, "count": len(results), "data": results}
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/semantic/validation")
async def validate_catalog_semantics() -> dict[str, object]:
    try:
        datasets = await _datasets()
        items: list[dict[str, object]] = []

        for dataset in datasets:
            validation = validate_dataset_jsonld(dataset_to_jsonld(dataset))
            items.append(
                {
                    "dataset_id": dataset.access.deployment_property_id,
                    "identifier": dataset.identifier,
                    **validation,
                }
            )

        failed = [item for item in items if item["conforms"] is False]
        return {
            "profile": "pipi-dcat-core-shacl-v1",
            "count": len(items),
            "conforms": len(failed) == 0,
            "conforms_count": len(items) - len(failed),
            "failed_count": len(failed),
            "data": items,
        }
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets/{dataset_id}.jsonld")
async def get_dataset_jsonld(dataset_id: int) -> dict[str, object]:
    try:
        return dataset_to_jsonld(await _dataset(dataset_id))
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets/{dataset_id}/validation")
async def validate_dataset_semantics(dataset_id: int) -> dict[str, object]:
    try:
        dataset = await _dataset(dataset_id)
        return {
            "dataset_id": dataset_id,
            "identifier": dataset.identifier,
            **validate_dataset_jsonld(dataset_to_jsonld(dataset)),
        }
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets/{dataset_id}")
async def get_dataset(dataset_id: int) -> dict[str, object]:
    try:
        dataset = await _dataset(dataset_id)
        return {"data": dataset.model_dump()}
    except SensorHubError as exc:
        _raise_http(exc)
