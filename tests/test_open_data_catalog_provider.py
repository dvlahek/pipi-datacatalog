from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from app.providers.open_data_catalog import (
    OpenDataCatalogSource,
    ckan_package_to_dataset,
    dcat_graph_to_datasets,
)
from app.semantic.dcat import dataset_to_jsonld
from app.semantic.shacl import validate_dataset_jsonld


def _source(source_type: str) -> OpenDataCatalogSource:
    return OpenDataCatalogSource(
        id="test-catalog",
        type=source_type,
        url="https://data.example.org",
        publisher="Example Open Data",
        max_datasets=20,
    )


def test_ckan_package_is_normalized_as_versioned_catalog_metadata() -> None:
    package = {
        "id": "pkg-123",
        "name": "air-quality-croatia",
        "title": "Air quality Croatia",
        "notes": "Hourly air-quality observations.",
        "metadata_created": "2026-01-01T12:00:00",
        "metadata_modified": "2026-02-03T14:00:00",
        "license_title": "CC BY 4.0",
        "organization": {"name": "env-agency", "title": "Environment Agency"},
        "tags": [{"name": "air quality"}, {"name": "Croatia"}],
        "groups": [{"name": "environment", "display_name": "Environment"}],
        "resources": [
            {
                "id": "resource-1",
                "name": "CSV download",
                "url": "https://data.example.org/files/air.csv",
                "format": "CSV",
                "mimetype": "text/csv",
            }
        ],
    }

    dataset = ckan_package_to_dataset(_source("ckan"), package)

    assert dataset.dataset_type == "open-data-catalog"
    assert dataset.source_system == "open-data:test-catalog"
    assert dataset.external_id == "pkg-123"
    assert dataset.title == "Air quality Croatia"
    assert dataset.publisher == "Environment Agency"
    assert dataset.license == "CC BY 4.0"
    assert dataset.provenance.last_modified == "2026-02-03T14:00:00"
    assert dataset.provenance.source_url.endswith("/dataset/air-quality-croatia")
    assert dataset.keywords == ["air quality", "Croatia", "Environment"]
    assert len(dataset.distributions) == 1
    assert dataset.distributions[0].media_type == "text/csv"
    assert dataset.extensions["open_data_catalog"]["catalog_type"] == "ckan"

    validation = validate_dataset_jsonld(dataset_to_jsonld(dataset))
    assert validation["conforms"] is True


def test_dcat_graph_is_normalized_without_copying_payload() -> None:
    DCAT = Namespace("http://www.w3.org/ns/dcat#")
    FOAF = Namespace("http://xmlns.com/foaf/0.1/")
    dataset_uri = URIRef("https://data.example.org/dataset/traffic")
    distribution_uri = URIRef("https://data.example.org/distribution/traffic-csv")
    publisher_uri = URIRef("https://data.example.org/org/city")

    graph = Graph()
    graph.add((dataset_uri, RDF.type, DCAT.Dataset))
    graph.add((dataset_uri, DCTERMS.title, Literal("Traffic counts", lang="en")))
    graph.add((dataset_uri, DCTERMS.description, Literal("Daily traffic counts.")))
    graph.add((dataset_uri, DCTERMS.publisher, publisher_uri))
    graph.add((publisher_uri, FOAF.name, Literal("Example City")))
    graph.add((dataset_uri, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))
    graph.add((dataset_uri, DCTERMS.modified, Literal("2026-03-04")))
    graph.add((dataset_uri, DCAT.keyword, Literal("traffic")))
    graph.add((dataset_uri, DCAT.distribution, distribution_uri))
    graph.add((distribution_uri, DCTERMS.title, Literal("CSV")))
    graph.add((distribution_uri, DCAT.accessURL, URIRef("https://data.example.org/files/traffic.csv")))
    graph.add((distribution_uri, DCAT.downloadURL, URIRef("https://data.example.org/files/traffic.csv")))
    graph.add((distribution_uri, DCAT.mediaType, Literal("text/csv")))

    datasets = dcat_graph_to_datasets(_source("dcat"), graph)

    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset.external_id == str(dataset_uri)
    assert dataset.title == "Traffic counts"
    assert dataset.publisher == "Example City"
    assert dataset.provenance.source_version == "2026-03-04"
    assert dataset.distributions[0].access_url.endswith("traffic.csv")
    assert dataset.extensions["open_data_catalog"]["catalog_type"] == "dcat"


def test_ckan_identity_is_stable_when_descriptive_metadata_changes() -> None:
    package = {
        "id": "stable-id",
        "name": "stable-name",
        "title": "Old title",
        "notes": "Old description",
        "resources": [],
    }
    first = ckan_package_to_dataset(_source("ckan"), package)

    package["title"] = "New title"
    package["notes"] = "New description"
    package["metadata_modified"] = "2026-05-01"
    second = ckan_package_to_dataset(_source("ckan"), package)

    assert second.identifier == first.identifier
    assert second.catalog_id == first.catalog_id
    assert second.title != first.title
    assert second.provenance.last_modified == "2026-05-01"
