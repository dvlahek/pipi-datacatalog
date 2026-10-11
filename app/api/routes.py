from fastapi import APIRouter, HTTPException, Query

from app.catalog.service import build_catalog
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
        return await build_catalog(client)


def _matches_dataset_ref(dataset: CanonicalDataset, dataset_ref: str) -> bool:
    if dataset.catalog_id == dataset_ref:
        return True
    if dataset.identifier == dataset_ref:
        return True
    if dataset.external_id == dataset_ref:
        return True
    if (
        dataset_ref.isdigit()
        and dataset.access is not None
        and dataset.access.deployment_property_id == int(dataset_ref)
    ):
        return True
    return False


async def _dataset(dataset_ref: str) -> CanonicalDataset:
    datasets = await _datasets()
    for dataset in datasets:
        if _matches_dataset_ref(dataset, dataset_ref):
            return dataset
    raise HTTPException(status_code=404, detail="Dataset not found.")


def _dataset_result_id(dataset: CanonicalDataset) -> int | str:
    if dataset.access is not None:
        return dataset.access.deployment_property_id
    return dataset.catalog_id


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/api/v1/providers")
async def list_providers() -> dict[str, object]:
    return {
        "count": 2,
        "data": [
            {
                "name": "sensor-hub",
                "kind": "api",
                "description": "PiPi Sensor Hub metadata provider",
            },
            {
                "name": "static-web",
                "kind": "external-web-resource",
                "description": "Manually registered external web datasets",
            },
        ],
    }


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
                    "dataset_id": _dataset_result_id(dataset),
                    "identifier": dataset.identifier,
                    "source_system": dataset.source_system,
                    **validation,
                }
            )

        failed = [item for item in items if item["conforms"] is False]
        return {
            "profile": "pipi-dcat-core-shacl-v2",
            "count": len(items),
            "conforms": len(failed) == 0,
            "conforms_count": len(items) - len(failed),
            "failed_count": len(failed),
            "data": items,
        }
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}.jsonld")
async def get_dataset_jsonld(dataset_ref: str) -> dict[str, object]:
    try:
        return dataset_to_jsonld(await _dataset(dataset_ref))
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}/validation")
async def validate_dataset_semantics(dataset_ref: str) -> dict[str, object]:
    try:
        dataset = await _dataset(dataset_ref)
        return {
            "dataset_id": _dataset_result_id(dataset),
            "identifier": dataset.identifier,
            "source_system": dataset.source_system,
            **validate_dataset_jsonld(dataset_to_jsonld(dataset)),
        }
    except SensorHubError as exc:
        _raise_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}")
async def get_dataset(dataset_ref: str) -> dict[str, object]:
    try:
        dataset = await _dataset(dataset_ref)
        return {"data": dataset.model_dump()}
    except SensorHubError as exc:
        _raise_http(exc)
