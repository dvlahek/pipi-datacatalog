from __future__ import annotations

from typing import Any

from app.models.catalog import CanonicalDataset


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


def _location(dataset: CanonicalDataset) -> dict[str, Any]:
    location = dataset.location
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
    if not dataset.temporal.start and not dataset.temporal.end:
        return None

    result: dict[str, Any] = {"@type": "dct:PeriodOfTime"}
    if dataset.temporal.start:
        result["dcat:startDate"] = {
            "@value": dataset.temporal.start,
            "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
        }
    if dataset.temporal.end:
        result["dcat:endDate"] = {
            "@value": dataset.temporal.end,
            "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
        }
    return result


def _subject(dataset: CanonicalDataset) -> dict[str, Any]:
    prop = dataset.observed_property
    subject: dict[str, Any] = {
        "@id": f"urn:pipi:property:{prop.id}",
        "@type": "skos:Concept",
        "skos:prefLabel": prop.name.replace("_", " "),
    }
    if prop.semantic_uri:
        subject["skos:exactMatch"] = _as_id(prop.semantic_uri)
    return subject


def _distribution(dataset: CanonicalDataset) -> dict[str, Any]:
    access = dataset.access
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
        "dcat:mediaType": _as_id(
            "https://www.iana.org/assignments/media-types/application/json"
        ),
        "pipi:deploymentPropertyId": access.deployment_property_id,
        "pipi:datasetScopedFilteringAvailable": (
            access.dataset_scoped_filtering_available
        ),
    }

    unit = dataset.observed_property
    if unit.unit_uri:
        distribution["qudt:hasUnit"] = _as_id(unit.unit_uri)
    elif unit.unit_code:
        distribution["pipi:unitCode"] = unit.unit_code

    return distribution


def dataset_to_jsonld(dataset: CanonicalDataset) -> dict[str, Any]:
    """Serialize one canonical dataset as DCAT/DCAT-AP-oriented JSON-LD."""

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
        "dct:spatial": _location(dataset),
        "dct:subject": _subject(dataset),
        "dcat:distribution": _distribution(dataset),
        "pipi:sourceCode": dataset.source.code,
    }

    temporal = _temporal(dataset)
    if temporal:
        doc["dct:temporal"] = temporal
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
    if dataset.observed_property.semantic_uri:
        doc["qudt:hasQuantityKind"] = _as_id(
            dataset.observed_property.semantic_uri
        )

    return doc
