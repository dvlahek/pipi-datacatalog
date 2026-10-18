from __future__ import annotations

import hashlib
import json
from typing import Any

from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.profiles import (
    catalog_snapshot_hash,
    get_retrieval_profile,
    get_retrieval_run,
)
from app.rag.search import search_rag


def evidence_key(item: dict[str, Any]) -> tuple[str, int, int]:
    """Stable identity of one retrieved chunk within a versioned dataset."""

    return (
        str(item.get("dataset_identifier") or ""),
        int(item.get("dataset_version") or 0),
        int(item.get("chunk_index") or 0),
    )


def source_key(item: dict[str, Any]) -> tuple[str, int]:
    """Stable identity of the versioned dataset that supplied one evidence chunk."""

    return (
        str(item.get("dataset_identifier") or ""),
        int(item.get("dataset_version") or 0),
    )


def _ordered_unique(values: list[tuple[str, int]]) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    ordered: list[tuple[str, int]] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def ordered_evidence_hash(results: list[dict[str, Any]]) -> str:
    """Hash the ordered evidence identity, excluding scores and display metadata."""

    payload = [evidence_key(item) for item in results]
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compare_ranked_evidence(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    limit: int,
) -> dict[str, Any]:
    """Measure chunk-level and source-level drift between two top-k retrieval results.

    Chunk-level metrics treat every retrieved chunk as distinct evidence. Source-level
    metrics collapse repeated chunks from the same versioned dataset so a change of
    paragraph within one document is not confused with a change of source document.
    """

    k = max(1, int(limit))
    left_items = left[:k]
    right_items = right[:k]
    left_keys = [evidence_key(item) for item in left_items]
    right_keys = [evidence_key(item) for item in right_items]
    left_set = set(left_keys)
    right_set = set(right_keys)
    shared = left_set & right_set
    union = left_set | right_set

    available = min(k, len(left_keys), len(right_keys))
    retention = len(shared) / available if available else 1.0
    jaccard = len(shared) / len(union) if union else 1.0

    left_rank = {key: rank for rank, key in enumerate(left_keys, start=1)}
    right_rank = {key: rank for rank, key in enumerate(right_keys, start=1)}
    shifts = [abs(left_rank[key] - right_rank[key]) for key in shared]

    left_sources = _ordered_unique([source_key(item) for item in left_items])
    right_sources = _ordered_unique([source_key(item) for item in right_items])
    left_source_set = set(left_sources)
    right_source_set = set(right_sources)
    shared_sources = left_source_set & right_source_set
    source_union = left_source_set | right_source_set
    source_available = min(len(left_sources), len(right_sources))
    source_retention = len(shared_sources) / source_available if source_available else 1.0
    source_jaccard = len(shared_sources) / len(source_union) if source_union else 1.0

    return {
        "top_k": k,
        "left_count": len(left_keys),
        "right_count": len(right_keys),
        "shared_count": len(shared),
        "retention_at_k": round(retention, 8),
        "churn_at_k": round(1.0 - retention, 8),
        "jaccard_at_k": round(jaccard, 8),
        "top1_same": bool(left_keys and right_keys and left_keys[0] == right_keys[0]),
        "ordered_evidence_same": left_keys == right_keys,
        "left_evidence_hash": ordered_evidence_hash(left_items),
        "right_evidence_hash": ordered_evidence_hash(right_items),
        "mean_abs_rank_shift_common": round(sum(shifts) / len(shifts), 8) if shifts else None,
        "max_abs_rank_shift_common": max(shifts) if shifts else None,
        "left_only": [list(key) for key in left_keys if key not in right_set],
        "right_only": [list(key) for key in right_keys if key not in left_set],
        "left_source_count": len(left_sources),
        "right_source_count": len(right_sources),
        "shared_source_count": len(shared_sources),
        "source_retention_at_k": round(source_retention, 8),
        "source_churn_at_k": round(1.0 - source_retention, 8),
        "source_jaccard_at_k": round(source_jaccard, 8),
        "top1_source_same": bool(
            left_sources and right_sources and left_sources[0] == right_sources[0]
        ),
        "left_sources_only": [list(key) for key in left_sources if key not in right_source_set],
        "right_sources_only": [list(key) for key in right_sources if key not in left_source_set],
    }


def compare_profiles(
    store: CatalogStore,
    settings: Settings,
    query: str,
    *,
    left_profile_id: str,
    right_profile_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Run two frozen profiles against one unchanged catalog snapshot."""

    left_profile = get_retrieval_profile(left_profile_id)
    right_profile = get_retrieval_profile(right_profile_id)
    snapshot_before = catalog_snapshot_hash(store)

    left = search_rag(
        store,
        settings,
        query,
        limit=limit,
        profile_id=left_profile.profile_id,
    )
    right = search_rag(
        store,
        settings,
        query,
        limit=limit,
        profile_id=right_profile.profile_id,
    )

    snapshot_after = catalog_snapshot_hash(store)
    if snapshot_before != snapshot_after:
        raise RuntimeError(
            "Catalog snapshot changed during profile comparison. Repeat the comparison on a stable snapshot."
        )

    left_data = list(left.get("data") or [])
    right_data = list(right.get("data") or [])
    return {
        "query": query,
        "catalog_snapshot_hash": snapshot_before,
        "left_profile": left_profile.public_dict(),
        "right_profile": right_profile.public_dict(),
        "drift": compare_ranked_evidence(left_data, right_data, limit=limit),
        "left": left,
        "right": right,
    }


def replay_retrieval_run(
    store: CatalogStore,
    settings: Settings,
    run_id: int,
) -> dict[str, Any]:
    """Strictly re-execute a recorded run when its profile and data snapshot still match.

    Historical evidence is already preserved in ``rag_retrieval_runs.result``. This
    function tests computational replay. It refuses to call a changed catalog state
    an exact replay because that would mix data drift with retrieval drift.
    """

    run = get_retrieval_run(store, run_id)
    if run is None:
        raise KeyError(run_id)

    profile_id = str(run.get("profile_id") or "")
    if not profile_id:
        raise RuntimeError("Legacy retrieval runs without a frozen profile cannot be strictly replayed.")

    profile = get_retrieval_profile(profile_id)
    recorded_profile_hash = str(run.get("profile_hash") or "")
    if recorded_profile_hash != profile.config_hash:
        raise RuntimeError(
            "Retrieval profile hash no longer matches the recorded run. Exact replay is blocked."
        )

    recorded_snapshot = str(run.get("catalog_snapshot_hash") or "")
    current_snapshot = catalog_snapshot_hash(store)
    if recorded_snapshot != current_snapshot:
        raise RuntimeError(
            "Catalog snapshot has changed since this run. Exact computational replay is blocked; "
            "the stored historical evidence remains available from the run record."
        )

    stored_result = run.get("result") if isinstance(run.get("result"), dict) else {}
    top_k = max(1, int(run.get("top_k") or 10))
    replay = search_rag(
        store,
        settings,
        str(run.get("query_text") or ""),
        limit=top_k,
        profile_id=profile_id,
    )

    stored_data = list(stored_result.get("data") or [])
    replay_data = list(replay.get("data") or [])
    drift = compare_ranked_evidence(stored_data, replay_data, limit=top_k)

    return {
        "source_run_id": int(run_id),
        "query": str(run.get("query_text") or ""),
        "profile_id": profile_id,
        "profile_hash": profile.config_hash,
        "catalog_snapshot_hash": current_snapshot,
        "exact_evidence_reproduced": bool(drift["ordered_evidence_same"]),
        "drift": drift,
        "stored_result": stored_result,
        "replayed_result": replay,
    }
