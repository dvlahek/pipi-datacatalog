from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, insert, select, update

from app.catalog.store import CatalogStore


metadata = MetaData()

rag_index_jobs = Table(
    "rag_index_jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("target_kind", String, nullable=False, index=True),
    Column("target_identifier", Text, nullable=False),
    Column("label", Text, nullable=True),
    Column("status", String, nullable=False, default="queued", index=True),
    Column("stage", String, nullable=True),
    Column("message", Text, nullable=True),
    Column("progress_current", Integer, nullable=True),
    Column("progress_total", Integer, nullable=True),
    Column("result", JSON, nullable=False, default=dict),
    Column("error", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
)

activity_events = Table(
    "activity_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("level", String, nullable=False, index=True),
    Column("category", String, nullable=False, index=True),
    Column("action", String, nullable=False),
    Column("message", Text, nullable=False),
    Column("details", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _json_safe(value: dict[str, Any] | None) -> dict[str, Any]:
    return json.loads(json.dumps(value or {}, ensure_ascii=False, default=str))


class ActivityStore:
    def __init__(self, catalog_store: CatalogStore) -> None:
        self.engine = catalog_store.engine
        if self.engine.dialect.name != "postgresql":
            metadata.create_all(self.engine, tables=[activity_events], checkfirst=True)

    def log(
        self,
        level: str,
        category: str,
        action: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            result = connection.execute(
                insert(activity_events)
                .values(
                    level=level.lower(),
                    category=category,
                    action=action,
                    message=message[:4000],
                    details=_json_safe(details),
                    created_at=now,
                )
                .returning(activity_events)
            )
            row = result.mappings().one()
            return self._row_dict(row)

    def list(self, *, limit: int = 50, level: str | None = None) -> list[dict[str, Any]]:
        query = select(activity_events)
        if level:
            query = query.where(activity_events.c.level == level.lower())
        query = query.order_by(activity_events.c.created_at.desc(), activity_events.c.id.desc()).limit(limit)
        with self.engine.begin() as connection:
            rows = connection.execute(query).mappings().all()
            return [self._row_dict(row) for row in rows]

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "level": str(row["level"]),
            "category": str(row["category"]),
            "action": str(row["action"]),
            "message": str(row["message"]),
            "details": dict(row["details"] or {}),
            "created_at": row["created_at"],
        }


class RagJobStore:
    def __init__(self, catalog_store: CatalogStore) -> None:
        self.engine = catalog_store.engine
        if self.engine.dialect.name != "postgresql":
            metadata.create_all(self.engine, tables=[rag_index_jobs], checkfirst=True)

    def create(
        self,
        *,
        target_kind: str,
        target_identifier: str,
        label: str | None = None,
    ) -> dict[str, Any]:
        existing = self.active_for_target(target_kind, target_identifier)
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            result = connection.execute(
                insert(rag_index_jobs)
                .values(
                    target_kind=target_kind,
                    target_identifier=target_identifier,
                    label=label,
                    status="queued",
                    stage="queued",
                    message="Waiting to start.",
                    result={},
                    created_at=now,
                )
                .returning(rag_index_jobs)
            )
            return self._row_dict(result.mappings().one())

    def active_for_target(self, target_kind: str, target_identifier: str) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(rag_index_jobs)
                .where(
                    rag_index_jobs.c.target_kind == target_kind,
                    rag_index_jobs.c.target_identifier == target_identifier,
                    rag_index_jobs.c.status.in_(["queued", "running"]),
                )
                .order_by(rag_index_jobs.c.id.desc())
                .limit(1)
            ).mappings().first()
            return None if row is None else self._row_dict(row)

    def start(self, job_id: int, *, stage: str = "starting", message: str = "Starting indexing.") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return self._update(
            job_id,
            status="running",
            stage=stage,
            message=message,
            started_at=now,
            error=None,
        )

    def progress(
        self,
        job_id: int,
        *,
        stage: str,
        message: str,
        current: int | None = None,
        total: int | None = None,
    ) -> dict[str, Any]:
        return self._update(
            job_id,
            status="running",
            stage=stage,
            message=message,
            progress_current=current,
            progress_total=total,
        )

    def succeed(self, job_id: int, result: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return self._update(
            job_id,
            status="success",
            stage="finished",
            message="Indexing completed.",
            result=_json_safe(result),
            error=None,
            finished_at=now,
        )

    def fail(self, job_id: int, error: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return self._update(
            job_id,
            status="error",
            stage="failed",
            message="Indexing failed.",
            error=error[:4000],
            finished_at=now,
        )

    def get(self, job_id: int) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(rag_index_jobs).where(rag_index_jobs.c.id == job_id)
            ).mappings().first()
            return None if row is None else self._row_dict(row)

    def list(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(rag_index_jobs)
                .order_by(rag_index_jobs.c.created_at.desc(), rag_index_jobs.c.id.desc())
                .limit(limit)
            ).mappings().all()
            return [self._row_dict(row) for row in rows]

    def mark_interrupted(self) -> int:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            result = connection.execute(
                update(rag_index_jobs)
                .where(rag_index_jobs.c.status.in_(["queued", "running"]))
                .values(
                    status="error",
                    stage="interrupted",
                    message="Indexing was interrupted by application restart.",
                    error="Application restarted before the background indexing job completed.",
                    finished_at=now,
                )
            )
            return int(result.rowcount or 0)

    def _update(self, job_id: int, **values: Any) -> dict[str, Any]:
        with self.engine.begin() as connection:
            connection.execute(
                update(rag_index_jobs)
                .where(rag_index_jobs.c.id == job_id)
                .values(**values)
            )
            row = connection.execute(
                select(rag_index_jobs).where(rag_index_jobs.c.id == job_id)
            ).mappings().one()
            return self._row_dict(row)

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "target_kind": str(row["target_kind"]),
            "target_identifier": str(row["target_identifier"]),
            "label": row["label"],
            "status": str(row["status"]),
            "stage": row["stage"],
            "message": row["message"],
            "progress_current": row["progress_current"],
            "progress_total": row["progress_total"],
            "result": dict(row["result"] or {}),
            "error": row["error"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }
