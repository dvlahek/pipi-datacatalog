from app.rag import embeddings
from app.rag.embeddings import (
    FeatureHashEmbeddingProvider,
    MultilingualE5EmbeddingProvider,
    reciprocal_rank_fusion,
)


def test_feature_hash_embeddings_are_deterministic_and_normalized() -> None:
    provider = FeatureHashEmbeddingProvider(name="test", dimensions=32)
    first, second = provider.embed_texts(["temperature demo-site-b", "temperature demo-site-b"])

    assert first == second
    assert len(first) == 32
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_feature_hash_keeps_related_token_signal() -> None:
    provider = FeatureHashEmbeddingProvider(name="test", dimensions=128)
    query, related, unrelated = provider.embed_texts(
        [
            "temperature demo-site-b",
            "demo-site-b temperature value",
            "faculty council document",
        ]
    )

    def dot(left, right):
        return sum(a * b for a, b in zip(left, right))

    assert dot(query, related) > dot(query, unrelated)


def test_multilingual_e5_uses_query_and_passage_prefixes(monkeypatch) -> None:
    calls: list[list[str]] = []

    class FakeModel:
        def encode(self, values, **_kwargs):
            calls.append(list(values))
            return [[1.0, 0.0, 0.0] for _ in values]

    monkeypatch.setattr(
        embeddings,
        "_load_sentence_transformer",
        lambda _model_id, _revision, _device: FakeModel(),
    )

    provider = MultilingualE5EmbeddingProvider(
        name="test-e5",
        dimensions=3,
        model_id="example/e5",
    )

    query = provider.embed_query("temperatura u Varaždinu")
    passages = provider.embed_documents(["temperatura senzora", "odluka fakulteta"])

    assert query == [1.0, 0.0, 0.0]
    assert passages == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert calls[0] == ["query: temperatura u Varaždinu"]
    assert calls[1] == ["passage: temperatura senzora", "passage: odluka fakulteta"]


def test_reciprocal_rank_fusion_combines_both_rankings() -> None:
    a = {
        "dataset_identifier": "urn:test:a",
        "dataset_version": 1,
        "chunk_index": 0,
        "text": "alpha",
    }
    b = {
        "dataset_identifier": "urn:test:b",
        "dataset_version": 1,
        "chunk_index": 0,
        "text": "beta",
        "vector_similarity": 0.9,
    }

    fused = reciprocal_rank_fusion([a, b], [b, a], limit=2, k=60)

    assert len(fused) == 2
    assert {item["dataset_identifier"] for item in fused} == {"urn:test:a", "urn:test:b"}
    assert all(item["lexical_rank"] is not None for item in fused)
    assert all(item["vector_rank"] is not None for item in fused)
