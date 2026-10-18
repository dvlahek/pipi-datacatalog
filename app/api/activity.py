from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.activity.store import ActivityStore
from app.catalog.service import catalog_store
from app.config import get_settings

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


def _store():
    settings = get_settings()
    if not settings.catalog_store_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persistent catalog store is required for activity logging.",
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
async def activity_log(
    limit: int = Query(default=30, ge=1, le=200),
    level: str | None = Query(default=None, pattern="^(info|warning|error)$"),
) -> dict[str, object]:
    data = ActivityStore(_store()).list(limit=limit, level=level)
    counts = {
        "info": sum(1 for item in data if item["level"] == "info"),
        "warning": sum(1 for item in data if item["level"] == "warning"),
        "error": sum(1 for item in data if item["level"] == "error"),
    }
    return {"count": len(data), "counts": counts, "data": data}
