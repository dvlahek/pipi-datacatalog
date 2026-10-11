from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, create_engine, select
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


class CatalogStore:
    """Persistent provider-neutral catalog metadata store.

    The store persists catalog metadata and distribution descriptors only. Source
    content such as Sensor Hub readings, HLS video segments, CSV files or audio
    remains in the source system unless a future provider explicitly ingests it.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def upsert_datasets(self, datasets: list[CanonicalDataset]) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        inserted = 0
        updated = 0

        with Session(self.engine) as session:
            for dataset in datasets:
                row = session.get(DatasetRow, dataset.identifier)
                payload = dataset.model_dump(exclude={"distributions"})

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
                    row.updated_at = now
                    row.distributions.clear()
                    updated += 1

                row.distributions = [
                    DistributionRow(
                        identifier=distribution.identifier,
                        dataset_identifier=dataset.identifier,
                        title=distribution.title,
                        access_url=distribution.access_url,
                        media_type=distribution.media_type,
                        format=distribution.format,
                        kind=distribution.kind,
                        is_live=distribution.is_live,
                        payload=distribution.model_dump(),
                    )
                    for distribution in dataset.distributions
                ]

            session.commit()

        return {
            "discovered": len(datasets),
            "inserted": inserted,
            "updated": updated,
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

    @staticmethod
    def _to_dataset(row: DatasetRow) -> CanonicalDataset:
        payload = dict(row.payload)
        payload["distributions"] = [
            CatalogDistribution.model_validate(distribution.payload).model_dump()
            for distribution in row.distributions
        ]
        return CanonicalDataset.model_validate(payload)
