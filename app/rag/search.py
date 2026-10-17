from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.embeddings import EmbeddingError, get_embedding_provider, reciprocal_rank_fusion
from app.rag.profiles import RetrievalProfile, get_retrieval_profile, settings_for_profile
from app.rag.retrieval import diversify_ranked_results
from app.rag.store import RagStore


def search_rag(
    store: CatalogStore,
    settings: Settings,
    query: str,
    *,
    limit: int = 10,
    mode: str = "hybrid",
    profile_id: str | None = None,
) -> dict[str, object]:
    """Search current RAG chunks with a runtime mode or immutable retrieval profile.

    ``profile_id`` freezes the retrieval configuration used for the run. The older
    ``mode`` argument remains supported for scripts and backward-compatible API calls.
    """

    profile: RetrievalProfile | None = None
    active_settings = settings
    if profile_id is not None:
        profile = get_retrieval_profile(profile_id)
        mode = profile.mode
        active_settings = settings_for_profile(settings, profile)

    if mode not in {"lexical", "vector", "hybrid"}:
        raise ValueError(f"Unsupported retrieval mode {mode!r}.")

    rag_store = RagStore(store)
    final_limit = max(1, int(limit))
    candidate_limit = min(100, max(20, final_limit * 5))
    diversity_cap = max(1, int(active_settings.rag_source_diversity_max_per_file))
    diversity = {
        "strategy": "source-file-soft-cap-v1",
        "max_per_source": diversity_cap,
    }
    profile_payload = None if profile is None else profile.public_dict()

    if mode == "lexical":
        candidates = rag_store.search_chunks(query, limit=candidate_limit)
        results = diversify_ranked_results(
            candidates,
            limit=final_limit,
            max_per_source=diversity_cap,
        )
        return {
            "query": query,
            "retrieval": "lexical-baseline-v1-current-only",
            "mode": mode,
            "profile": profile_payload,
            "diversity": diversity,
            "count": len(results),
            "data": [{"rank": rank, **item} for rank, item in enumerate(results, start=1)],
        }

    try:
        provider = get_embedding_provider(active_settings)
        query_vector = provider.embed_query(query)
        vector_candidates = rag_store.vector_search(
            query_vector,
            model=provider.name,
            limit=candidate_limit,
        )
    except (EmbeddingError, RuntimeError, SQLAlchemyError) as exc:
        if mode == "vector":
            raise RuntimeError(f"Vector retrieval unavailable: {exc}") from exc
        lexical_candidates = rag_store.search_chunks(query, limit=candidate_limit)
        lexical = diversify_ranked_results(
            lexical_candidates,
            limit=final_limit,
            max_per_source=diversity_cap,
        )
        return {
            "query": query,
            "retrieval": "lexical-fallback-vector-unavailable",
            "mode": mode,
            "profile": profile_payload,
            "warning": str(exc),
            "diversity": diversity,
            "count": len(lexical),
            "data": [{"rank": rank, **item} for rank, item in enumerate(lexical, start=1)],
        }

    if mode == "vector":
        diversified = diversify_ranked_results(
            vector_candidates,
            limit=final_limit,
            max_per_source=diversity_cap,
        )
        results: list[dict[str, object]] = []
        original_rank = {
            (
                str(item["dataset_identifier"]),
                int(item["dataset_version"]),
                int(item["chunk_index"]),
            ): rank
            for rank, item in enumerate(vector_candidates, start=1)
        }
        for item in diversified:
            record = dict(item)
            key = (
                str(record["dataset_identifier"]),
                int(record["dataset_version"]),
                int(record["chunk_index"]),
            )
            record["score"] = record.get("vector_similarity")
            record["vector_rank"] = original_rank[key]
            record["lexical_rank"] = None
            results.append(record)
        return {
            "query": query,
            "retrieval": f"pgvector-cosine-exact:{provider.name}",
            "mode": mode,
            "profile": profile_payload,
            "embedding_model": provider.name,
            "diversity": diversity,
            "count": len(results),
            "data": [{"rank": rank, **item} for rank, item in enumerate(results, start=1)],
        }

    lexical_candidates = rag_store.search_chunks(query, limit=candidate_limit)
    if not vector_candidates:
        lexical = diversify_ranked_results(
            lexical_candidates,
            limit=final_limit,
            max_per_source=diversity_cap,
        )
        return {
            "query": query,
            "retrieval": "lexical-fallback-no-current-vectors",
            "mode": mode,
            "profile": profile_payload,
            "embedding_model": provider.name,
            "diversity": diversity,
            "count": len(lexical),
            "data": [{"rank": rank, **item} for rank, item in enumerate(lexical, start=1)],
        }

    fused_candidates = reciprocal_rank_fusion(
        lexical_candidates,
        vector_candidates,
        limit=candidate_limit,
        k=max(1, int(active_settings.rag_hybrid_rrf_k)),
    )
    fused = diversify_ranked_results(
        fused_candidates,
        limit=final_limit,
        max_per_source=diversity_cap,
    )
    return {
        "query": query,
        "retrieval": f"hybrid-rrf-v1:lexical+pgvector:{provider.name}",
        "mode": mode,
        "profile": profile_payload,
        "embedding_model": provider.name,
        "diversity": diversity,
        "count": len(fused),
        "data": [{"rank": rank, **item} for rank, item in enumerate(fused, start=1)],
    }
