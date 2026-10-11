from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

ResourceType = Literal[
    "auto",
    "csv",
    "json",
    "document",
    "text",
    "image",
    "audio",
    "video",
    "generic",
]


class ResourceCreate(BaseModel):
    source_url: HttpUrl
    name: str | None = Field(default=None, max_length=300)
    resource_type: ResourceType = "auto"
    publisher: str | None = Field(default=None, max_length=300)
    license: str | None = Field(default=None, max_length=300)
    keywords: list[str] = Field(default_factory=list, max_length=50)


class ResourceRecord(BaseModel):
    id: int
    name: str | None
    source_url: str
    requested_type: str
    detected_type: str | None
    enabled: bool
    refresh_policy: str
    dataset_identifier: str | None
    last_media_type: str | None
    last_etag: str | None
    last_modified: str | None
    last_content_sha256: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
