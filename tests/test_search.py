from app.models.catalog import (
    CatalogAccess,
    CatalogLocation,
    CatalogObservedProperty,
    CatalogSource,
    CatalogTemporalCoverage,
    CanonicalDataset,
)
from app.search.catalog import search_datasets


def _dataset(
    *,
    dataset_id: int,
    title: str,
    property_name: str,
    location_name: str,
    source_name: str,
    description: str,
) -> CanonicalDataset:
    return CanonicalDataset(
        catalog_id=f"sensor-hub:deployment-property:{dataset_id}",
        identifier=(
            "urn:pipi:dataset:sensor-hub:deployment-property:"
            f"{dataset_id}"
        ),
        title=title,
        description=description,
        publisher="PiPi Lab",
        license="CC-BY-4.0",
        source=CatalogSource(
            id=dataset_id,
            code=f"source-{dataset_id}",
            name=source_name,
            owner="PiPi Lab",
        ),
        location=CatalogLocation(id=dataset_id, name=location_name),
        temporal=CatalogTemporalCoverage(start="2026-01-01T00:00:00Z"),
        observed_property=CatalogObservedProperty(
            id=dataset_id,
            name=property_name,
            quantity_kind="qudt:Temperature",
            semantic_uri=(
                "http://qudt.org/vocab/quantitykind/Temperature"
                if "temperature" in property_name
                else None
            ),
            data_type="float",
            unit_code="DEG_C",
            unit_uri="http://qudt.org/vocab/unit/DEG_C",
        ),
        sampling_interval_seconds=60,
        resolution=0.1,
        uncertainty="+/-0.3 C",
        min_value=-20,
        max_value=50,
        is_active=True,
        observation_target="Indoor air",
        access=CatalogAccess(
            provider="sensor-hub",
            data_service_identifier="urn:pipi:dataservice:sensor-hub",
            endpoint_url="https://sensor.example/api/v1",
            endpoint_description="https://sensor.example/docs/",
            readings_url="https://sensor.example/api/v1/readings",
            deployment_property_id=dataset_id,
        ),
    )


def test_search_matches_and_ranks_catalog_metadata() -> None:
    datasets = [
        _dataset(
            dataset_id=1,
            title="air temperature - FOI 1 - Sensor A01",
            property_name="air_temperature",
            location_name="FOI 1 - Ucionica Sjever",
            source_name="PiPi Klima Senzor A01",
            description="Ambient air temperature in a classroom.",
        ),
        _dataset(
            dataset_id=2,
            title="relative humidity - FOI 2 - Sensor B01",
            property_name="relative_humidity",
            location_name="FOI 2 - Ucionica Jug",
            source_name="PiPi Klima Senzor B01",
            description="Indoor relative humidity.",
        ),
    ]

    temperature = search_datasets(datasets, "temperature")
    assert len(temperature) == 1
    assert temperature[0]["dataset"]["access"]["deployment_property_id"] == 1
    assert "title" in temperature[0]["matched_fields"]
    assert "observed_property.name" in temperature[0]["matched_fields"]

    foi_two = search_datasets(datasets, "FOI 2")
    assert len(foi_two) == 1
    assert foi_two[0]["dataset"]["access"]["deployment_property_id"] == 2

    humidity_classroom = search_datasets(datasets, "humidity ucionica")
    assert len(humidity_classroom) == 1
    assert humidity_classroom[0]["dataset"]["access"]["deployment_property_id"] == 2


def test_search_is_case_and_diacritic_insensitive() -> None:
    datasets = [
        _dataset(
            dataset_id=3,
            title="temperatura - Učionica Sjever",
            property_name="air_temperature",
            location_name="Učionica Sjever",
            source_name="Senzor C01",
            description="Temperatura zraka.",
        )
    ]

    results = search_datasets(datasets, "UCIONICA")
    assert len(results) == 1
    assert results[0]["dataset"]["access"]["deployment_property_id"] == 3
