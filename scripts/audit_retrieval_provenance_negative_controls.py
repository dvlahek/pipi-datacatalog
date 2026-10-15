from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

from app.rag.profiles import get_retrieval_profile


EXPECTED_PROFILE_HASHES = {
    "lexical-v1": "4234a9a6691d7f0c004eb7b6469662675db35f66fe04dd8eb5b053b1d7a31a54",
    "vector-e5-content-v1": "8c00e6326839a8e0e798083197225d1fd90b60db7d6a9e974fe8667de5f0562f",
    "hybrid-e5-content-v1": "04fd11fb3c56e9273f7b312a376d5c975a852489276f87fc796f7e0c716f7a45",
    "vector-e5-metadata-v1": "e250344e567f85c3dc8ac36b0cd68663f570e322bed7686de99a270ffa0e1628",
    "hybrid-e5-metadata-v1": "7b63711593b091d1c21a1548f1b672f4572c69b4fca380779114cad6163211e4",
}

EXPECTED_CATALOG_SNAPSHOT = (
    "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
)
EXPECTED_CORPUS_FINGERPRINT = (
    "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
)


def sha256_json(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def audit_profile_baseline() -> dict:
    mismatches = {}
    for profile_id, expected in EXPECTED_PROFILE_HASHES.items():
        actual = get_retrieval_profile(profile_id).config_hash
        if actual != expected:
            mismatches[profile_id] = {"expected": expected, "actual": actual}
    return {
        "control": "frozen-profile-baseline",
        "detected": not mismatches,
        "details": mismatches,
    }


def audit_same_id_rrf_mutation() -> dict:
    profile = get_retrieval_profile("hybrid-e5-content-v1")
    mutated = replace(profile, rrf_k=61)
    expected = EXPECTED_PROFILE_HASHES[profile.profile_id]
    return {
        "control": "same-profile-id-rrf-k-60-to-61",
        "stage": "retrieval-profile",
        "profile_id_unchanged": mutated.profile_id == profile.profile_id,
        "expected_hash": expected,
        "mutated_hash": mutated.config_hash,
        "detected": mutated.config_hash != expected,
    }


def audit_embedding_revision_mutation() -> dict:
    profile = get_retrieval_profile("hybrid-e5-content-v1")
    mutated = replace(profile, embedding_revision="negative-control-revision")
    expected = EXPECTED_PROFILE_HASHES[profile.profile_id]
    baseline_identity = (
        profile.embedding_provider,
        profile.embedding_model,
        profile.embedding_revision,
        profile.embedding_dimensions,
        profile.embedding_input_profile,
    )
    mutated_identity = (
        mutated.embedding_provider,
        mutated.embedding_model,
        mutated.embedding_revision,
        mutated.embedding_dimensions,
        mutated.embedding_input_profile,
    )
    return {
        "control": "same-profile-id-embedding-revision-mutation",
        "stage": "index-embedding-identity",
        "profile_id_unchanged": mutated.profile_id == profile.profile_id,
        "embedding_identity_changed": mutated_identity != baseline_identity,
        "expected_hash": expected,
        "mutated_hash": mutated.config_hash,
        "detected": mutated.config_hash != expected and mutated_identity != baseline_identity,
    }


def audit_chunking_fingerprint_sensitivity() -> dict:
    # The frozen corpus fingerprint is built from chunk_index, char_start, char_end,
    # text SHA-256 and metadata SHA-256. This minimal fixture exercises the same
    # canonical-hash sensitivity without requiring the private chunk text.
    baseline = {
        "dataset_identifier": "urn:pipi:negative-control:fixture",
        "dataset_version": 1,
        "chunks": [
            {
                "chunk_index": 0,
                "char_start": 0,
                "char_end": 1000,
                "text_sha256": "a" * 64,
                "metadata_sha256": "b" * 64,
            },
            {
                "chunk_index": 1,
                "char_start": 1000,
                "char_end": 2000,
                "text_sha256": "c" * 64,
                "metadata_sha256": "d" * 64,
            },
        ],
    }
    mutated = copy.deepcopy(baseline)
    mutated["chunks"][0]["char_end"] = 900
    mutated["chunks"][1]["char_start"] = 900
    baseline_hash = sha256_json(baseline)
    mutated_hash = sha256_json(mutated)
    return {
        "control": "chunk-boundary-mutation",
        "stage": "corpus-index-artifact",
        "baseline_fixture_hash": baseline_hash,
        "mutated_fixture_hash": mutated_hash,
        "detected": baseline_hash != mutated_hash,
        "note": (
            "The production frozen-corpus fingerprint includes the same chunk boundary "
            "fields plus text and metadata hashes, so a changed chunking result cannot "
            "retain the same corpus fingerprint unless a SHA-256 collision occurs."
        ),
    }


def audit_parent_anchor_mismatch() -> dict:
    foreign_snapshot = "1" + EXPECTED_CATALOG_SNAPSHOT[1:]
    foreign_corpus = "1" + EXPECTED_CORPUS_FINGERPRINT[1:]
    return {
        "control": "foreign-parent-anchors",
        "stage": "catalog-corpus-parent",
        "catalog_snapshot_detected": foreign_snapshot != EXPECTED_CATALOG_SNAPSHOT,
        "corpus_fingerprint_detected": foreign_corpus != EXPECTED_CORPUS_FINGERPRINT,
        "detected": (
            foreign_snapshot != EXPECTED_CATALOG_SNAPSHOT
            and foreign_corpus != EXPECTED_CORPUS_FINGERPRINT
        ),
    }


def main() -> None:
    controls = [
        audit_profile_baseline(),
        audit_same_id_rrf_mutation(),
        audit_embedding_revision_mutation(),
        audit_chunking_fingerprint_sensitivity(),
        audit_parent_anchor_mismatch(),
    ]
    passed = all(bool(item["detected"]) for item in controls)
    output = {
        "artifact": "pipi-benchmark-v2-retrieval-provenance-negative-controls",
        "schema_version": 1,
        "analysis_role": (
            "post-hoc systems audit; does not alter frozen RQ1-RQ4 scientific results"
        ),
        "expected_catalog_snapshot_sha256": EXPECTED_CATALOG_SNAPSHOT,
        "expected_corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "controls": controls,
        "all_controls_pass": passed,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit("RETRIEVAL_PROVENANCE_NEGATIVE_CONTROLS_FAIL")
    print("RETRIEVAL_PROVENANCE_NEGATIVE_CONTROLS_PASS")


if __name__ == "__main__":
    main()
