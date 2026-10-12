from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.service import RagIndexError, index_registered_resource
from app.rag.store import RagStore

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


def _store():
    settings = get_settings()
    if not settings.catalog_store_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persistent catalog store is required for RAG indexing.",
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


def _resource_or_404(resource_id: int) -> tuple[object, dict[str, object]]:
    store = _store()
    resource = store.get_resource(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    return store, resource


@router.post("/resources/{resource_id}/index")
async def index_resource(resource_id: int) -> dict[str, object]:
    settings = get_settings()
    store, _ = _resource_or_404(resource_id)
    try:
        return await index_registered_resource(store, resource_id, settings)
    except RagIndexError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/resources/{resource_id}/status")
async def rag_resource_status(resource_id: int) -> dict[str, object]:
    store, resource = _resource_or_404(resource_id)
    dataset_identifier = resource.get("dataset_identifier")
    if not dataset_identifier:
        return {
            "resource_id": resource_id,
            "status": "not_indexed",
            "dataset_identifier": None,
            "document": None,
        }

    document = RagStore(store).document_status(str(dataset_identifier))
    return {
        "resource_id": resource_id,
        "status": "indexed" if document is not None else "not_indexed",
        "dataset_identifier": dataset_identifier,
        "document": document,
    }


@router.get("/resources/{resource_id}/chunks")
async def rag_resource_chunks(
    resource_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    store, resource = _resource_or_404(resource_id)
    dataset_identifier = resource.get("dataset_identifier")
    if not dataset_identifier:
        return {"resource_id": resource_id, "count": 0, "offset": offset, "data": []}

    chunks = RagStore(store).list_chunks(
        str(dataset_identifier),
        offset=offset,
        limit=limit,
    )
    return {
        "resource_id": resource_id,
        "count": len(chunks),
        "offset": offset,
        "limit": limit,
        "data": chunks,
    }
