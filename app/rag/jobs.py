from __future__ import annotations

from typing import Any

from app.activity.store import ActivityStore, RagJobStore
from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.embeddings import EmbeddingError, backfill_current_embeddings, embed_dataset_chunks
from app.rag.service import index_catalog_dataset, index_registered_resource


def _result_summary(result: dict[str, Any]) -> str:
    github = result.get("github_index")
    embedding = result.get("embedding")
    vector_note = ""
    if isinstance(embedding, dict):
        if embedding.get("status") == "error":
            vector_note = " Vector embedding failed; lexical index remains available."
        else:
            vector_note = f" Embedded {embedding.get('embedded', 0)} chunk(s)."
    if isinstance(github, dict):
        return (
            f"Indexed {github.get('files_indexed', 0)} repository file(s) into "
            f"{result.get('chunk_count', 0)} chunk(s), dataset version {result.get('dataset_version')}."
            f"{vector_note}"
        )
    return (
        f"Indexed dataset version {result.get('dataset_version')} into "
        f"{result.get('chunk_count', 0)} chunk(s).{vector_note}"
    )


def _embed_after_index(
    store: CatalogStore,
    settings: Settings,
    jobs: RagJobStore,
    activity: ActivityStore,
    job_id: int,
    result: dict[str, Any],
) -> None:
    dataset_identifier = str(result.get("dataset_identifier") or "")
    if not dataset_identifier:
        return

    jobs.progress(
        job_id,
        stage="embedding",
        message="Building vector embeddings for indexed chunks.",
    )
    try:
        embedding = embed_dataset_chunks(
            store,
            settings,
            dataset_identifier,
            progress=lambda current, total: jobs.progress(
                job_id,
                stage="embedding",
                message=f"Embedding current chunks with {settings.rag_embedding_model}.",
                current=current,
                total=total,
            ),
        )
        result["embedding"] = embedding
        activity.log(
            "info",
            "rag",
            "embedding-completed",
            f"Embedded {embedding.get('embedded', 0)} chunk(s) for {dataset_identifier}.",
            details={"job_id": job_id, "dataset_identifier": dataset_identifier, **embedding},
        )
    except (EmbeddingError, RuntimeError, ValueError) as exc:
        error = str(exc) or exc.__class__.__name__
        result["embedding"] = {"status": "error", "error": error}
        activity.log(
            "warning",
            "rag",
            "embedding-failed",
            f"Text indexing succeeded but vector embedding failed: {error}",
            details={"job_id": job_id, "dataset_identifier": dataset_identifier},
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
        _embed_after_index(store, settings, jobs, activity, job_id, result)
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
        _embed_after_index(store, settings, jobs, activity, job_id, result)
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


async def run_embedding_backfill_job(
    store: CatalogStore,
    settings: Settings,
    job_id: int,
    limit: int | None = None,
) -> None:
    jobs = RagJobStore(store)
    activity = ActivityStore(store)
    jobs.start(
        job_id,
        stage="embedding",
        message=f"Building vectors with {settings.rag_embedding_model}.",
    )
    activity.log(
        "info",
        "rag",
        "embedding-backfill-started",
        f"Started vector backfill with {settings.rag_embedding_model}.",
        details={"job_id": job_id, "limit": limit},
    )
    try:
        result = backfill_current_embeddings(
            store,
            settings,
            limit=limit,
            progress=lambda current, total: jobs.progress(
                job_id,
                stage="embedding",
                message=f"Building vectors with {settings.rag_embedding_model}.",
                current=current,
                total=total,
            ),
        )
        result = {"embedding_backfill": result}
        jobs.succeed(job_id, result)
        activity.log(
            "info",
            "rag",
            "embedding-backfill-completed",
            f"Embedded {result['embedding_backfill'].get('embedded', 0)} current chunk(s).",
            details={"job_id": job_id, **result["embedding_backfill"]},
        )
    except Exception as exc:
        error = str(exc) or exc.__class__.__name__
        jobs.fail(job_id, error)
        activity.log(
            "error",
            "rag",
            "embedding-backfill-failed",
            f"Vector backfill failed: {error}",
            details={"job_id": job_id},
        )
