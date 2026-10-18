from __future__ import annotations

from typing import Any

from app.models.catalog import CanonicalDataset, CatalogDistribution


_CONTEXT = {
    "dcat": "http://www.w3.org/ns/dcat#",
    "dct": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "schema": "https://schema.org/",
    "locn": "http://www.w3.org/ns/locn#",
    "geosparql": "http://www.opengis.net/ont/geosparql#",
    "qudt": "http://qudt.org/schema/qudt/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "pipi": "urn:pipi:vocab:",
}


def _as_id(value: str) -> dict[str, str]:
    return {"@id": value}


def _license_value(value: str) -> str | dict[str, str]:
    normalized = value.strip().upper()
    if normalized == "CC-BY-4.0":
        return _as_id("https://creativecommons.org/licenses/by/4.0/")
    return value


def _media_type_uri(media_type: str) -> dict[str, str]:
    return _as_id(
        "https://www.iana.org/assignments/media-types/"
        f"{media_type.strip().lower()}"
    )


def _location(dataset: CanonicalDataset) -> dict[str, Any] | None:
    location = dataset.location
    if location is None:
        return None

    result: dict[str, Any] = {
        "@type": "dct:Location",
        "schema:name": location.name,
    }

    if location.address:
        result["locn:address"] = location.address
    if location.latitude is not None:
        result["schema:latitude"] = location.latitude
    if location.longitude is not None:
        result["schema:longitude"] = location.longitude
    if location.elevation is not None:
        result["schema:elevation"] = location.elevation
    if location.geometry_wkt:
        result["locn:geometry"] = {
            "@value": location.geometry_wkt,
            "@type": "geosparql:wktLiteral",
        }

    return result


def _temporal(dataset: CanonicalDataset) -> dict[str, Any] | None:
    temporal = dataset.temporal
    if temporal is None or (not temporal.start and not temporal.end):
        return None

    result: dict[str, Any] = {"@type": "dct:PeriodOfTime"}
    if temporal.start:
        result["dcat:startDate"] = {
            "@value": temporal.start,
            "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
        }
    if temporal.end:
        result["dcat:endDate"] = {
            "@value": temporal.end,
            "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
        }
    return result


def _subject(dataset: CanonicalDataset) -> dict[str, Any]:
    prop = dataset.observed_property
    if prop is not None:
        subject: dict[str, Any] = {
            "@id": f"urn:pipi:property:{prop.id}",
            "@type": "skos:Concept",
            "skos:prefLabel": prop.name.replace("_", " "),
        }
        if prop.semantic_uri:
            subject["skos:exactMatch"] = _as_id(prop.semantic_uri)
        return subject

    return {
        "@id": f"urn:pipi:subject:{dataset.dataset_type}",
        "@type": "skos:Concept",
        "skos:prefLabel": dataset.dataset_type.replace("-", " "),
    }


def _distribution_from_model(
    dataset: CanonicalDataset,
    distribution: CatalogDistribution,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "@id": distribution.identifier,
        "@type": "dcat:Distribution",
        "dct:title": distribution.title,
        "dcat:accessURL": _as_id(distribution.access_url),
        "dcat:mediaType": _media_type_uri(distribution.media_type),
    }

    if distribution.format:
        result["dct:format"] = distribution.format
    if distribution.download_url:
        result["dcat:downloadURL"] = _as_id(distribution.download_url)
    if distribution.kind:
        result["pipi:distributionKind"] = distribution.kind
    if distribution.is_live is not None:
        result["pipi:isLive"] = distribution.is_live
    if distribution.source_media_type:
        result["pipi:sourceMediaType"] = distribution.source_media_type

    if dataset.access is not None and distribution.kind == "api":
        result["pipi:deploymentPropertyId"] = dataset.access.deployment_property_id
        result["pipi:datasetScopedFilteringAvailable"] = (
            dataset.access.dataset_scoped_filtering_available
        )
        prop = dataset.observed_property
        if prop is not None:
            if prop.unit_uri:
                result["qudt:hasUnit"] = _as_id(prop.unit_uri)
            elif prop.unit_code:
                result["pipi:unitCode"] = prop.unit_code

    if distribution.access_service_identifier:
        service: dict[str, Any] = {
            "@id": distribution.access_service_identifier,
            "@type": "dcat:DataService",
            "dct:title": f"{distribution.title} service",
            "dcat:endpointURL": _as_id(
                distribution.endpoint_url or distribution.access_url
            ),
            "dcat:servesDataset": _as_id(dataset.identifier),
        }
        if distribution.endpoint_description:
            service["dcat:endpointDescription"] = _as_id(
                distribution.endpoint_description
            )
        result["dcat:accessService"] = service

    return result


def _legacy_distribution(dataset: CanonicalDataset) -> dict[str, Any] | None:
    access = dataset.access
    if access is None:
        return None

    service = {
        "@id": access.data_service_identifier,
        "@type": "dcat:DataService",
        "dct:title": "PiPi Sensor Hub API",
        "dcat:endpointURL": _as_id(access.endpoint_url),
        "dcat:endpointDescription": _as_id(access.endpoint_description),
        "dcat:servesDataset": _as_id(dataset.identifier),
    }

    distribution: dict[str, Any] = {
        "@id": f"{dataset.identifier}:distribution:api",
        "@type": "dcat:Distribution",
        "dct:title": "Sensor Hub API access",
        "dcat:accessURL": _as_id(access.readings_url),
        "dcat:accessService": service,
        "dcat:mediaType": _media_type_uri("application/json"),
        "pipi:deploymentPropertyId": access.deployment_property_id,
        "pipi:datasetScopedFilteringAvailable": (
            access.dataset_scoped_filtering_available
        ),
    }

    prop = dataset.observed_property
    if prop is not None:
        if prop.unit_uri:
            distribution["qudt:hasUnit"] = _as_id(prop.unit_uri)
        elif prop.unit_code:
            distribution["pipi:unitCode"] = prop.unit_code

    return distribution


def _distributions(dataset: CanonicalDataset) -> dict[str, Any] | list[dict[str, Any]]:
    items = [
        _distribution_from_model(dataset, distribution)
        for distribution in dataset.distributions
    ]

    if not items:
        legacy = _legacy_distribution(dataset)
        if legacy is not None:
            items.append(legacy)

    if not items:
        raise ValueError(f"Dataset {dataset.identifier} has no distribution.")

    if len(items) == 1:
        return items[0]
    return items


def dataset_to_jsonld(dataset: CanonicalDataset) -> dict[str, Any]:
    """Serialize a provider-neutral catalog dataset as DCAT-oriented JSON-LD."""

    doc: dict[str, Any] = {
        "@context": _CONTEXT,
        "@id": dataset.identifier,
        "@type": "dcat:Dataset",
        "dct:identifier": dataset.identifier,
        "dct:title": dataset.title,
        "dct:description": dataset.description,
        "dct:publisher": {
            "@type": "foaf:Agent",
            "foaf:name": dataset.publisher,
        },
        "dct:license": _license_value(dataset.license),
        "dct:subject": _subject(dataset),
        "dcat:distribution": _distributions(dataset),
        "pipi:datasetType": dataset.dataset_type,
        "pipi:sourceSystem": dataset.source_system,
    }

    if dataset.external_id:
        doc["pipi:externalId"] = dataset.external_id
    if dataset.keywords:
        doc["dcat:keyword"] = dataset.keywords

    location = _location(dataset)
    if location:
        doc["dct:spatial"] = location

    temporal = _temporal(dataset)
    if temporal:
        doc["dct:temporal"] = temporal

    if dataset.source is not None:
        doc["pipi:sourceCode"] = dataset.source.code

    if dataset.observation_target:
        doc["pipi:observationTarget"] = dataset.observation_target
    if dataset.sampling_interval_seconds is not None:
        doc["pipi:samplingIntervalSeconds"] = dataset.sampling_interval_seconds
    if dataset.uncertainty:
        doc["pipi:uncertainty"] = dataset.uncertainty
    if dataset.resolution is not None:
        doc["pipi:resolution"] = dataset.resolution
    if dataset.is_active is not None:
        doc["pipi:isActive"] = dataset.is_active
    if dataset.min_value is not None:
        doc["pipi:minValue"] = dataset.min_value
    if dataset.max_value is not None:
        doc["pipi:maxValue"] = dataset.max_value

    prop = dataset.observed_property
    if prop is not None and prop.semantic_uri:
        doc["qudt:hasQuantityKind"] = _as_id(prop.semantic_uri)

    return doc
