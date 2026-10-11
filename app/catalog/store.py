from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

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


class CatalogStore:
    """Persistent provider-neutral catalog metadata store with version history.

    The current dataset row is mutable and optimized for reads. Every meaningful
    change creates an immutable version snapshot. Source payloads such as Sensor
    Hub readings, HLS segments, CSV files or audio remain in their source systems
    unless a provider explicitly ingests them.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

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

    @staticmethod
    def _to_dataset(row: DatasetRow) -> CanonicalDataset:
        payload = dict(row.payload)
        payload["distributions"] = [
            CatalogDistribution.model_validate(distribution.payload).model_dump()
            for distribution in row.distributions
        ]
        return CanonicalDataset.model_validate(payload)
