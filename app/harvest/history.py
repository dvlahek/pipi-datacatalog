from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, Text, insert, select, update

from app.catalog.store import CatalogStore


metadata = MetaData()

harvest_runs = Table(
    "harvest_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_kind", String, nullable=False, index=True),
    Column("trigger", String, nullable=False),
    Column("status", String, nullable=False, default="running", index=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("summary", JSON, nullable=False, default=dict),
    Column("error", Text, nullable=True),
)


def _json_safe(value: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize API/service summaries so JSON columns never receive datetimes."""

    return json.loads(json.dumps(value or {}, ensure_ascii=False, default=str))


class HarvestHistoryStore:
    """Small persistent audit log for provider/resource refresh activity."""

    def __init__(self, catalog_store: CatalogStore) -> None:
        self.catalog_store = catalog_store
        self.engine = catalog_store.engine
        if self.engine.dialect.name != "postgresql":
            metadata.create_all(self.engine, tables=[harvest_runs], checkfirst=True)

    def start(self, run_kind: str, *, trigger: str) -> int:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            result = connection.execute(
                insert(harvest_runs)
                .values(
                    run_kind=run_kind,
                    trigger=trigger,
                    status="running",
                    started_at=now,
                    summary={},
                )
                .returning(harvest_runs.c.id)
            )
            return int(result.scalar_one())

    def finish(
        self,
        run_id: int,
        *,
        status: str,
        summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(
                update(harvest_runs)
                .where(harvest_runs.c.id == run_id)
                .values(
                    status=status,
                    finished_at=now,
                    summary=_json_safe(summary),
                    error=error[:4000] if error else None,
                )
            )
            row = connection.execute(
                select(harvest_runs).where(harvest_runs.c.id == run_id)
            ).mappings().one()
            return self._row_dict(row)

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(harvest_runs)
                .order_by(harvest_runs.c.started_at.desc(), harvest_runs.c.id.desc())
                .limit(limit)
            ).mappings().all()
            return [self._row_dict(row) for row in rows]

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "run_kind": str(row["run_kind"]),
            "trigger": str(row["trigger"]),
            "status": str(row["status"]),
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "summary": dict(row["summary"] or {}),
            "error": row["error"],
        }
