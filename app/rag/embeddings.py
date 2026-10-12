from __future__ import annotations

import hashlib
import importlib.util
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Iterable

from app.catalog.store import CatalogStore
from app.config import Settings
from app.rag.store import RagStore


class EmbeddingError(RuntimeError):
    pass


_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class EmbeddingProvider:
    name: str
    dimensions: int

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return self.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


@dataclass(frozen=True, slots=True)
class FeatureHashEmbeddingProvider(EmbeddingProvider):
    """Dependency-free vector baseline used to validate pgvector plumbing.

    This is intentionally not presented as a semantic language model. It maps
    unicode tokens and adjacent token pairs into a deterministic dense vector,
    which gives us a reproducible local vector baseline before a multilingual
    neural embedding provider is configured.
    """

    def _features(self, text: str) -> list[tuple[str, float]]:
        tokens = [match.group(0).casefold() for match in _TOKEN_RE.finditer(text)]
        features: list[tuple[str, float]] = [(token, 1.0) for token in tokens]
        features.extend(
            (f"{left}\u241f{right}", 0.65)
            for left, right in zip(tokens, tokens[1:])
        )
        return features

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature, weight in self._features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big", signed=False)
            index = value % self.dimensions
            sign = -1.0 if (value >> 63) else 1.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


@lru_cache(maxsize=4)
def _load_sentence_transformer(
    model_id: str,
    revision: str | None,
    device: str,
) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "Neural embeddings require the optional sentence-transformers dependency. "
            "Install it with: python -m pip install -r requirements-embeddings.txt"
        ) from exc

    kwargs: dict[str, Any] = {}
    if revision:
        kwargs["revision"] = revision
    if device.strip().lower() not in {"", "auto"}:
        kwargs["device"] = device

    try:
        return SentenceTransformer(model_id, **kwargs)
    except Exception as exc:
        raise EmbeddingError(f"Could not load embedding model {model_id!r}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class MultilingualE5EmbeddingProvider(EmbeddingProvider):
    """Multilingual neural retrieval using a Sentence Transformers E5 model.

    E5 models are trained with asymmetric retrieval prefixes. Catalog chunks are
    encoded as passages and user searches as queries. Vectors are normalized so
    pgvector cosine distance is directly usable for ranking.
    """

    model_id: str
    revision: str | None = None
    device: str = "auto"

    def _encode(self, texts: Iterable[str], *, prefix: str) -> list[list[float]]:
        values = [f"{prefix}: {text}" for text in texts]
        if not values:
            return []

        model = _load_sentence_transformer(self.model_id, self.revision, self.device)
        try:
            encoded = model.encode(
                values,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError(f"Embedding with {self.model_id!r} failed: {exc}") from exc

        rows = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
        if rows and isinstance(rows[0], (int, float)):
            rows = [rows]

        vectors: list[list[float]] = []
        for row in rows:
            vector = [float(value) for value in row]
            if len(vector) != self.dimensions:
                raise EmbeddingError(
                    f"Embedding model {self.model_id!r} returned {len(vector)} dimensions; "
                    f"configured RAG_EMBEDDING_DIMENSIONS={self.dimensions}."
                )
            vectors.append(vector)
        return vectors

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return self._encode(texts, prefix="passage")

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], prefix="query")[0]


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.rag_embedding_provider.strip().lower()
    if provider == "feature-hash":
        return FeatureHashEmbeddingProvider(
            name=settings.rag_embedding_model,
            dimensions=settings.rag_embedding_dimensions,
        )
    if provider in {"multilingual-e5", "sentence-transformers-e5", "e5"}:
        if importlib.util.find_spec("sentence_transformers") is None:
            raise EmbeddingError(
                "RAG_EMBEDDING_PROVIDER is configured for multilingual E5, but "
                "sentence-transformers is not installed. Run: "
                "python -m pip install -r requirements-embeddings.txt"
            )
        revision = settings.rag_embedding_revision or None
        identity = settings.rag_embedding_model
        if revision:
            identity = f"{identity}@{revision}"
        return MultilingualE5EmbeddingProvider(
            name=identity,
            dimensions=settings.rag_embedding_dimensions,
            model_id=settings.rag_embedding_model,
            revision=revision,
            device=settings.rag_embedding_device,
        )
    raise EmbeddingError(
        f"Unsupported RAG embedding provider {settings.rag_embedding_provider!r}."
    )


def embed_dataset_chunks(
    store: CatalogStore,
    settings: Settings,
    dataset_identifier: str,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, object]:
    provider = get_embedding_provider(settings)
    rag_store = RagStore(store)
    rows = rag_store.list_current_chunks_for_embedding(
        provider.name,
        dataset_identifier=dataset_identifier,
    )
    total = len(rows)
    embedded = 0
    batch_size = max(1, int(settings.rag_embedding_batch_size))

    for start in range(0, total, batch_size):
        batch = rows[start : start + batch_size]
        vectors = provider.embed_documents(item["text"] for item in batch)
        rag_store.write_chunk_embeddings(
            [
                {
                    "chunk_id": int(item["chunk_id"]),
                    "vector": vector,
                }
                for item, vector in zip(batch, vectors)
            ],
            model=provider.name,
            dimensions=provider.dimensions,
        )
        embedded += len(batch)
        if progress:
            progress(embedded, total)

    return {
        "provider": settings.rag_embedding_provider,
        "model": provider.name,
        "dimensions": provider.dimensions,
        "eligible": total,
        "embedded": embedded,
    }


def backfill_current_embeddings(
    store: CatalogStore,
    settings: Settings,
    *,
    limit: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, object]:
    provider = get_embedding_provider(settings)
    rag_store = RagStore(store)
    effective_limit = (
        max(1, int(limit))
        if limit is not None
        else max(1, int(settings.rag_embedding_backfill_limit))
    )

    current_identifiers = sorted(
        str(item["dataset_identifier"])
        for item in rag_store.list_index_statuses()
        if item.get("status") == "indexed" and item.get("dataset_identifier")
    )
    rows: list[dict[str, object]] = []
    for dataset_identifier in current_identifiers:
        remaining = effective_limit - len(rows)
        if remaining <= 0:
            break
        rows.extend(
            rag_store.list_current_chunks_for_embedding(
                provider.name,
                dataset_identifier=dataset_identifier,
                limit=remaining,
            )
        )

    total = len(rows)
    embedded = 0
    batch_size = max(1, int(settings.rag_embedding_batch_size))

    for start in range(0, total, batch_size):
        batch = rows[start : start + batch_size]
        vectors = provider.embed_documents(item["text"] for item in batch)
        rag_store.write_chunk_embeddings(
            [
                {
                    "chunk_id": int(item["chunk_id"]),
                    "vector": vector,
                }
                for item, vector in zip(batch, vectors)
            ],
            model=provider.name,
            dimensions=provider.dimensions,
        )
        embedded += len(batch)
        if progress:
            progress(embedded, total)

    status = rag_store.embedding_status(provider.name)
    return {
        "provider": settings.rag_embedding_provider,
        "model": provider.name,
        "dimensions": provider.dimensions,
        "attempted": total,
        "embedded": embedded,
        "status": status,
    }


def reciprocal_rank_fusion(
    lexical: list[dict[str, object]],
    vector: list[dict[str, object]],
    *,
    limit: int,
    k: int = 60,
) -> list[dict[str, object]]:
    """Fuse lexical and vector rankings without assuming comparable score scales."""

    fused: dict[tuple[str, int, int], dict[str, object]] = {}

    def key(item: dict[str, object]) -> tuple[str, int, int]:
        return (
            str(item["dataset_identifier"]),
            int(item["dataset_version"]),
            int(item["chunk_index"]),
        )

    for rank, item in enumerate(lexical, start=1):
        record = dict(item)
        record["lexical_rank"] = rank
        record["vector_rank"] = None
        record["vector_similarity"] = None
        record["score"] = 1.0 / (k + rank)
        fused[key(item)] = record

    for rank, item in enumerate(vector, start=1):
        item_key = key(item)
        record = fused.get(item_key)
        if record is None:
            record = dict(item)
            record["lexical_rank"] = None
            record["score"] = 0.0
            fused[item_key] = record
        record["vector_rank"] = rank
        record["vector_similarity"] = item.get("vector_similarity")
        record["score"] = float(record.get("score") or 0.0) + 1.0 / (k + rank)

    ranked = sorted(
        fused.values(),
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("dataset_identifier") or ""),
            int(item.get("chunk_index") or 0),
        ),
    )[:limit]
    for item in ranked:
        item["score"] = round(float(item["score"]), 8)
    return ranked
