from copy import deepcopy

from app.semantic.shacl import validate_dataset_jsonld


def _valid_document() -> dict[str, object]:
    return {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "pipi": "urn:pipi:vocab:",
        },
        "@id": "urn:test:dataset:1",
        "@type": "dcat:Dataset",
        "dct:identifier": "urn:test:dataset:1",
        "dct:title": "Air temperature - test location",
        "dct:description": "Test dataset.",
        "dct:publisher": {"@id": "urn:test:publisher"},
        "dct:license": "test-license",
        "dct:spatial": {"@id": "urn:test:location"},
        "dct:subject": {"@id": "urn:test:property"},
        "dcat:distribution": {
            "@id": "urn:test:distribution:1",
            "@type": "dcat:Distribution",
            "dcat:accessURL": {"@id": "https://example.test/readings"},
            "dcat:accessService": {
                "@id": "urn:test:service",
                "@type": "dcat:DataService",
                "dcat:endpointURL": {"@id": "https://example.test/api"},
                "dcat:endpointDescription": {"@id": "https://example.test/docs"},
                "dcat:servesDataset": {"@id": "urn:test:dataset:1"},
            },
            "pipi:deploymentPropertyId": 1,
        },
    }


def test_valid_catalog_document_conforms_to_pipi_dcat_core_shape() -> None:
    result = validate_dataset_jsonld(_valid_document())

    assert result["profile"] == "pipi-dcat-core-shacl-v1"
    assert result["conforms"] is True
    assert result["result_count"] == 0


def test_missing_distribution_is_reported_by_shacl() -> None:
    document = deepcopy(_valid_document())
    document.pop("dcat:distribution")

    result = validate_dataset_jsonld(document)

    assert result["conforms"] is False
    assert result["result_count"] >= 1
    assert any(
        item["path"] == "http://www.w3.org/ns/dcat#distribution"
        for item in result["results"]
    )
