from app.activity.store import ActivityStore, RagJobStore
from app.catalog.store import CatalogStore


def _store(tmp_path) -> CatalogStore:
    store = CatalogStore(f"sqlite:///{tmp_path / 'catalog.db'}")
    store.initialize()
    return store


def test_rag_job_lifecycle_is_persistent(tmp_path) -> None:
    store = _store(tmp_path)
    jobs = RagJobStore(store)

    created = jobs.create(
        target_kind="resource",
        target_identifier="2",
        label="Example repository",
    )
    assert created["status"] == "queued"
    assert jobs.active_for_target("resource", "2")["id"] == created["id"]

    running = jobs.start(created["id"], stage="indexing", message="Working")
    assert running["status"] == "running"

    progress = jobs.progress(
        created["id"],
        stage="fetching-files",
        message="Fetching source files",
        current=3,
        total=10,
    )
    assert progress["progress_current"] == 3
    assert progress["progress_total"] == 10

    finished = jobs.succeed(created["id"], {"chunk_count": 12, "dataset_version": 4})
    assert finished["status"] == "success"
    assert finished["result"]["chunk_count"] == 12
    assert jobs.active_for_target("resource", "2") is None


def test_activity_store_records_errors(tmp_path) -> None:
    store = _store(tmp_path)
    activity = ActivityStore(store)

    activity.log("info", "rag", "index-started", "Started")
    activity.log("error", "rag", "index-failed", "Failed", details={"job_id": 7})

    rows = activity.list(limit=10)
    assert len(rows) == 2
    assert rows[0]["level"] == "error"
    assert rows[0]["details"]["job_id"] == 7
    assert activity.list(limit=10, level="error")[0]["action"] == "index-failed"
