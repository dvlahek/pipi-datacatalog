from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.catalog.store import CatalogStore
from app.config import Settings


DEFAULT_RETRIEVAL_PROFILE_ID = "hybrid-e5-content-v1"


@dataclass(frozen=True, slots=True)
class RetrievalProfile:
    profile_id: str
    version: int
    label: str
    mode: str
    description: str
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_revision: str | None = None
    embedding_dimensions: int | None = None
    embedding_input_profile: str | None = None
    rrf_k: int | None = None
    diversity_max_per_file: int = 2
    reranker: str | None = None

    def config(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "mode": self.mode,
            "embedding": None
            if self.embedding_provider is None
            else {
                "provider": self.embedding_provider,
                "model": self.embedding_model,
                "revision": self.embedding_revision,
                "dimensions": self.embedding_dimensions,
                "input_profile": self.embedding_input_profile,
            },
            "fusion": None
            if self.mode != "hybrid"
            else {"algorithm": "rrf-v1", "k": self.rrf_k},
            "diversity": {
                "algorithm": "source-file-soft-cap-v1",
                "max_per_file": self.diversity_max_per_file,
            },
            "reranker": self.reranker,
        }

    @property
    def config_hash(self) -> str:
        payload = json.dumps(
            self.config(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def public_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "label": self.label,
            "mode": self.mode,
            "description": self.description,
            "config_hash": self.config_hash,
            "config": self.config(),
            "is_default": self.profile_id == DEFAULT_RETRIEVAL_PROFILE_ID,
        }


_BUILTIN_PROFILES = (
    RetrievalProfile(
        profile_id="lexical-v1",
        version=1,
        label="Lexical baseline · v1",
        mode="lexical",
        description="Deterministic lexical baseline over current non-stale chunks.",
        diversity_max_per_file=2,
    ),
    RetrievalProfile(
        profile_id="vector-e5-content-v1",
        version=1,
        label="Vector E5 · content-v1",
        mode="vector",
        description="Multilingual E5 cosine retrieval over content-only chunk embeddings.",
        embedding_provider="multilingual-e5",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimensions=384,
        embedding_input_profile="content-v1",
        diversity_max_per_file=2,
    ),
    RetrievalProfile(
        profile_id="hybrid-e5-content-v1",
        version=1,
        label="Hybrid E5 · content-v1",
        mode="hybrid",
        description="Frozen stable baseline: lexical plus multilingual E5 content embeddings with RRF.",
        embedding_provider="multilingual-e5",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimensions=384,
        embedding_input_profile="content-v1",
        rrf_k=60,
        diversity_max_per_file=2,
    ),
    RetrievalProfile(
        profile_id="vector-e5-metadata-v1",
        version=1,
        label="Vector E5 · metadata-v1",
        mode="vector",
        description="Multilingual E5 cosine retrieval with dataset title and source file path context.",
        embedding_provider="multilingual-e5",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimensions=384,
        embedding_input_profile="metadata-v1",
        diversity_max_per_file=2,
    ),
    RetrievalProfile(
        profile_id="hybrid-e5-metadata-v1",
        version=1,
        label="Hybrid E5 · metadata-v1",
        mode="hybrid",
        description="Experimental metadata-aware E5 profile fused with lexical retrieval using RRF.",
        embedding_provider="multilingual-e5",
        embedding_model="intfloat/multilingual-e5-small",
        embedding_dimensions=384,
        embedding_input_profile="metadata-v1",
        rrf_k=60,
        diversity_max_per_file=2,
    ),
)

_BUILTIN_BY_ID = {profile.profile_id: profile for profile in _BUILTIN_PROFILES}


def builtin_retrieval_profiles() -> list[RetrievalProfile]:
    return list(_BUILTIN_PROFILES)


def get_retrieval_profile(profile_id: str) -> RetrievalProfile:
    profile = _BUILTIN_BY_ID.get(profile_id)
    if profile is None:
        raise KeyError(profile_id)
    return profile


def settings_for_profile(settings: Settings, profile: RetrievalProfile) -> Settings:
    updates: dict[str, Any] = {
        "rag_source_diversity_max_per_file": profile.diversity_max_per_file,
    }
    if profile.embedding_provider is not None:
        updates.update(
            {
                "rag_embedding_provider": profile.embedding_provider,
                "rag_embedding_model": profile.embedding_model,
                "rag_embedding_revision": profile.embedding_revision,
                "rag_embedding_dimensions": profile.embedding_dimensions,
                "rag_embedding_input_profile": profile.embedding_input_profile,
            }
        )
    if profile.rrf_k is not None:
        updates["rag_hybrid_rrf_k"] = profile.rrf_k
    return settings.model_copy(update=updates)


def ensure_builtin_profiles(store: CatalogStore) -> list[dict[str, Any]]:
    if store.engine.dialect.name != "postgresql":
        return [profile.public_dict() for profile in _BUILTIN_PROFILES]

    select_sql = text(
        "SELECT profile_id, config_hash FROM rag_retrieval_profiles WHERE profile_id = :profile_id"
    )
    insert_sql = text(
        """
        INSERT INTO rag_retrieval_profiles (
            profile_id, profile_version, label, mode, description,
            config, config_hash, enabled
        ) VALUES (
            :profile_id, :profile_version, :label, :mode, :description,
            CAST(:config AS jsonb), :config_hash, TRUE
        )
        """
    )
    with store.engine.begin() as connection:
        for profile in _BUILTIN_PROFILES:
            existing = connection.execute(
                select_sql, {"profile_id": profile.profile_id}
            ).mappings().first()
            if existing is not None:
                if str(existing["config_hash"]) != profile.config_hash:
                    raise RuntimeError(
                        f"Retrieval profile {profile.profile_id!r} already exists with a different "
                        "configuration hash. Create a new versioned profile instead of rewriting it."
                    )
                continue
            connection.execute(
                insert_sql,
                {
                    "profile_id": profile.profile_id,
                    "profile_version": profile.version,
                    "label": profile.label,
                    "mode": profile.mode,
                    "description": profile.description,
                    "config": json.dumps(profile.config(), ensure_ascii=False, sort_keys=True),
                    "config_hash": profile.config_hash,
                },
            )
    return [profile.public_dict() for profile in _BUILTIN_PROFILES]


def catalog_snapshot_hash(store: CatalogStore) -> str:
    if store.engine.dialect.name != "postgresql":
        payload = []
        for dataset in store.list_datasets():
            payload.append((dataset.identifier, dataset.model_dump(mode="json")))
    else:
        statement = text(
            """
            SELECT DISTINCT ON (dataset_identifier)
                dataset_identifier, version, fingerprint
            FROM catalog_dataset_versions
            ORDER BY dataset_identifier, version DESC
            """
        )
        with store.engine.begin() as connection:
            rows = connection.execute(statement).mappings().all()
        payload = [
            (str(row["dataset_identifier"]), int(row["version"]), str(row["fingerprint"]))
            for row in rows
        ]

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def record_retrieval_run(
    store: CatalogStore,
    *,
    query: str,
    profile: RetrievalProfile | None,
    retrieval: str,
    top_k: int,
    result: dict[str, Any],
) -> int | None:
    if store.engine.dialect.name != "postgresql":
        return None
    statement = text(
        """
        INSERT INTO rag_retrieval_runs (
            query_text, profile_id, profile_hash, catalog_snapshot_hash,
            retrieval, top_k, result
        ) VALUES (
            :query_text, :profile_id, :profile_hash, :catalog_snapshot_hash,
            :retrieval, :top_k, CAST(:result AS jsonb)
        )
        RETURNING id
        """
    )
    with store.engine.begin() as connection:
        run_id = connection.execute(
            statement,
            {
                "query_text": query,
                "profile_id": None if profile is None else profile.profile_id,
                "profile_hash": None if profile is None else profile.config_hash,
                "catalog_snapshot_hash": catalog_snapshot_hash(store),
                "retrieval": retrieval,
                "top_k": int(top_k),
                "result": json.dumps(result, ensure_ascii=False, default=str),
            },
        ).scalar_one()
    return int(run_id)


def list_retrieval_runs(store: CatalogStore, *, limit: int = 30) -> list[dict[str, Any]]:
    if store.engine.dialect.name != "postgresql":
        return []
    statement = text(
        """
        SELECT id, query_text, profile_id, profile_hash, catalog_snapshot_hash,
               retrieval, top_k, result, created_at
        FROM rag_retrieval_runs
        ORDER BY id DESC
        LIMIT :limit
        """
    )
    with store.engine.begin() as connection:
        rows = connection.execute(statement, {"limit": max(1, int(limit))}).mappings().all()
    return [dict(row) for row in rows]


def get_retrieval_run(store: CatalogStore, run_id: int) -> dict[str, Any] | None:
    if store.engine.dialect.name != "postgresql":
        return None
    statement = text(
        """
        SELECT id, query_text, profile_id, profile_hash, catalog_snapshot_hash,
               retrieval, top_k, result, created_at
        FROM rag_retrieval_runs
        WHERE id = :run_id
        """
    )
    with store.engine.begin() as connection:
        row = connection.execute(statement, {"run_id": int(run_id)}).mappings().first()
    return None if row is None else dict(row)
