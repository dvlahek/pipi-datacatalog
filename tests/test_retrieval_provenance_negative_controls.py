from scripts.audit_retrieval_provenance_negative_controls import (
    audit_chunking_fingerprint_sensitivity,
    audit_embedding_revision_mutation,
    audit_parent_anchor_mismatch,
    audit_profile_baseline,
    audit_same_id_rrf_mutation,
)


def test_frozen_profile_hashes_match_confirmation_anchors() -> None:
    assert audit_profile_baseline()["detected"] is True


def test_same_profile_id_rrf_mutation_is_detected() -> None:
    result = audit_same_id_rrf_mutation()
    assert result["profile_id_unchanged"] is True
    assert result["detected"] is True


def test_embedding_revision_mutation_is_detected() -> None:
    result = audit_embedding_revision_mutation()
    assert result["profile_id_unchanged"] is True
    assert result["embedding_identity_changed"] is True
    assert result["detected"] is True


def test_chunk_boundary_mutation_changes_index_fingerprint() -> None:
    assert audit_chunking_fingerprint_sensitivity()["detected"] is True


def test_foreign_parent_anchors_are_detected() -> None:
    result = audit_parent_anchor_mismatch()
    assert result["catalog_snapshot_detected"] is True
    assert result["corpus_fingerprint_detected"] is True
    assert result["detected"] is True
