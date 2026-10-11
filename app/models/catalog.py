from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CatalogSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str
    code: str
    name: str
    description: str | None = None
    owner: str | None = None
    provider: str | None = None
    license: str | None = None
    manufacturer: str | None = None
    model: str | None = None


class CatalogLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    address: str | None = None
    geometry_wkt: str | None = None
    environment: str | None = None


class CatalogTemporalCoverage(BaseModel):
    start: str | None = None
    end: str | None = None


class CatalogObservedProperty(BaseModel):
    id: int | str
    name: str
    description: str | None = None
    quantity_kind: str | None = None
    semantic_uri: str | None = None
    data_type: str | None = None
    unit_code: str | None = None
    unit_uri: str | None = None


class CatalogAccess(BaseModel):
    """Legacy Sensor Hub access metadata kept for compatibility."""

    provider: str
    data_service_identifier: str
    endpoint_url: str
    endpoint_description: str
    readings_url: str
    deployment_property_id: int
    dataset_scoped_filtering_available: bool = False


class CatalogDistribution(BaseModel):
    """Provider-neutral representation of one way to access a dataset."""

    identifier: str
    title: str
    access_url: str
    media_type: str
    format: str | None = None
    source_media_type: str | None = None
    download_url: str | None = None
    access_service_identifier: str | None = None
    endpoint_url: str | None = None
    endpoint_description: str | None = None
    kind: str | None = None
    is_live: bool | None = None


class CanonicalDataset(BaseModel):
    """Provider-neutral catalog dataset with optional domain extensions.

    Sensor Hub fields remain available so the first provider stays backward
    compatible, while future API, file, text, image, audio and video providers
    can use the common fields and distributions without inventing sensor data.
    """

    catalog_id: str
    identifier: str
    title: str
    description: str
    publisher: str
    license: str

    dataset_type: str = "generic"
    source_system: str = "unknown"
    external_id: str | None = None
    keywords: list[str] = Field(default_factory=list)

    source: CatalogSource | None = None
    location: CatalogLocation | None = None
    temporal: CatalogTemporalCoverage | None = None
    distributions: list[CatalogDistribution] = Field(default_factory=list)

    # Sensor/observation extension. These fields are intentionally optional.
    observed_property: CatalogObservedProperty | None = None
    sampling_interval_seconds: int | None = None
    resolution: float | None = None
    uncertainty: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    is_active: bool | None = None
    observation_target: str | None = None
    access: CatalogAccess | None = None

    # Provider-specific metadata can be preserved without changing the core.
    extensions: dict[str, Any] = Field(default_factory=dict)
