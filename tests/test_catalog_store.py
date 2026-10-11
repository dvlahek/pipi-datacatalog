import asyncio

from app.catalog.store import CatalogStore
from app.providers.static_web import StaticWebProvider


def test_catalog_store_persists_and_upserts_provider_dataset(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'catalog.db'}"
    store = CatalogStore(database_url)
    store.initialize()

    datasets = asyncio.run(StaticWebProvider().datasets())
    first = store.upsert_datasets(datasets)

    assert first == {"discovered": 1, "inserted": 1, "updated": 0}
    assert store.count_datasets() == 1

    persisted = store.list_datasets()
    assert len(persisted) == 1
    assert persisted[0].external_id == "hr_varazdin1"
    assert persisted[0].source_system == "whatsupcams"
    assert len(persisted[0].distributions) == 2
    assert persisted[0].distributions[0].access_url.startswith("https://")

    changed = datasets[0].model_copy(update={"title": "Updated Varaždin webcam"})
    second = store.upsert_datasets([changed])

    assert second == {"discovered": 1, "inserted": 0, "updated": 1}
    assert store.list_datasets()[0].title == "Updated Varaždin webcam"
