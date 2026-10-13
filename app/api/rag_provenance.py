from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import compare_profiles, replay_retrieval_run
from app.rag.profiles import (
    get_retrieval_profile,
    record_retrieval_run,
)

router = APIRouter(prefix="/api/v1/rag", tags=["rag-provenance"])


def _store():
    settings = get_settings()
    if not settings.catalog_store_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persistent catalog store is required for retrieval provenance.",
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


@router.get("/compare")
async def compare_retrieval_profiles(
    q: str = Query(min_length=2, max_length=500),
    left: str = Query(default="hybrid-e5-content-v1"),
    right: str = Query(default="hybrid-e5-metadata-v1"),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, object]:
    store = _store()
    settings = get_settings()
    try:
        payload = compare_profiles(
            store,
            settings,
            q,
            left_profile_id=left,
            right_profile_id=right,
            limit=limit,
        )
        left_profile = get_retrieval_profile(left)
        right_profile = get_retrieval_profile(right)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Retrieval profile not found: {exc.args[0]}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    left_result = dict(payload["left"])
    right_result = dict(payload["right"])
    left_run_id = record_retrieval_run(
        store,
        query=q,
        profile=left_profile,
        retrieval=str(left_result.get("retrieval") or "unknown"),
        top_k=limit,
        result=left_result,
    )
    right_run_id = record_retrieval_run(
        store,
        query=q,
        profile=right_profile,
        retrieval=str(right_result.get("retrieval") or "unknown"),
        top_k=limit,
        result=right_result,
    )
    payload["left_run_id"] = left_run_id
    payload["right_run_id"] = right_run_id
    return payload


@router.post("/runs/{run_id}/replay")
async def replay_run(run_id: int) -> dict[str, object]:
    store = _store()
    settings = get_settings()
    try:
        payload = replay_retrieval_run(store, settings, run_id)
        profile = get_retrieval_profile(str(payload["profile_id"]))
    except KeyError as exc:
        if exc.args and exc.args[0] == run_id:
            raise HTTPException(status_code=404, detail="Retrieval run not found.") from exc
        raise HTTPException(status_code=404, detail=f"Retrieval profile not found: {exc.args[0]}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    replayed = dict(payload["replayed_result"])
    replayed["replay_of_run_id"] = run_id
    replay_run_id = record_retrieval_run(
        store,
        query=str(payload["query"]),
        profile=profile,
        retrieval=str(replayed.get("retrieval") or "unknown"),
        top_k=int(payload["drift"]["top_k"]),
        result=replayed,
    )
    payload["replay_run_id"] = replay_run_id
    return payload
