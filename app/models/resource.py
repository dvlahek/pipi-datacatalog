from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

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

ResourceAccessLevel = Literal[
    "public",
    "authenticated",
    "approval-required",
    "private",
]

ResourceCommercialModel = Literal[
    "free",
    "paid",
    "negotiable",
    "not-for-sale",
]


class ResourceCreate(BaseModel):
    source_url: HttpUrl
    name: str | None = Field(default=None, max_length=300)
    resource_type: ResourceType = "auto"
    publisher: str | None = Field(default=None, max_length=300)
    license: str | None = Field(default=None, max_length=300)
    keywords: list[str] = Field(default_factory=list, max_length=50)

    # These fields describe sharing terms inside the PiPi dataspace. They do not
    # by themselves make an already-public source URL private; enforcement belongs
    # to the later identity/authorization/contract layer.
    access_level: ResourceAccessLevel = "public"
    commercial_model: ResourceCommercialModel = "free"
    price_amount: float | None = Field(default=None, ge=0)
    price_currency: str | None = Field(default=None, min_length=3, max_length=3)
    access_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_commercial_terms(self) -> "ResourceCreate":
        if self.commercial_model == "paid":
            if self.price_amount is None:
                raise ValueError("price_amount is required when commercial_model is 'paid'.")
            if not self.price_currency:
                raise ValueError("price_currency is required when commercial_model is 'paid'.")
            self.price_currency = self.price_currency.upper()
        elif self.price_amount is not None:
            raise ValueError("price_amount is only valid when commercial_model is 'paid'.")
        return self


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
