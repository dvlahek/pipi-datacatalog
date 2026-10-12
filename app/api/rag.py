from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.activity.store import ActivityStore, RagJobStore
from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.jobs import run_dataset_index_job, run_resource_index_job
from app.rag.maintenance import reindex_stale_datasets
from app.rag.service import RagIndexError, index_catalog_dataset, index_registered_resource
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


@router.get("/search")
async def rag_search(
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, object]:
    results = RagStore(_store()).search_chunks(q, limit=limit)
    return {
        "query": q,
        "retrieval": "lexical-baseline-v1-current-only",
        "count": len(results),
        "data": [
            {"rank": rank, **item}
            for rank, item in enumerate(results, start=1)
        ],
    }


@router.get("/status")
async def rag_status() -> dict[str, object]:
    data = RagStore(_store()).list_index_statuses()
    counts = {
        "indexed": sum(1 for item in data if item["status"] == "indexed"),
        "stale": sum(1 for item in data if item["status"] == "stale"),
        "not_indexed": sum(1 for item in data if item["status"] == "not_indexed"),
    }
    return {
        "count": len(data),
        "counts": counts,
        "data": data,
    }


@router.post("/reindex-stale")
async def reindex_stale(
    limit: int | None = Query(default=None, ge=1, le=100),
) -> dict[str, object]:
    settings = get_settings()
    return await reindex_stale_datasets(_store(), settings, limit=limit)


@router.post("/jobs/datasets/{dataset_identifier:path}", status_code=status.HTTP_202_ACCEPTED)
async def queue_dataset_index(
    dataset_identifier: str,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    settings = get_settings()
    store = _store()
    dataset = next((item for item in store.list_datasets() if item.identifier == dataset_identifier), None)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Catalog dataset not found.")

    jobs = RagJobStore(store)
    active = jobs.active_for_target("dataset", dataset_identifier)
    if active is not None:
        return {"accepted": False, "reason": "already-running", "job": active}

    job = jobs.create(target_kind="dataset", target_identifier=dataset_identifier, label=dataset.title)
    ActivityStore(store).log(
        "info",
        "rag",
        "index-queued",
        f"Queued background indexing for {dataset.title}.",
        details={"job_id": job["id"], "dataset_identifier": dataset_identifier},
    )
    background_tasks.add_task(
        run_dataset_index_job,
        store,
        settings,
        int(job["id"]),
        dataset_identifier,
        dataset.title,
    )
    return {"accepted": True, "job": job}


@router.post("/jobs/resources/{resource_id}", status_code=status.HTTP_202_ACCEPTED)
async def queue_resource_index(
    resource_id: int,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    settings = get_settings()
    store, resource = _resource_or_404(resource_id)
    if not bool(resource.get("enabled")):
        raise HTTPException(status_code=422, detail="Disabled resources cannot be indexed.")

    target_identifier = str(resource_id)
    label = str(resource.get("name") or resource.get("source_url") or f"Resource {resource_id}")
    jobs = RagJobStore(store)
    active = jobs.active_for_target("resource", target_identifier)
    if active is not None:
        return {"accepted": False, "reason": "already-running", "job": active}

    job = jobs.create(target_kind="resource", target_identifier=target_identifier, label=label)
    ActivityStore(store).log(
        "info",
        "rag",
        "index-queued",
        f"Queued background indexing for {label}.",
        details={"job_id": job["id"], "resource_id": resource_id},
    )
    background_tasks.add_task(
        run_resource_index_job,
        store,
        settings,
        int(job["id"]),
        resource_id,
        label,
    )
    return {"accepted": True, "job": job}


@router.get("/jobs")
async def list_index_jobs(
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, object]:
    data = RagJobStore(_store()).list(limit=limit)
    return {"count": len(data), "data": data}


@router.get("/jobs/{job_id}")
async def index_job(job_id: int) -> dict[str, object]:
    job = RagJobStore(_store()).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Indexing job not found.")
    return job


# Synchronous indexing endpoints are kept for scripts/backward compatibility.
# The web portal uses the background job endpoints above.
@router.post("/datasets/{dataset_identifier:path}/index")
async def index_dataset(dataset_identifier: str) -> dict[str, object]:
    settings = get_settings()
    store = _store()
    try:
        return await index_catalog_dataset(store, dataset_identifier, settings)
    except RagIndexError as exc:
        detail = str(exc)
        code = 404 if detail == "Catalog dataset not found." else 422
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/datasets/{dataset_identifier:path}/status")
async def rag_dataset_status(dataset_identifier: str) -> dict[str, object]:
    store = _store()
    if not any(item.identifier == dataset_identifier for item in store.list_datasets()):
        raise HTTPException(status_code=404, detail="Catalog dataset not found.")
    return RagStore(store).index_status(dataset_identifier)


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
            "catalog_version": None,
            "indexed_version": None,
            "document": None,
        }

    status_payload = RagStore(store).index_status(str(dataset_identifier))
    return {
        "resource_id": resource_id,
        **status_payload,
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
