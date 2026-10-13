import pytest

from app.rag.drift import compare_ranked_evidence, evidence_key, ordered_evidence_hash


def _item(dataset: str, version: int, chunk: int) -> dict[str, object]:
    return {
        "dataset_identifier": dataset,
        "dataset_version": version,
        "chunk_index": chunk,
    }


def test_evidence_key_uses_versioned_chunk_identity() -> None:
    assert evidence_key(_item("dataset-a", 3, 7)) == ("dataset-a", 3, 7)


def test_identical_rankings_have_zero_drift() -> None:
    results = [_item("a", 1, 0), _item("b", 2, 4), _item("c", 1, 2)]

    metrics = compare_ranked_evidence(results, results, limit=3)

    assert metrics["shared_count"] == 3
    assert metrics["retention_at_k"] == 1.0
    assert metrics["churn_at_k"] == 0.0
    assert metrics["jaccard_at_k"] == 1.0
    assert metrics["top1_same"] is True
    assert metrics["ordered_evidence_same"] is True
    assert metrics["mean_abs_rank_shift_common"] == 0.0
    assert metrics["left_evidence_hash"] == metrics["right_evidence_hash"]


def test_profile_change_can_preserve_set_but_change_ranking() -> None:
    left = [_item("a", 1, 0), _item("b", 1, 0), _item("c", 1, 0)]
    right = [_item("b", 1, 0), _item("a", 1, 0), _item("c", 1, 0)]

    metrics = compare_ranked_evidence(left, right, limit=3)

    assert metrics["retention_at_k"] == 1.0
    assert metrics["jaccard_at_k"] == 1.0
    assert metrics["top1_same"] is False
    assert metrics["ordered_evidence_same"] is False
    assert metrics["mean_abs_rank_shift_common"] == pytest.approx(2 / 3, abs=1e-7)
    assert metrics["max_abs_rank_shift_common"] == 1
    assert ordered_evidence_hash(left) != ordered_evidence_hash(right)


def test_disjoint_rankings_have_full_churn() -> None:
    left = [_item("a", 1, 0), _item("b", 1, 0)]
    right = [_item("c", 1, 0), _item("d", 1, 0)]

    metrics = compare_ranked_evidence(left, right, limit=2)

    assert metrics["shared_count"] == 0
    assert metrics["retention_at_k"] == 0.0
    assert metrics["churn_at_k"] == 1.0
    assert metrics["jaccard_at_k"] == 0.0
    assert metrics["mean_abs_rank_shift_common"] is None
    assert len(metrics["left_only"]) == 2
    assert len(metrics["right_only"]) == 2
