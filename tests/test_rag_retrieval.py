from app.rag.retrieval import lexical_score, rank_chunk_candidates


def test_lexical_score_rewards_full_term_coverage() -> None:
    relevant = (
        "Row 3. record_id: 3 | site: demo-site-b | metric: temperature | "
        "value: 18.7 | unit: C"
    )
    partial = "Row 2. site: demo-site-a | metric: temperature | value: 20.1"

    assert lexical_score("temperature demo-site-b", relevant) == 1.0
    assert lexical_score("temperature demo-site-b", partial) == 0.5


def test_rank_chunk_candidates_returns_source_aware_best_match() -> None:
    candidates = [
        {
            "dataset_identifier": "urn:pipi:dataset:resource:1",
            "dataset_version": 1,
            "source_url": "https://example.org/demo.csv",
            "media_type": "text/csv",
            "chunk_index": 0,
            "text": "site demo-site-a metric temperature value 20.1",
            "metadata": {},
        },
        {
            "dataset_identifier": "urn:pipi:dataset:resource:2",
            "dataset_version": 3,
            "source_url": "https://example.org/other.csv",
            "media_type": "text/csv",
            "chunk_index": 4,
            "text": "site demo-site-b metric temperature value 18.7",
            "metadata": {},
        },
    ]

    results = rank_chunk_candidates("temperature demo-site-b", candidates, limit=5)

    assert len(results) == 2
    assert results[0]["dataset_identifier"] == "urn:pipi:dataset:resource:2"
    assert results[0]["dataset_version"] == 3
    assert results[0]["source_url"] == "https://example.org/other.csv"
    assert results[0]["score"] == 1.0
    assert results[1]["score"] == 0.5
