from app.harvesters.sensor_hub import SensorHubHarvester


class StubClient:
    base_url = "https://sensor.example/api/v1/"


def test_live_deg_c_unit_code_maps_to_qudt_uri() -> None:
    harvester = SensorHubHarvester(StubClient())  # type: ignore[arg-type]

    dataset = harvester._to_dataset(
        deployment_property={
            "id": 1,
            "deployment_id": 1,
            "property_id": 1,
            "unit": "DEG_C",
            "resolution": 0.1,
            "uncertainty": "+/-0.3 C",
            "min_value": 15,
            "max_value": 35,
            "sampling_interval": 21600,
            "is_active": True,
            "observation_target": "Indoor classroom air temperature in FOI 1",
        },
        deployment={
            "id": 1,
            "source_id": 1,
            "location_id": 1,
            "active_from": "2026-03-01T09:00:00Z",
            "active_to": "2026-03-18T11:00:00Z",
            "purpose": "Initial indoor deployment before sensor relocation to FOI 2",
        },
        prop={
            "id": 1,
            "name": "air_temperature",
            "description": "Ambient air temperature near the measurement source.",
            "quantity_kind": "qudt:Temperature",
            "default_unit": "DEG_C",
            "data_type": "float",
            "semantic_uri": "http://qudt.org/vocab/quantitykind/Temperature",
        },
        source={
            "id": 1,
            "code": "klima_a01",
            "name": "PiPi Klima Senzor A01",
            "owner": "PiPi Lab",
            "provider": None,
            "license": "CC-BY-4.0",
        },
        location={
            "id": 1,
            "name": "FOI 1 - Ucionica Sjever",
            "latitude": 46.3079,
            "longitude": 16.3368,
        },
    )

    assert dataset.observed_property.unit_code == "DEG_C"
    assert dataset.observed_property.unit_uri == "http://qudt.org/vocab/unit/DEG_C"
    assert " — " not in dataset.title
