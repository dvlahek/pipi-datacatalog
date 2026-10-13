from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import httpx
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, FOAF, RDF, SKOS

from app.models.catalog import (
    CatalogDistribution,
    CatalogProvenance,
    CatalogSource,
    CatalogTemporalCoverage,
    CanonicalDataset,
)
from app.security.url_policy import validate_external_resource_url


DCAT = URIRef("http://www.w3.org/ns/dcat#Dataset")
DCAT_NS = "http://www.w3.org/ns/dcat#"


class OpenDataCatalogError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenDataCatalogSource:
    id: str
    type: str
    url: str
    publisher: str
    enabled: bool = True
    max_datasets: int = 200
    page_size: int = 100
    timeout_seconds: float | None = None


_SAFE_COMPONENT_RE = re.compile(r"[^a-z0-9._-]+")


def _stable_component(value: str) -> str:
    normalized = _SAFE_COMPONENT_RE.sub("-", value.casefold()).strip("-._")
    digest = hashlib.blake2s(value.encode("utf-8"), digest_size=5).hexdigest()
    if not normalized:
        return digest
    return f"{normalized[:56]}-{digest}"


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _http_url(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def _format_media_type(value: str) -> str:
    normalized = value.strip().lower()
    if "/" in normalized:
        return normalized
    known = {
        "csv": "text/csv",
        "json": "application/json",
        "jsonld": "application/ld+json",
        "geojson": "application/geo+json",
        "xml": "application/xml",
        "rdf": "application/rdf+xml",
        "ttl": "text/turtle",
        "turtle": "text/turtle",
        "pdf": "application/pdf",
        "zip": "application/zip",
    }
    return known.get(normalized, "application/octet-stream")


def _license_value(item: dict[str, Any]) -> str:
    for key in ("license_title", "license_id", "license_url"):
        value = _clean_text(item.get(key))
        if value:
            return value
    return "unknown"


def _ckan_distribution(
    dataset_identifier: str,
    resource: dict[str, Any],
    index: int,
) -> CatalogDistribution | None:
    access_url = _http_url(resource.get("url"))
    if access_url is None:
        return None

    resource_id = _clean_text(resource.get("id"), str(index))
    format_value = _clean_text(resource.get("format"))
    media_type = _clean_text(resource.get("mimetype"))
    if not media_type:
        media_type = _format_media_type(format_value)

    title = _clean_text(resource.get("name")) or format_value or f"Resource {index + 1}"
    return CatalogDistribution(
        identifier=f"{dataset_identifier}:distribution:{_stable_component(resource_id)}",
        title=title,
        access_url=access_url,
        download_url=access_url if _clean_text(resource.get("url_type")) != "api" else None,
        media_type=media_type,
        source_media_type=_clean_text(resource.get("mimetype")) or None,
        format=format_value or None,
        kind="api" if _clean_text(resource.get("url_type")).casefold() == "api" else "download",
        is_live=False,
    )


def ckan_package_to_dataset(
    source: OpenDataCatalogSource,
    package: dict[str, Any],
    *,
    max_resources: int = 30,
) -> CanonicalDataset:
    external_id = _clean_text(package.get("id")) or _clean_text(package.get("name"))
    if not external_id:
        raise OpenDataCatalogError(f"CKAN package from {source.id!r} has no id or name.")

    native_name = _clean_text(package.get("name"), external_id)
    component = _stable_component(external_id)
    identifier = f"urn:pipi:dataset:open-data:{_stable_component(source.id)}:{component}"
    landing_url = urljoin(source.url.rstrip("/") + "/", f"dataset/{native_name}")

    organization = package.get("organization") if isinstance(package.get("organization"), dict) else {}
    publisher = (
        _clean_text(organization.get("title"))
        or _clean_text(organization.get("name"))
        or source.publisher
    )

    tags = package.get("tags") if isinstance(package.get("tags"), list) else []
    groups = package.get("groups") if isinstance(package.get("groups"), list) else []
    keywords = _unique_strings(
        [
            *(tag.get("display_name") or tag.get("name") for tag in tags if isinstance(tag, dict)),
            *(group.get("display_name") or group.get("title") or group.get("name") for group in groups if isinstance(group, dict)),
        ]
    )

    resources = package.get("resources") if isinstance(package.get("resources"), list) else []
    distributions: list[CatalogDistribution] = []
    for index, resource in enumerate(resources[: max(0, int(max_resources))]):
        if not isinstance(resource, dict):
            continue
        distribution = _ckan_distribution(identifier, resource, index)
        if distribution is not None:
            distributions.append(distribution)

    modified = _clean_text(package.get("metadata_modified")) or _clean_text(package.get("metadata_created"))
    source_version = _clean_text(package.get("revision_id")) or modified or None

    extras = package.get("extras") if isinstance(package.get("extras"), list) else []
    extras_map = {
        _clean_text(item.get("key")): _clean_text(item.get("value"))
        for item in extras
        if isinstance(item, dict) and _clean_text(item.get("key"))
    }
    temporal = None
    start = extras_map.get("temporal_start") or extras_map.get("temporal-start")
    end = extras_map.get("temporal_end") or extras_map.get("temporal-end")
    if start or end:
        temporal = CatalogTemporalCoverage(start=start or None, end=end or None)

    title = _clean_text(package.get("title"), native_name)
    description = _clean_text(package.get("notes"), f"Open-data dataset harvested from {source.publisher}.")

    return CanonicalDataset(
        catalog_id=f"open-data:{source.id}:{external_id}",
        identifier=identifier,
        title=title,
        description=description,
        publisher=publisher,
        license=_license_value(package),
        dataset_type="open-data-catalog",
        source_system=f"open-data:{source.id}",
        external_id=external_id,
        keywords=keywords,
        provenance=CatalogProvenance(
            source_url=landing_url,
            last_modified=modified or None,
            source_version=source_version,
        ),
        source=CatalogSource(
            id=source.id,
            code=source.id,
            name=source.publisher,
            provider="CKAN",
        ),
        temporal=temporal,
        distributions=distributions,
        extensions={
            "open_data_catalog": {
                "catalog_id": source.id,
                "catalog_type": "ckan",
                "catalog_url": source.url,
                "native_name": native_name,
                "organization": publisher,
                "metadata_created": _clean_text(package.get("metadata_created")) or None,
                "metadata_modified": modified or None,
                "resource_count": len(resources),
                "groups": _unique_strings(
                    group.get("display_name") or group.get("title") or group.get("name")
                    for group in groups
                    if isinstance(group, dict)
                ),
                "extras": extras_map,
            }
        },
    )


def _first_text(graph: Graph, subject: Any, predicates: Iterable[Any]) -> str | None:
    fallback: str | None = None
    for predicate in predicates:
        for value in graph.objects(subject, predicate):
            text = _clean_text(value)
            if not text:
                continue
            if isinstance(value, Literal) and value.language in {"en", "hr"}:
                return text
            if fallback is None:
                fallback = text
    return fallback


def _publisher_text(graph: Graph, dataset: Any, default: str) -> str:
    publisher = next(iter(graph.objects(dataset, DCTERMS.publisher)), None)
    if publisher is None:
        return default
    if isinstance(publisher, Literal):
        return _clean_text(publisher, default)
    return (
        _first_text(graph, publisher, (FOAF.name, DCTERMS.title, SKOS.prefLabel))
        or _clean_text(publisher, default)
    )


def _rdf_format(content_type: str, url: str) -> str | None:
    media = content_type.split(";", 1)[0].strip().lower()
    by_media = {
        "application/ld+json": "json-ld",
        "application/rdf+xml": "xml",
        "application/xml": "xml",
        "text/xml": "xml",
        "text/turtle": "turtle",
        "application/x-turtle": "turtle",
        "application/n-triples": "nt",
        "application/trig": "trig",
    }
    if media in by_media:
        return by_media[media]
    suffix = Path(urlparse(url).path).suffix.casefold()
    return {
        ".ttl": "turtle",
        ".rdf": "xml",
        ".xml": "xml",
        ".jsonld": "json-ld",
        ".json": "json-ld",
        ".nt": "nt",
        ".trig": "trig",
    }.get(suffix)


def dcat_graph_to_datasets(
    source: OpenDataCatalogSource,
    graph: Graph,
    *,
    max_datasets: int | None = None,
    max_resources: int = 30,
) -> list[CanonicalDataset]:
    dcat_distribution = URIRef(f"{DCAT_NS}distribution")
    dcat_access_url = URIRef(f"{DCAT_NS}accessURL")
    dcat_download_url = URIRef(f"{DCAT_NS}downloadURL")
    dcat_media_type = URIRef(f"{DCAT_NS}mediaType")
    dcat_keyword = URIRef(f"{DCAT_NS}keyword")
    dcat_theme = URIRef(f"{DCAT_NS}theme")
    dcat_landing_page = URIRef(f"{DCAT_NS}landingPage")
    dcat_start_date = URIRef(f"{DCAT_NS}startDate")
    dcat_end_date = URIRef(f"{DCAT_NS}endDate")

    subjects = sorted(set(graph.subjects(RDF.type, DCAT)), key=str)
    if max_datasets is not None:
        subjects = subjects[: max(0, int(max_datasets))]

    datasets: list[CanonicalDataset] = []
    for dataset in subjects:
        external_id = _clean_text(dataset)
        if not external_id:
            continue
        component = _stable_component(external_id)
        identifier = f"urn:pipi:dataset:open-data:{_stable_component(source.id)}:{component}"

        title = _first_text(graph, dataset, (DCTERMS.title,)) or external_id
        description = _first_text(graph, dataset, (DCTERMS.description,)) or (
            f"Open-data dataset harvested from {source.publisher}."
        )
        publisher = _publisher_text(graph, dataset, source.publisher)
        license_value = _first_text(graph, dataset, (DCTERMS.license,)) or "unknown"
        modified = _first_text(graph, dataset, (DCTERMS.modified, DCTERMS.issued))
        landing_url = _first_text(graph, dataset, (dcat_landing_page,)) or _http_url(external_id) or source.url

        keywords = _unique_strings(
            [
                *(graph.objects(dataset, dcat_keyword)),
                *(
                    _first_text(graph, theme, (SKOS.prefLabel, DCTERMS.title)) or theme
                    for theme in graph.objects(dataset, dcat_theme)
                ),
            ]
        )

        distributions: list[CatalogDistribution] = []
        distribution_nodes = list(graph.objects(dataset, dcat_distribution))[: max(0, int(max_resources))]
        for index, distribution in enumerate(distribution_nodes):
            access = _first_text(graph, distribution, (dcat_access_url, dcat_download_url))
            access_url = _http_url(access)
            if access_url is None:
                continue
            download = _first_text(graph, distribution, (dcat_download_url,))
            download_url = _http_url(download)
            format_value = _first_text(graph, distribution, (DCTERMS.format,)) or ""
            media_type = _first_text(graph, distribution, (dcat_media_type,)) or _format_media_type(format_value)
            distribution_id = _clean_text(distribution, str(index))
            distributions.append(
                CatalogDistribution(
                    identifier=f"{identifier}:distribution:{_stable_component(distribution_id)}",
                    title=_first_text(graph, distribution, (DCTERMS.title,)) or format_value or f"Distribution {index + 1}",
                    access_url=access_url,
                    download_url=download_url,
                    media_type=media_type,
                    format=format_value or None,
                    kind="download" if download_url else "access",
                    is_live=False,
                )
            )

        temporal = None
        temporal_node = next(iter(graph.objects(dataset, DCTERMS.temporal)), None)
        if temporal_node is not None:
            start = _first_text(graph, temporal_node, (dcat_start_date,))
            end = _first_text(graph, temporal_node, (dcat_end_date,))
            if start or end:
                temporal = CatalogTemporalCoverage(start=start, end=end)

        datasets.append(
            CanonicalDataset(
                catalog_id=f"open-data:{source.id}:{external_id}",
                identifier=identifier,
                title=title,
                description=description,
                publisher=publisher,
                license=license_value,
                dataset_type="open-data-catalog",
                source_system=f"open-data:{source.id}",
                external_id=external_id,
                keywords=keywords,
                provenance=CatalogProvenance(
                    source_url=landing_url,
                    last_modified=modified,
                    source_version=modified,
                ),
                source=CatalogSource(
                    id=source.id,
                    code=source.id,
                    name=source.publisher,
                    provider="DCAT/DCAT-AP",
                ),
                temporal=temporal,
                distributions=distributions,
                extensions={
                    "open_data_catalog": {
                        "catalog_id": source.id,
                        "catalog_type": "dcat",
                        "catalog_url": source.url,
                        "rdf_subject": external_id,
                        "distribution_count": len(distribution_nodes),
                    }
                },
            )
        )

    return datasets


class OpenDataCatalogProvider:
    """Harvest metadata-only datasets from administrator-configured CKAN or DCAT catalogs.

    Source payloads are not copied. PiPi stores normalized metadata, distributions and
    provenance so external open-data catalogs participate in the same versioned Data
    Space as local and institutional providers.
    """

    name = "open-data-catalogs"

    def __init__(
        self,
        config_path: str,
        *,
        default_timeout_seconds: float = 30.0,
        allowed_ports: set[int] | None = None,
        root_dir: Path | None = None,
    ) -> None:
        self.root_dir = (root_dir or Path(__file__).resolve().parents[2]).resolve()
        configured_path = Path(config_path)
        self.config_path = (
            configured_path if configured_path.is_absolute() else self.root_dir / configured_path
        ).resolve()
        self.default_timeout_seconds = float(default_timeout_seconds)
        self.allowed_ports = allowed_ports

    def sources(self) -> list[OpenDataCatalogSource]:
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise OpenDataCatalogError(f"Open-data catalog config not found: {self.config_path}") from exc
        except json.JSONDecodeError as exc:
            raise OpenDataCatalogError(f"Open-data catalog config is not valid JSON: {exc}") from exc

        raw_sources = payload.get("catalogs") if isinstance(payload, dict) else payload
        if not isinstance(raw_sources, list):
            raise OpenDataCatalogError("Open-data config must contain a 'catalogs' list.")

        sources: list[OpenDataCatalogSource] = []
        for item in raw_sources:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("enabled", True)):
                continue
            source_type = _clean_text(item.get("type")).casefold()
            if source_type not in {"ckan", "dcat"}:
                raise OpenDataCatalogError(
                    f"Unsupported open-data catalog type {source_type!r}; expected 'ckan' or 'dcat'."
                )
            source_id = _clean_text(item.get("id"))
            url = _clean_text(item.get("url"))
            if not source_id or not url:
                raise OpenDataCatalogError("Every enabled open-data catalog needs id and url.")
            validate_external_resource_url(url, allowed_ports=self.allowed_ports)
            sources.append(
                OpenDataCatalogSource(
                    id=source_id,
                    type=source_type,
                    url=url,
                    publisher=_clean_text(item.get("publisher"), source_id),
                    enabled=True,
                    max_datasets=max(1, int(item.get("max_datasets", 200))),
                    page_size=max(1, min(1000, int(item.get("page_size", 100)))),
                    timeout_seconds=(
                        float(item["timeout_seconds"])
                        if item.get("timeout_seconds") is not None
                        else None
                    ),
                )
            )
        return sources

    async def _ckan_datasets(self, source: OpenDataCatalogSource) -> list[CanonicalDataset]:
        endpoint = source.url.rstrip("/") + "/api/3/action/package_search"
        validate_external_resource_url(endpoint, allowed_ports=self.allowed_ports)
        timeout = source.timeout_seconds or self.default_timeout_seconds
        packages: list[dict[str, Any]] = []
        start = 0

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "PiPi-DataCatalog/1.0 (+metadata-harvester)"},
        ) as client:
            while len(packages) < source.max_datasets:
                rows = min(source.page_size, source.max_datasets - len(packages))
                response = await client.get(endpoint, params={"rows": rows, "start": start})
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("success") is not True:
                    raise OpenDataCatalogError(f"CKAN catalog {source.id!r} returned an unsuccessful response.")
                result = payload.get("result")
                if not isinstance(result, dict):
                    raise OpenDataCatalogError(f"CKAN catalog {source.id!r} returned no result object.")
                page = result.get("results")
                if not isinstance(page, list):
                    raise OpenDataCatalogError(f"CKAN catalog {source.id!r} returned no results list.")
                valid_page = [item for item in page if isinstance(item, dict)]
                packages.extend(valid_page)
                start += len(page)
                total = int(result.get("count") or 0)
                if not page or (total and start >= total):
                    break

        return [ckan_package_to_dataset(source, package) for package in packages[: source.max_datasets]]

    async def _dcat_datasets(self, source: OpenDataCatalogSource) -> list[CanonicalDataset]:
        validate_external_resource_url(source.url, allowed_ports=self.allowed_ports)
        timeout = source.timeout_seconds or self.default_timeout_seconds
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "PiPi-DataCatalog/1.0 (+metadata-harvester)",
                "Accept": "text/turtle, application/ld+json, application/rdf+xml, application/xml;q=0.9, */*;q=0.1",
            },
        ) as client:
            response = await client.get(source.url)
            response.raise_for_status()

        graph = Graph()
        rdf_format = _rdf_format(response.headers.get("content-type", ""), str(response.url))
        try:
            graph.parse(data=response.content, format=rdf_format, publicID=str(response.url))
        except Exception as exc:
            raise OpenDataCatalogError(
                f"Could not parse DCAT catalog {source.id!r} as RDF: {exc}"
            ) from exc
        return dcat_graph_to_datasets(source, graph, max_datasets=source.max_datasets)

    async def datasets(self) -> list[CanonicalDataset]:
        datasets: list[CanonicalDataset] = []
        for source in self.sources():
            try:
                if source.type == "ckan":
                    discovered = await self._ckan_datasets(source)
                else:
                    discovered = await self._dcat_datasets(source)
            except (httpx.HTTPError, ValueError) as exc:
                raise OpenDataCatalogError(
                    f"Open-data catalog {source.id!r} failed: {exc}"
                ) from exc
            datasets.extend(discovered)

        datasets.sort(key=lambda item: item.catalog_id)
        return datasets
