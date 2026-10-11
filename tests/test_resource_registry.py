from app.catalog.store import CatalogStore
from app.resources.fetcher import ResourceProbe, detect_resource_type
from app.resources.service import dataset_from_registered_resource


def test_resource_registry_persists_and_links_dataset(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'resources.db'}"
    store = CatalogStore(database_url)
    store.initialize()

    resource = store.create_resource(
        source_url="https://example.com/data.csv",
        name="Example CSV",
        requested_type="auto",
        metadata={"publisher": "Example", "license": "unknown", "keywords": ["demo"]},
    )

    probe = ResourceProbe(
        final_url="https://example.com/data.csv",
        media_type="text/csv",
        detected_type="csv",
        content_sha256="a" * 64,
        byte_size=123,
        etag='"v1"',
        last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        title_hint="data.csv",
    )
    dataset = dataset_from_registered_resource(resource, probe)
    stats = store.upsert_datasets([dataset])
    updated = store.mark_resource_success(
        int(resource["id"]),
        detected_type="csv",
        dataset_identifier=dataset.identifier,
        media_type="text/csv",
        etag=probe.etag,
        last_modified=probe.last_modified,
        content_sha256=probe.content_sha256,
    )

    assert stats["inserted"] == 1
    assert updated["dataset_identifier"] == dataset.identifier
    assert updated["detected_type"] == "csv"
    assert updated["last_content_sha256"] == "a" * 64
    assert len(store.list_resources()) == 1


def test_live_hls_playlist_churn_does_not_change_catalog_snapshot(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'hls.db'}"
    store = CatalogStore(database_url)
    store.initialize()
    resource = store.create_resource(
        source_url="https://example.com/live.m3u8",
        name="Live camera",
        requested_type="auto",
    )

    first_probe = ResourceProbe(
        final_url="https://example.com/live.m3u8",
        media_type="application/vnd.apple.mpegurl",
        detected_type="video",
        content_sha256="a" * 64,
        byte_size=300,
        etag='"segment-set-a"',
        last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
        title_hint="live.m3u8",
    )
    second_probe = ResourceProbe(
        final_url="https://example.com/live.m3u8",
        media_type="application/vnd.apple.mpegurl",
        detected_type="video",
        content_sha256="b" * 64,
        byte_size=450,
        etag='"segment-set-b"',
        last_modified="Mon, 01 Jan 2026 00:01:00 GMT",
        title_hint="live.m3u8",
    )

    first = dataset_from_registered_resource(resource, first_probe)
    second = dataset_from_registered_resource(resource, second_probe)
    first_stats = store.upsert_datasets([first])
    second_stats = store.upsert_datasets([second])

    assert first.provenance.content_sha256 is None
    assert first.provenance.etag is None
    assert first.extensions["resource_registry"]["byte_size"] is None
    assert first_stats["versions_created"] == 1
    assert second_stats["versions_created"] == 0


def test_resource_type_detection() -> None:
    assert detect_resource_type("https://x.test/data.csv", "text/plain", b"a,b\n1,2") == "csv"
    assert detect_resource_type("https://x.test/data", "application/json", b"{}") == "json"
    assert detect_resource_type("https://x.test/report", "application/pdf", b"%PDF-1.7") == "document"
    assert detect_resource_type("https://x.test/live.m3u8", "application/octet-stream", b"#EXTM3U") == "video"
