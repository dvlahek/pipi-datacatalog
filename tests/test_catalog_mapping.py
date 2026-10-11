from app.harvesters.sensor_hub import SensorHubHarvester
from app.semantic.dcat import dataset_to_jsonld


class StubClient:
    base_url = "https://sensor.example/api/v1/"


def test_sensor_hub_metadata_maps_to_canonical_dataset_and_jsonld() -> None:
    harvester = SensorHubHarvester(StubClient())  # type: ignore[arg-type]

    dataset = harvester._to_dataset(
        deployment_property={
            "id": 51,
            "deployment_id": 31,
            "property_id": 41,
            "unit": "Cel",
            "resolution": 0.1,
            "uncertainty": "±0.5 °C",
            "min_value": -40,
            "max_value": 85,
            "sampling_interval": 60,
            "is_active": True,
            "observation_target": "Zrak na krovu FOI Varaždin",
        },
        deployment={
            "id": 31,
            "source_id": 11,
            "location_id": 21,
            "platform_name": "FOI Krovna Stanica",
            "platform_type": "station",
            "mounting": "pole",
            "active_from": "2026-04-01T00:00:00Z",
            "active_to": None,
            "purpose": "Praćenje mikroklimatskih uvjeta",
        },
        prop={
            "id": 41,
            "name": "temperature",
            "description": "Temperatura zraka",
            "quantity_kind": "temperature",
            "default_unit": "Cel",
            "data_type": "float",
            "semantic_uri": "http://qudt.org/vocab/quantitykind/Temperature",
            "is_derived": False,
        },
        source={
            "id": 11,
            "type": "sensor",
            "code": "foi-bme680-1",
            "name": "FOI BME680 1",
            "description": "Senzor za temperaturu i vlagu.",
            "owner": "FOI",
            "provider": "FOI Sensor Hub",
            "license": "CC-BY-4.0",
            "manufacturer": "Bosch",
            "model": "BME680",
        },
        location={
            "id": 21,
            "name": "FOI Varazdin Krov",
            "latitude": 46.3059,
            "longitude": 16.3368,
            "elevation": 182.4,
            "address": "Pavlinska 2, Varazdin",
            "geometry_wkt": "POINT(16.336800 46.305900)",
            "environment": "outdoor",
        },
    )

    assert dataset.identifier.endswith(":51")
    assert dataset.observed_property.unit_uri == "http://qudt.org/vocab/unit/DEG_C"
    assert dataset.access.dataset_scoped_filtering_available is False

    jsonld = dataset_to_jsonld(dataset)
    assert jsonld["@type"] == "dcat:Dataset"
    assert jsonld["dct:license"]["@id"] == (
        "https://creativecommons.org/licenses/by/4.0/"
    )
    assert jsonld["dcat:distribution"]["dcat:accessService"]["@type"] == (
        "dcat:DataService"
    )
    assert jsonld["dcat:distribution"]["pipi:deploymentPropertyId"] == 51
    assert jsonld["qudt:hasQuantityKind"]["@id"].endswith("/Temperature")


def test_nullable_source_provider_uses_owner_as_publisher() -> None:
    harvester = SensorHubHarvester(StubClient())  # type: ignore[arg-type]

    dataset = harvester._to_dataset(
        deployment_property={
            "id": 52,
            "deployment_id": 32,
            "property_id": 42,
            "unit": "%",
            "resolution": 0.1,
            "uncertainty": "unknown",
            "min_value": 0,
            "max_value": 100,
            "sampling_interval": 60,
            "is_active": True,
            "observation_target": "Zrak",
        },
        deployment={
            "id": 32,
            "source_id": 12,
            "location_id": 22,
            "platform_name": "Legacy station",
            "platform_type": "station",
            "mounting": "pole",
            "active_from": "2026-04-01T00:00:00Z",
            "active_to": None,
            "purpose": None,
        },
        prop={
            "id": 42,
            "name": "relative_humidity",
            "description": None,
            "quantity_kind": "relative_humidity",
            "default_unit": "%",
            "data_type": "float",
            "semantic_uri": None,
            "is_derived": False,
        },
        source={
            "id": 12,
            "type": "sensor",
            "code": "legacy-12",
            "name": "Legacy sensor",
            "description": None,
            "owner": "FOI",
            "provider": None,
            "license": None,
            "manufacturer": None,
            "model": None,
        },
        location={
            "id": 22,
            "name": "FOI",
            "latitude": None,
            "longitude": None,
            "elevation": None,
            "address": None,
            "geometry_wkt": None,
            "environment": None,
        },
    )

    assert dataset.source.provider is None
    assert dataset.publisher == "FOI"
    assert dataset.license == "unknown"


def test_sparse_optional_metadata_does_not_break_dataset_mapping() -> None:
    harvester = SensorHubHarvester(StubClient())  # type: ignore[arg-type]

    dataset = harvester._to_dataset(
        deployment_property={
            "id": 53,
            "deployment_id": 33,
            "property_id": 43,
            "unit": None,
            "resolution": None,
            "uncertainty": None,
            "min_value": None,
            "max_value": None,
            "sampling_interval": None,
            "is_active": None,
            "observation_target": None,
        },
        deployment={
            "id": 33,
            "source_id": 13,
            "location_id": 23,
            "active_from": None,
            "active_to": None,
            "purpose": None,
        },
        prop={
            "id": 43,
            "name": "custom_value",
            "description": None,
            "quantity_kind": None,
            "default_unit": None,
            "data_type": None,
            "semantic_uri": None,
        },
        source={
            "id": 13,
            "code": "legacy-13",
            "name": "Legacy source",
            "owner": None,
            "provider": None,
            "license": None,
        },
        location={
            "id": 23,
            "name": "Unknown location",
        },
    )

    assert dataset.publisher == "Unknown"
    assert dataset.sampling_interval_seconds is None
    assert dataset.resolution is None
    assert dataset.observed_property.unit_code is None

    jsonld = dataset_to_jsonld(dataset)
    assert "dct:temporal" not in jsonld
    assert "pipi:resolution" not in jsonld
    assert "pipi:unitCode" not in jsonld["dcat:distribution"]
