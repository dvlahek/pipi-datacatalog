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
