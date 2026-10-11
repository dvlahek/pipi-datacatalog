from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CatalogSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
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

    id: int
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
    id: int
    name: str
    description: str | None = None
    quantity_kind: str | None = None
    semantic_uri: str | None = None
    data_type: str | None = None
    unit_code: str | None = None
    unit_uri: str | None = None


class CatalogAccess(BaseModel):
    provider: str
    data_service_identifier: str
    endpoint_url: str
    endpoint_description: str
    readings_url: str
    deployment_property_id: int
    dataset_scoped_filtering_available: bool = False


class CanonicalDataset(BaseModel):
    catalog_id: str
    identifier: str
    title: str
    description: str
    publisher: str
    license: str
    source: CatalogSource
    location: CatalogLocation
    temporal: CatalogTemporalCoverage
    observed_property: CatalogObservedProperty
    sampling_interval_seconds: int | None = None
    resolution: float | None = None
    uncertainty: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    is_active: bool | None = None
    observation_target: str | None = None
    access: CatalogAccess
