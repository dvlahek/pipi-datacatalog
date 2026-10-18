from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.catalog.service import catalog_store, load_catalog, sync_catalog
from app.clients.sensor_hub import (
    SensorHubAuthenticationError,
    SensorHubClient,
    SensorHubConfigurationError,
    SensorHubError,
)
from app.config import get_settings
from app.harvest.history import HarvestHistoryStore
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


def _raise_store_http(exc: Exception) -> None:
    raise HTTPException(status_code=503, detail=f"Catalog store unavailable: {exc}") from exc


async def _datasets() -> list[CanonicalDataset]:
    settings = get_settings()
    async with _client() as client:
        return await load_catalog(client, settings)


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


def _persistent_store():
    settings = get_settings()
    if not settings.catalog_store_enabled:
        raise HTTPException(
            status_code=409,
            detail="Dataset version history requires CATALOG_STORE_ENABLED=true.",
        )
    try:
        store = catalog_store(settings)
        assert store is not None
        return store
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/api/v1/providers")
async def list_providers() -> dict[str, object]:
    settings = get_settings()
    providers: list[dict[str, object]] = []

    if settings.provider_sensor_hub_enabled:
        providers.append(
            {
                "name": "sensor-hub",
                "kind": "api",
                "description": "PiPi Sensor Hub metadata provider",
            }
        )
    if settings.provider_static_web_enabled:
        providers.append(
            {
                "name": "static-web",
                "kind": "external-web-resource",
                "description": "Manually registered external web datasets",
            }
        )
    if settings.provider_csv_enabled:
        providers.append(
            {
                "name": "csv-files",
                "kind": "file",
                "description": "Version-aware CSV file metadata provider",
            }
        )
    if settings.provider_foi_documents_enabled:
        providers.append(
            {
                "name": "foi-documents",
                "kind": "public-document-catalog",
                "description": "Public FOI Dokumenti discovery provider",
            }
        )

    return {"count": len(providers), "data": providers}


@router.get("/api/v1/catalog/status")
async def catalog_status() -> dict[str, object]:
    settings = get_settings()
    if not settings.catalog_store_enabled:
        return {
            "mode": "live",
            "persistent": False,
            "stored_datasets": None,
        }

    try:
        store = catalog_store(settings)
        assert store is not None
        return {
            "mode": "persistent",
            "persistent": True,
            "stored_datasets": store.count_datasets(),
            "database": "postgresql" if settings.database_url and settings.database_url.startswith("postgresql") else "sqlalchemy",
            "versioning": "immutable-snapshot-history",
        }
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


@router.get("/api/v1/harvest/runs")
async def list_harvest_runs(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    store = _persistent_store()
    runs = HarvestHistoryStore(store).list(limit=limit)
    return {"count": len(runs), "data": runs}


@router.post("/api/v1/catalog/sync")
async def sync_catalog_metadata() -> dict[str, object]:
    """Merge provider metadata into the catalog and create versions on changes."""

    settings = get_settings()
    if not settings.catalog_store_enabled:
        raise HTTPException(
            status_code=409,
            detail="Persistent catalog store is disabled. Set CATALOG_STORE_ENABLED=true.",
        )

    store = _persistent_store()
    history = HarvestHistoryStore(store)
    run_id = history.start("provider-sync", trigger="manual")

    try:
        async with _client() as client:
            stats = await sync_catalog(client, settings)
        run_status = "partial" if int(stats.get("provider_errors", 0)) else "ok"
        history.finish(run_id, status=run_status, summary=stats)
        return {
            "status": run_status,
            "mode": "version-aware-upsert",
            "harvest_run_id": run_id,
            **stats,
        }
    except SensorHubError as exc:
        history.finish(run_id, status="error", error=str(exc))
        _raise_http(exc)
    except (RuntimeError, SQLAlchemyError) as exc:
        history.finish(run_id, status="error", error=str(exc))
        _raise_store_http(exc)


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
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


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
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


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
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}.jsonld")
async def get_dataset_jsonld(dataset_ref: str) -> dict[str, object]:
    try:
        return dataset_to_jsonld(await _dataset(dataset_ref))
    except SensorHubError as exc:
        _raise_http(exc)
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


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
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}/versions")
async def list_dataset_versions(dataset_ref: str) -> dict[str, object]:
    try:
        dataset = await _dataset(dataset_ref)
        store = _persistent_store()
        versions = store.list_versions(dataset.identifier)
        return {
            "identifier": dataset.identifier,
            "count": len(versions),
            "data": versions,
        }
    except SensorHubError as exc:
        _raise_http(exc)
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}/versions/{version}")
async def get_dataset_version(dataset_ref: str, version: int) -> dict[str, object]:
    try:
        current = await _dataset(dataset_ref)
        store = _persistent_store()
        historical = store.get_version(current.identifier, version)
        if historical is None:
            raise HTTPException(status_code=404, detail="Dataset version not found.")
        return {
            "version": version,
            "data": historical.model_dump(),
        }
    except SensorHubError as exc:
        _raise_http(exc)
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)


@router.get("/api/v1/datasets/{dataset_ref}")
async def get_dataset(dataset_ref: str) -> dict[str, object]:
    try:
        dataset = await _dataset(dataset_ref)
        return {"data": dataset.model_dump()}
    except SensorHubError as exc:
        _raise_http(exc)
    except (RuntimeError, SQLAlchemyError) as exc:
        _raise_store_http(exc)
