from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

import httpx

from app.config import Settings
from app.security.url_policy import validate_external_resource_url


class ResourceFetchError(RuntimeError):
    pass


@dataclass(slots=True)
class ResourceProbe:
    final_url: str
    media_type: str
    detected_type: str
    content_sha256: str | None
    byte_size: int
    etag: str | None
    last_modified: str | None
    title_hint: str | None


def detect_resource_type(url: str, media_type: str, content: bytes) -> str:
    media = media_type.lower()
    suffix = PurePosixPath(urlparse(url).path).suffix.lower()

    if media == "text/csv" or suffix == ".csv":
        return "csv"
    if media == "application/json" or media.endswith("+json") or suffix == ".json":
        return "json"
    if media == "application/pdf" or suffix == ".pdf" or content.startswith(b"%PDF"):
        return "document"
    if media in {"application/vnd.apple.mpegurl", "application/x-mpegurl"} or suffix == ".m3u8":
        return "video"
    if media.startswith("image/"):
        return "image"
    if media.startswith("audio/"):
        return "audio"
    if media.startswith("video/"):
        return "video"
    if media.startswith("text/"):
        return "text"
    return "generic"


def _title_hint(url: str) -> str | None:
    path = PurePosixPath(urlparse(url).path)
    if path.name:
        return path.name
    return urlparse(url).hostname


async def fetch_resource_probe(url: str, settings: Settings) -> ResourceProbe:
    current_url = validate_external_resource_url(
        url,
        allowed_ports=settings.allowed_resource_ports,
    )

    timeout = httpx.Timeout(settings.resource_fetch_timeout_seconds)
    headers = {
        "User-Agent": "PiPi-Data-Catalog/0.1 resource-probe",
        "Accept": "*/*",
    }

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(5):
            try:
                async with client.stream("GET", current_url, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise ResourceFetchError("Redirect response has no Location header.")
                        redirected = urljoin(current_url, location)
                        current_url = validate_external_resource_url(
                            redirected,
                            allowed_ports=settings.allowed_resource_ports,
                        )
                        continue

                    response.raise_for_status()
                    media_type = response.headers.get("content-type", "application/octet-stream")
                    media_type = media_type.split(";", 1)[0].strip().lower()

                    declared_length = response.headers.get("content-length")
                    if declared_length:
                        try:
                            if int(declared_length) > settings.resource_fetch_max_bytes:
                                raise ResourceFetchError(
                                    "Resource exceeds configured maximum download size."
                                )
                        except ValueError:
                            pass

                    digest = hashlib.sha256()
                    content = bytearray()
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > settings.resource_fetch_max_bytes:
                            raise ResourceFetchError(
                                "Resource exceeds configured maximum download size."
                            )
                        digest.update(chunk)
                        content.extend(chunk)

                    payload = bytes(content)
                    detected_type = detect_resource_type(current_url, media_type, payload)
                    return ResourceProbe(
                        final_url=current_url,
                        media_type=media_type,
                        detected_type=detected_type,
                        content_sha256=digest.hexdigest(),
                        byte_size=total,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        title_hint=_title_hint(current_url),
                    )
            except httpx.HTTPStatusError as exc:
                raise ResourceFetchError(
                    f"Resource returned HTTP {exc.response.status_code}."
                ) from exc
            except httpx.HTTPError as exc:
                raise ResourceFetchError(f"Resource request failed: {exc}") from exc

    raise ResourceFetchError("Too many redirects while fetching resource.")
