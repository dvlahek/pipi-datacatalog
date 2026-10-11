from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import urlparse

from app.catalog.store import CatalogStore
from app.config import Settings
from app.models.catalog import (
    CanonicalDataset,
    CatalogDistribution,
    CatalogProvenance,
    CatalogSource,
)
from app.models.resource import ResourceCreate
from app.resources.fetcher import ResourceFetchError, ResourceProbe, fetch_resource_probe
from app.security.url_policy import UnsafeResourceURL, validate_external_resource_url


def _dataset_type(detected_type: str) -> str:
    return {
        "csv": "tabular-data",
        "json": "structured-data",
        "document": "document",
        "text": "text-document",
        "image": "image",
        "audio": "audio",
        "video": "video",
    }.get(detected_type, "generic")


def _format_name(detected_type: str, media_type: str, url: str) -> str | None:
    if detected_type == "csv":
        return "CSV"
    if detected_type == "json":
        return "JSON"
    if detected_type == "document" and media_type == "application/pdf":
        return "PDF"
    if media_type in {"application/vnd.apple.mpegurl", "application/x-mpegurl"}:
        return "HLS"
    suffix = PurePosixPath(urlparse(url).path).suffix.lstrip(".")
    return suffix.upper() if suffix else None


def _is_live_hls(probe: ResourceProbe) -> bool:
    return probe.media_type in {
        "application/vnd.apple.mpegurl",
        "application/x-mpegurl",
    } or urlparse(probe.final_url).path.lower().endswith(".m3u8")


def dataset_from_registered_resource(
    resource: dict[str, object],
    probe: ResourceProbe,
) -> CanonicalDataset:
    resource_id = int(resource["id"])
    metadata = dict(resource.get("metadata") or {})
    title = str(resource.get("name") or probe.title_hint or f"External resource {resource_id}")
    publisher = str(metadata.get("publisher") or "unknown")
    license_value = str(metadata.get("license") or "unknown")
    keywords = [str(item) for item in metadata.get("keywords", [])]
    if probe.detected_type not in keywords:
        keywords.append(probe.detected_type)

    identifier = f"urn:pipi:dataset:resource:{resource_id}"
    live_hls = _is_live_hls(probe)

    provenance = CatalogProvenance(
        source_url=str(resource["source_url"]),
        etag=None if live_hls else probe.etag,
        last_modified=None if live_hls else probe.last_modified,
        content_sha256=None if live_hls else probe.content_sha256,
    )

    return CanonicalDataset(
        catalog_id=f"resource:{resource_id}",
        identifier=identifier,
        title=title,
        description=(
            "External resource registered through the PiPi dataspace resource registry. "
            "The catalog stores normalized metadata and source provenance while the "
            "resource content remains at its source."
        ),
        publisher=publisher,
        license=license_value,
        dataset_type=_dataset_type(probe.detected_type),
        source_system="resource-registry",
        external_id=str(resource_id),
        keywords=keywords,
        provenance=provenance,
        source=CatalogSource(
            id=str(resource_id),
            code=f"resource-{resource_id}",
            name=title,
            provider=publisher,
            license=license_value,
        ),
        distributions=[
            CatalogDistribution(
                identifier=f"{identifier}:distribution:source",
                title="Source resource",
                access_url=probe.final_url,
                media_type=probe.media_type,
                format=_format_name(probe.detected_type, probe.media_type, probe.final_url),
                download_url=None if live_hls else probe.final_url,
                endpoint_url=probe.final_url if live_hls else None,
                kind="live-stream" if live_hls else "external-resource",
                is_live=live_hls,
            )
        ],
        extensions={
            "resource_registry": {
                "resource_id": resource_id,
                "registered_source_url": str(resource["source_url"]),
                "final_url": probe.final_url,
                "requested_type": resource["requested_type"],
                "detected_type": probe.detected_type,
                "byte_size": probe.byte_size,
            }
        },
    )


async def refresh_registered_resource(
    store: CatalogStore,
    resource_id: int,
    settings: Settings,
) -> dict[str, object]:
    resource = store.get_resource(resource_id)
    if resource is None:
        raise KeyError(resource_id)
    if not resource["enabled"]:
        return {"status": "disabled", "resource": resource, "sync": None}

    try:
        probe = await fetch_resource_probe(str(resource["source_url"]), settings)
        dataset = dataset_from_registered_resource(resource, probe)
        sync_stats = store.upsert_datasets([dataset])
        updated_resource = store.mark_resource_success(
            resource_id,
            detected_type=probe.detected_type,
            dataset_identifier=dataset.identifier,
            media_type=probe.media_type,
            etag=None if _is_live_hls(probe) else probe.etag,
            last_modified=None if _is_live_hls(probe) else probe.last_modified,
            content_sha256=None if _is_live_hls(probe) else probe.content_sha256,
        )
        return {
            "status": "ok",
            "resource": updated_resource,
            "dataset": dataset.model_dump(),
            "sync": sync_stats,
        }
    except (ResourceFetchError, UnsafeResourceURL, ValueError) as exc:
        failed = store.mark_resource_error(resource_id, str(exc))
        return {"status": "error", "resource": failed, "error": str(exc), "sync": None}


async def register_resource(
    store: CatalogStore,
    payload: ResourceCreate,
    settings: Settings,
) -> dict[str, object]:
    source_url = str(payload.source_url)
    validate_external_resource_url(
        source_url,
        allowed_ports=settings.allowed_resource_ports,
    )
    resource = store.create_resource(
        source_url=source_url,
        name=payload.name,
        requested_type=payload.resource_type,
        metadata={
            "publisher": payload.publisher,
            "license": payload.license,
            "keywords": payload.keywords,
        },
    )
    return await refresh_registered_resource(store, int(resource["id"]), settings)
