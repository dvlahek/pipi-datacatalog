from __future__ import annotations

from typing import Any

from app.activity.store import ActivityStore, RagJobStore
from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.service import index_catalog_dataset, index_registered_resource


def _result_summary(result: dict[str, Any]) -> str:
    github = result.get("github_index")
    if isinstance(github, dict):
        return (
            f"Indexed {github.get('files_indexed', 0)} repository file(s) into "
            f"{result.get('chunk_count', 0)} chunk(s), dataset version {result.get('dataset_version')}."
        )
    return (
        f"Indexed dataset version {result.get('dataset_version')} into "
        f"{result.get('chunk_count', 0)} chunk(s)."
    )


async def run_dataset_index_job(
    store: CatalogStore,
    settings: Settings,
    job_id: int,
    dataset_identifier: str,
    label: str,
) -> None:
    jobs = RagJobStore(store)
    activity = ActivityStore(store)
    jobs.start(job_id, stage="indexing", message=f"Indexing {label}. This may take a while.")
    activity.log(
        "info",
        "rag",
        "index-started",
        f"Started background indexing for {label}.",
        details={"job_id": job_id, "dataset_identifier": dataset_identifier},
    )
    try:
        result = await index_catalog_dataset(store, dataset_identifier, settings)
        jobs.succeed(job_id, result)
        activity.log(
            "info",
            "rag",
            "index-completed",
            _result_summary(result),
            details={"job_id": job_id, "dataset_identifier": dataset_identifier, "result": result},
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        jobs.fail(job_id, error)
        activity.log(
            "error",
            "rag",
            "index-failed",
            f"Indexing failed for {label}: {error}",
            details={"job_id": job_id, "dataset_identifier": dataset_identifier},
        )


async def run_resource_index_job(
    store: CatalogStore,
    settings: Settings,
    job_id: int,
    resource_id: int,
    label: str,
) -> None:
    jobs = RagJobStore(store)
    activity = ActivityStore(store)
    jobs.start(job_id, stage="indexing", message=f"Indexing {label}. This may take a while.")
    activity.log(
        "info",
        "rag",
        "index-started",
        f"Started background indexing for {label}.",
        details={"job_id": job_id, "resource_id": resource_id},
    )
    try:
        result = await index_registered_resource(store, resource_id, settings)
        jobs.succeed(job_id, result)
        activity.log(
            "info",
            "rag",
            "index-completed",
            _result_summary(result),
            details={"job_id": job_id, "resource_id": resource_id, "result": result},
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        jobs.fail(job_id, error)
        activity.log(
            "error",
            "rag",
            "index-failed",
            f"Indexing failed for {label}: {error}",
            details={"job_id": job_id, "resource_id": resource_id},
        )
