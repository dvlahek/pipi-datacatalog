from app.catalog.store import CatalogStore
from app.harvest.history import HarvestHistoryStore


def test_harvest_history_records_finished_run(tmp_path) -> None:
    store = CatalogStore(f"sqlite:///{tmp_path / 'harvest.db'}")
    store.initialize()
    history = HarvestHistoryStore(store)

    run_id = history.start("provider-sync", trigger="manual")
    finished = history.finish(
        run_id,
        status="ok",
        summary={"inserted": 2, "updated": 1, "provider_errors": 0},
    )

    assert finished["id"] == run_id
    assert finished["run_kind"] == "provider-sync"
    assert finished["trigger"] == "manual"
    assert finished["status"] == "ok"
    assert finished["summary"]["inserted"] == 2
    assert finished["finished_at"] is not None

    listed = history.list(limit=10)
    assert len(listed) == 1
    assert listed[0]["id"] == run_id


def test_harvest_history_records_errors(tmp_path) -> None:
    store = CatalogStore(f"sqlite:///{tmp_path / 'harvest-errors.db'}")
    store.initialize()
    history = HarvestHistoryStore(store)

    run_id = history.start("resource-refresh", trigger="scheduled")
    finished = history.finish(run_id, status="error", error="upstream failed")

    assert finished["status"] == "error"
    assert finished["error"] == "upstream failed"
