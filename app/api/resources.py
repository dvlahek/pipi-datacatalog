from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.catalog.service import catalog_store
from app.config import get_settings
from app.harvest.history import HarvestHistoryStore
from app.models.resource import ResourceCreate
from app.resources.service import (
    refresh_enabled_resources,
    refresh_registered_resource,
    register_resource,
)
from app.security.url_policy import UnsafeResourceURL

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


def _store():
    settings = get_settings()
    if not settings.catalog_store_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persistent catalog store is required for the resource registry.",
        )
    try:
        store = catalog_store(settings)
        assert store is not None
        return store
    except (RuntimeError, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Catalog store unavailable: {exc}",
        ) from exc


@router.get("")
async def list_resources() -> dict[str, object]:
    resources = _store().list_resources()
    return {"count": len(resources), "data": resources}


@router.post("/refresh-enabled")
async def refresh_all_enabled_resources() -> dict[str, object]:
    settings = get_settings()
    store = _store()
    history = HarvestHistoryStore(store)
    run_id = history.start("resource-refresh", trigger="manual")
    try:
        result = await refresh_enabled_resources(store, settings)
        run_status = "partial" if int(result.get("errors", 0)) else "ok"
        history.finish(run_id, status=run_status, summary=result)
        return {**result, "harvest_run_id": run_id}
    except Exception as exc:
        history.finish(run_id, status="error", error=str(exc))
        raise


@router.get("/{resource_id}")
async def get_resource(resource_id: int) -> dict[str, object]:
    resource = _store().get_resource(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    return {"data": resource}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resource(payload: ResourceCreate) -> dict[str, object]:
    settings = get_settings()
    store = _store()
    try:
        return await register_resource(store, payload, settings)
    except UnsafeResourceURL as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{resource_id}/refresh")
async def refresh_resource(resource_id: int) -> dict[str, object]:
    settings = get_settings()
    store = _store()
    if store.get_resource(resource_id) is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    return await refresh_registered_resource(store, resource_id, settings)


@router.delete("/{resource_id}")
async def disable_resource(resource_id: int) -> dict[str, object]:
    store = _store()
    try:
        resource = store.set_resource_enabled(resource_id, False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Resource not found.") from exc
    return {
        "status": "disabled",
        "data": resource,
        "note": "Dataset metadata and version history are retained.",
    }


@router.post("/{resource_id}/enable")
async def enable_resource(resource_id: int) -> dict[str, object]:
    store = _store()
    try:
        resource = store.set_resource_enabled(resource_id, True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Resource not found.") from exc
    return {"status": "enabled", "data": resource}
