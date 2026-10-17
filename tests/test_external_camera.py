import asyncio

from app.providers.static_web import StaticWebProvider
from app.search.catalog import search_datasets
from app.semantic.dcat import dataset_to_jsonld
from app.semantic.shacl import validate_dataset_jsonld


def _camera_dataset():
    return asyncio.run(StaticWebProvider().datasets())[0]


def test_varazdin_webcam_is_provider_neutral_catalog_dataset() -> None:
    dataset = _camera_dataset()

    assert dataset.catalog_id == "webcam:whatsupcams:hr_varazdin1"
    assert dataset.dataset_type == "live-video-stream"
    assert dataset.source_system == "whatsupcams"
    assert dataset.observed_property is None
    assert dataset.access is None
    assert len(dataset.distributions) == 2

    hls = next(item for item in dataset.distributions if item.kind == "live-stream")
    assert hls.access_url.endswith("/hls/hr_varazdin1.m3u8")
    assert hls.media_type == "application/vnd.apple.mpegurl"
    assert hls.source_media_type == "application/x-mpegURL"
    assert hls.is_live is True

    snapshot = next(item for item in dataset.distributions if item.kind == "snapshot")
    assert snapshot.media_type == "image/jpeg"


def test_varazdin_webcam_jsonld_and_search() -> None:
    dataset = _camera_dataset()
    jsonld = dataset_to_jsonld(dataset)

    assert jsonld["@type"] == "dcat:Dataset"
    assert jsonld["pipi:datasetType"] == "live-video-stream"
    assert isinstance(jsonld["dcat:distribution"], list)
    assert len(jsonld["dcat:distribution"]) == 2

    validation = validate_dataset_jsonld(jsonld)
    assert validation["conforms"] is True

    camera = search_datasets([dataset], "camera varazdin")
    assert len(camera) == 1

    hls = search_datasets([dataset], "HLS")
    assert len(hls) == 1
