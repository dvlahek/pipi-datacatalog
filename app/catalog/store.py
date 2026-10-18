from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.catalog.database import initialize_postgres_database
from app.models.catalog import CanonicalDataset, CatalogDistribution


class Base(DeclarativeBase):
    pass


class DatasetRow(Base):
    __tablename__ = "catalog_datasets"

    identifier: Mapped[str] = mapped_column(String, primary_key=True)
    catalog_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    source_system: Mapped[str] = mapped_column(String, index=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    dataset_type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    harvested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    distributions: Mapped[list["DistributionRow"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DistributionRow(Base):
    __tablename__ = "catalog_distributions"

    identifier: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_identifier: Mapped[str] = mapped_column(
        ForeignKey("catalog_datasets.identifier", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String)
    access_url: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String, index=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_live: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

    dataset: Mapped[DatasetRow] = relationship(back_populates="distributions")


class DatasetVersionRow(Base):
    __tablename__ = "catalog_dataset_versions"

    dataset_identifier: Mapped[str] = mapped_column(
        ForeignKey("catalog_datasets.identifier", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ResourceRow(Base):
    __tablename__ = "catalog_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str] = mapped_column(String, unique=True)
    requested_type: Mapped[str] = mapped_column(String, default="auto")
    detected_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    refresh_policy: Mapped[str] = mapped_column(String, default="manual")
    dataset_identifier: Mapped[str | None] = mapped_column(
        ForeignKey("catalog_datasets.identifier", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_media_type: Mapped[str | None] = mapped_column(String, nullable=True)
    last_etag: Mapped[str | None] = mapped_column(String, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String, nullable=True)
    last_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CatalogStore:
    """Persistent provider-neutral catalog metadata store with version history.

    PostgreSQL schema changes are applied from versioned SQL migrations. SQLite is
    retained only for isolated unit tests and uses SQLAlchemy create_all().
    """

    def __init__(self, database_url: str, *, admin_url: str | None = None) -> None:
        self.database_url = database_url
        self.admin_url = admin_url
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)

    def initialize(self) -> dict[str, object]:
        if self.engine.dialect.name == "postgresql":
            return initialize_postgres_database(
                self.database_url,
                admin_url=self.admin_url,
            )

        Base.metadata.create_all(self.engine)
        return {
            "current_version": 0,
            "applied_now": [],
            "migration_count": 0,
            "mode": "sqlalchemy-test-schema",
        }

    @staticmethod
    def _snapshot(dataset: CanonicalDataset) -> dict[str, Any]:
        return dataset.model_dump(mode="json")

    @staticmethod
    def _fingerprint(snapshot: dict[str, Any]) -> str:
        canonical = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def upsert_datasets(self, datasets: list[CanonicalDataset]) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0
        unchanged = 0
        versions_created = 0

        with Session(self.engine) as session:
            for dataset in datasets:
                snapshot = self._snapshot(dataset)
                fingerprint = self._fingerprint(snapshot)
                row = session.get(DatasetRow, dataset.identifier)

                latest_version = session.scalars(
                    select(DatasetVersionRow)
                    .where(DatasetVersionRow.dataset_identifier == dataset.identifier)
                    .order_by(DatasetVersionRow.version.desc())
                    .limit(1)
                ).first()

                changed = latest_version is None or latest_version.fingerprint != fingerprint

                payload = dataset.model_dump(mode="json", exclude={"distributions"})
                if row is None:
                    row = DatasetRow(
                        identifier=dataset.identifier,
                        catalog_id=dataset.catalog_id,
                        source_system=dataset.source_system,
                        external_id=dataset.external_id,
                        title=dataset.title,
                        dataset_type=dataset.dataset_type,
                        payload=payload,
                        harvested_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                    inserted += 1
                else:
                    row.catalog_id = dataset.catalog_id
                    row.source_system = dataset.source_system
                    row.external_id = dataset.external_id
                    row.title = dataset.title
                    row.dataset_type = dataset.dataset_type
                    row.payload = payload
                    row.harvested_at = now
                    if changed:
                        row.updated_at = now
                        updated += 1
                    else:
                        unchanged += 1
                    row.distributions.clear()

                row.distributions = [
                    DistributionRow(
                        identifier=distribution.identifier,
                        title=distribution.title,
                        access_url=distribution.access_url,
                        media_type=distribution.media_type,
                        format=distribution.format,
                        kind=distribution.kind,
                        is_live=distribution.is_live,
                        payload=distribution.model_dump(mode="json"),
                    )
                    for distribution in dataset.distributions
                ]

                if changed:
                    next_version = 1 if latest_version is None else latest_version.version + 1
                    session.add(
                        DatasetVersionRow(
                            dataset_identifier=dataset.identifier,
                            version=next_version,
                            fingerprint=fingerprint,
                            snapshot=snapshot,
                            created_at=now,
                        )
                    )
                    versions_created += 1

            session.commit()

        return {
            "discovered": len(datasets),
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "versions_created": versions_created,
        }

    def list_datasets(self) -> list[CanonicalDataset]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(DatasetRow).order_by(DatasetRow.catalog_id)
            ).all()
            return [self._to_dataset(row) for row in rows]

    def count_datasets(self) -> int:
        with Session(self.engine) as session:
            return len(session.scalars(select(DatasetRow.identifier)).all())

    def list_versions(self, dataset_identifier: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            versions = session.scalars(
                select(DatasetVersionRow)
                .where(DatasetVersionRow.dataset_identifier == dataset_identifier)
                .order_by(DatasetVersionRow.version.desc())
            ).all()
            return [
                {
                    "version": item.version,
                    "fingerprint": item.fingerprint,
                    "created_at": item.created_at.isoformat(),
                }
                for item in versions
            ]

    def get_version(
        self,
        dataset_identifier: str,
        version: int,
    ) -> CanonicalDataset | None:
        with Session(self.engine) as session:
            row = session.get(
                DatasetVersionRow,
                {"dataset_identifier": dataset_identifier, "version": version},
            )
            if row is None:
                return None
            return CanonicalDataset.model_validate(row.snapshot)

    def create_resource(
        self,
        *,
        source_url: str,
        name: str | None,
        requested_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            existing = session.scalars(
                select(ResourceRow).where(ResourceRow.source_url == source_url)
            ).first()
            if existing is not None:
                raise ValueError("Resource URL is already registered.")
            row = ResourceRow(
                name=name,
                source_url=source_url,
                requested_type=requested_type,
                enabled=True,
                refresh_policy="manual",
                metadata_json=metadata or {},
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._resource_dict(row)

    def list_resources(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = session.scalars(select(ResourceRow).order_by(ResourceRow.id)).all()
            return [self._resource_dict(row) for row in rows]

    def get_resource(self, resource_id: int) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            row = session.get(ResourceRow, resource_id)
            return None if row is None else self._resource_dict(row)

    def mark_resource_success(
        self,
        resource_id: int,
        *,
        detected_type: str,
        dataset_identifier: str,
        media_type: str,
        etag: str | None,
        last_modified: str | None,
        content_sha256: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            row = session.get(ResourceRow, resource_id)
            if row is None:
                raise KeyError(resource_id)
            row.detected_type = detected_type
            row.dataset_identifier = dataset_identifier
            row.last_media_type = media_type
            row.last_etag = etag
            row.last_modified = last_modified
            row.last_content_sha256 = content_sha256
            row.last_checked_at = now
            row.last_success_at = now
            row.last_error = None
            row.updated_at = now
            session.commit()
            session.refresh(row)
            return self._resource_dict(row)

    def mark_resource_error(self, resource_id: int, error: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            row = session.get(ResourceRow, resource_id)
            if row is None:
                raise KeyError(resource_id)
            row.last_checked_at = now
            row.last_error = error[:4000]
            row.updated_at = now
            session.commit()
            session.refresh(row)
            return self._resource_dict(row)

    def set_resource_enabled(self, resource_id: int, enabled: bool) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session:
            row = session.get(ResourceRow, resource_id)
            if row is None:
                raise KeyError(resource_id)
            row.enabled = enabled
            row.updated_at = now
            session.commit()
            session.refresh(row)
            return self._resource_dict(row)

    @staticmethod
    def _resource_dict(row: ResourceRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "source_url": row.source_url,
            "requested_type": row.requested_type,
            "detected_type": row.detected_type,
            "enabled": row.enabled,
            "refresh_policy": row.refresh_policy,
            "dataset_identifier": row.dataset_identifier,
            "last_media_type": row.last_media_type,
            "last_etag": row.last_etag,
            "last_modified": row.last_modified,
            "last_content_sha256": row.last_content_sha256,
            "metadata": dict(row.metadata_json or {}),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "last_checked_at": row.last_checked_at,
            "last_success_at": row.last_success_at,
            "last_error": row.last_error,
        }

    @staticmethod
    def _to_dataset(row: DatasetRow) -> CanonicalDataset:
        payload = dict(row.payload)
        payload["distributions"] = [
            CatalogDistribution.model_validate(distribution.payload).model_dump()
            for distribution in row.distributions
        ]
        return CanonicalDataset.model_validate(payload)
