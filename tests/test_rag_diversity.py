from app.rag.retrieval import diversify_ranked_results


def _item(rank: int, file_path: str | None) -> dict[str, object]:
    metadata = {} if file_path is None else {"file_path": file_path, "structure": "github-file"}
    return {
        "dataset_identifier": "urn:test:repo",
        "dataset_version": 1,
        "chunk_index": rank,
        "score": 1.0 / rank,
        "metadata": metadata,
    }


def test_diversity_prefers_different_github_files() -> None:
    ranked = [
        _item(1, "docs/a.md"),
        _item(2, "docs/a.md"),
        _item(3, "docs/a.md"),
        _item(4, "docs/b.md"),
        _item(5, "docs/c.md"),
    ]

    result = diversify_ranked_results(ranked, limit=4, max_per_source=2)

    assert [item["chunk_index"] for item in result] == [1, 2, 4, 5]


def test_diversity_soft_cap_backfills_when_only_one_source_exists() -> None:
    ranked = [_item(index, "docs/a.md") for index in range(1, 6)]

    result = diversify_ranked_results(ranked, limit=4, max_per_source=2)

    assert [item["chunk_index"] for item in result] == [1, 2, 3, 4]


def test_diversity_does_not_suppress_sources_without_file_boundary() -> None:
    ranked = [_item(index, None) for index in range(1, 5)]

    result = diversify_ranked_results(ranked, limit=4, max_per_source=2)

    assert [item["chunk_index"] for item in result] == [1, 2, 3, 4]
