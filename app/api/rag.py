from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.activity.store import ActivityStore, RagJobStore
from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.embeddings import EmbeddingError, get_embedding_provider
from app.rag.jobs import run_dataset_index_job, run_embedding_backfill_job, run_resource_index_job
from app.rag.maintenance import reindex_stale_datasets
from app.rag.profiles import (
    ensure_builtin_profiles,
    get_retrieval_profile,
    get_retrieval_run,
    list_retrieval_runs,
    record_retrieval_run,
    settings_for_profile,
)
from app.rag.search import search_rag
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


def _profile_or_404(profile_id: str):
    try:
        return get_retrieval_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Retrieval profile not found.") from exc


@router.get("/profiles")
async def retrieval_profiles() -> dict[str, object]:
    store = _store()
    settings = get_settings()
    profiles = ensure_builtin_profiles(store)
    data: list[dict[str, object]] = []
    for item in profiles:
        row = dict(item)
        profile = get_retrieval_profile(str(row["profile_id"]))
        if profile.embedding_provider is None:
            row["embedding_status"] = None
        else:
            profile_settings = settings_for_profile(settings, profile)
            provider = get_embedding_provider(profile_settings)
            row["embedding_status"] = RagStore(store).embedding_status(provider.name)
            row["embedding_identity"] = provider.name
        data.append(row)
    return {"count": len(data), "data": data}


@router.get("/search")
async def rag_search(
    q: str = Query(min_length=2, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
    mode: str = Query(default="hybrid", pattern="^(lexical|vector|hybrid)$"),
    profile: str | None = Query(default=None),
) -> dict[str, object]:
    settings = get_settings()
    store = _store()
    selected_profile = None
    if profile is not None:
        selected_profile = _profile_or_404(profile)
        ensure_builtin_profiles(store)
    try:
        payload = search_rag(
            store,
            settings,
            q,
            limit=limit,
            mode=mode,
            profile_id=profile,
        )
    except RuntimeError as exc:
        effective_mode = selected_profile.mode if selected_profile is not None else mode
        if effective_mode == "vector":
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise

    run_id = record_retrieval_run(
        store,
        query=q,
        profile=selected_profile,
        retrieval=str(payload.get("retrieval") or "unknown"),
        top_k=limit,
        result=payload,
    )
    if run_id is not None:
        payload["retrieval_run_id"] = run_id
    return payload


@router.get("/embeddings/status")
async def embedding_status(
    profile: str | None = Query(default=None),
) -> dict[str, object]:
    settings = get_settings()
    profile_payload = None
    if profile is not None:
        selected = _profile_or_404(profile)
        if selected.embedding_provider is None:
            return {
                "available": True,
                "profile": selected.public_dict(),
                "not_applicable": True,
                "model": None,
                "dimensions": None,
                "total_current_chunks": 0,
                "embedded_current_model": 0,
                "missing": 0,
                "complete": True,
            }
        settings = settings_for_profile(settings, selected)
        profile_payload = selected.public_dict()
    try:
        provider = get_embedding_provider(settings)
        payload = RagStore(_store()).embedding_status(provider.name)
        return {
            "available": True,
            "profile": profile_payload,
            "provider": settings.rag_embedding_provider,
            "model": provider.name,
            "dimensions": provider.dimensions,
            **payload,
        }
    except (EmbeddingError, RuntimeError, SQLAlchemyError) as exc:
        return {
            "available": False,
            "profile": profile_payload,
            "provider": settings.rag_embedding_provider,
            "model": settings.rag_embedding_model,
            "dimensions": settings.rag_embedding_dimensions,
            "error": str(exc),
        }


@router.post("/embeddings/jobs/backfill", status_code=status.HTTP_202_ACCEPTED)
async def queue_embedding_backfill(
    background_tasks: BackgroundTasks,
    limit: int | None = Query(default=None, ge=1, le=50000),
    profile: str | None = Query(default=None),
) -> dict[str, object]:
    settings = get_settings()
    store = _store()
    selected_profile = None
    if profile is not None:
        selected_profile = _profile_or_404(profile)
        ensure_builtin_profiles(store)
        if selected_profile.embedding_provider is None:
            raise HTTPException(status_code=422, detail="Lexical profiles do not require vectors.")
        settings = settings_for_profile(settings, selected_profile)
    try:
        target = get_embedding_provider(settings).name
    except EmbeddingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    jobs = RagJobStore(store)
    active = jobs.active_for_target("embedding-backfill", target)
    if active is not None:
        return {"accepted": False, "reason": "already-running", "job": active}

    job = jobs.create(
        target_kind="embedding-backfill",
        target_identifier=target,
        label=f"Vector backfill · {target}",
    )
    ActivityStore(store).log(
        "info",
        "rag",
        "embedding-backfill-queued",
        f"Queued vector backfill for {target}.",
        details={
            "job_id": job["id"],
            "limit": limit,
            "profile_id": None if selected_profile is None else selected_profile.profile_id,
        },
    )
    background_tasks.add_task(
        run_embedding_backfill_job,
        store,
        settings,
        int(job["id"]),
        limit,
    )
    return {"accepted": True, "job": job}


@router.get("/runs")
async def retrieval_runs(
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, object]:
    data = list_retrieval_runs(_store(), limit=limit)
    return {"count": len(data), "data": data}


@router.get("/runs/{run_id}")
async def retrieval_run(run_id: int) -> dict[str, object]:
    row = get_retrieval_run(_store(), run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Retrieval run not found.")
    return row


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
