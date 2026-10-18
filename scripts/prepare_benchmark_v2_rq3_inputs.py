from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import builtin_retrieval_profiles, catalog_snapshot_hash
from app.rag.search import search_rag

EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
EXPECTED_CORPUS_FINGERPRINT = "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
EXPECTED_CONFIRMATION_SHA256 = "c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5"
PROTOCOL_PATH = ROOT / "config" / "rq3_answer_drift_protocol.json"
QUERY_PATH = ROOT / "results" / f"benchmark_v2_confirmation_queries_frozen_{EXPECTED_CONFIRMATION_SHA256[:12]}.json"
OUTPUT_PATH = ROOT / "results" / f"benchmark_v2_rq3_inputs_unfrozen_{EXPECTED_CONFIRMATION_SHA256[:12]}.json"
PROFILE_IDS = ("hybrid-e5-content-v1", "hybrid-e5-metadata-v1")
TOP_K = 10


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def serialize_evidence(items: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for idx, item in enumerate(items, start=1):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        blocks.append(
            "\n".join(
                [
                    f"[E{idx}]",
                    f"dataset_identifier: {str(item.get('dataset_identifier') or '')}",
                    f"dataset_version: {int(item.get('dataset_version') or 0)}",
                    f"chunk_index: {int(item.get('chunk_index') or 0)}",
                    f"file_path: {str(metadata.get('file_path') or '')}",
                    "text:",
                    str(item.get("text") or "").strip(),
                ]
            )
        )
    return "\n\n".join(blocks).strip()


def main() -> None:
    if not PROTOCOL_PATH.is_file():
        raise SystemExit(f"Missing frozen RQ3 protocol: {PROTOCOL_PATH}")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    protocol_sha = canonical_sha(protocol)
    if protocol.get("status") != "frozen-before-any-benchmark-answer-generation":
        raise SystemExit("RQ3 protocol is not in the required frozen pre-generation state.")
    if int(protocol.get("top_k") or 0) != TOP_K:
        raise SystemExit("RQ3 protocol top_k mismatch.")

    if not QUERY_PATH.is_file():
        raise SystemExit(f"Missing frozen confirmation queries: {QUERY_PATH}")
    query_set = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
    if query_set.get("confirmation_cases_sha256") != EXPECTED_CONFIRMATION_SHA256:
        raise SystemExit("Frozen confirmation query hash mismatch.")
    if query_set.get("catalog_snapshot_hash") != EXPECTED_SNAPSHOT:
        raise SystemExit("Frozen confirmation query snapshot mismatch.")
    if query_set.get("corpus_fingerprint_sha256") != EXPECTED_CORPUS_FINGERPRINT:
        raise SystemExit("Frozen confirmation query corpus fingerprint mismatch.")

    cases = list(query_set.get("cases") or [])
    if len(cases) != 192:
        raise SystemExit(f"Expected 192 confirmation cases, found {len(cases)}.")

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")
    snapshot_before = catalog_snapshot_hash(store)
    if snapshot_before != EXPECTED_SNAPSHOT:
        raise SystemExit(
            "RQ3_INPUT_PREPARATION_REFUSED_SNAPSHOT_MISMATCH\n"
            f"expected={EXPECTED_SNAPSHOT}\nactual={snapshot_before}"
        )

    profiles = {p.profile_id: p for p in builtin_retrieval_profiles()}
    for profile_id in PROFILE_IDS:
        if profile_id not in profiles:
            raise SystemExit(f"Missing frozen retrieval profile: {profile_id}")

    prepared_cases: list[dict[str, Any]] = []
    total = len(cases) * len(PROFILE_IDS)
    done = 0
    print("PiPi Benchmark V2 RQ3 input preparation")
    print(f"RQ3_PROTOCOL_SHA256={protocol_sha}")
    print(f"CATALOG_SNAPSHOT={snapshot_before}")
    print(f"CASES={len(cases)} CONDITIONS={len(PROFILE_IDS)} SEARCHES={total}")

    for case in cases:
        case_id = str(case["case_id"])
        query = str(case["query_text"])
        conditions: dict[str, Any] = {}
        for profile_id in PROFILE_IDS:
            profile = profiles[profile_id]
            payload = search_rag(store, settings, query, limit=TOP_K, profile_id=profile_id)
            if payload.get("warning"):
                raise SystemExit(f"RQ3_INPUT_REFUSED_WARNING case={case_id} profile={profile_id}: {payload['warning']}")
            retrieval = str(payload.get("retrieval") or "")
            if "fallback" in retrieval.casefold():
                raise SystemExit(f"RQ3_INPUT_REFUSED_FALLBACK case={case_id} profile={profile_id}")
            returned_profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
            if returned_profile.get("profile_id") != profile_id:
                raise SystemExit(f"Profile identity mismatch for {case_id}/{profile_id}")
            if returned_profile.get("config_hash") != profile.config_hash:
                raise SystemExit(f"Profile hash mismatch for {case_id}/{profile_id}")

            results = list(payload.get("data") or [])
            if len(results) != TOP_K:
                raise SystemExit(f"Expected exactly {TOP_K} evidence chunks for {case_id}/{profile_id}, got {len(results)}")
            evidence_records = []
            for rank, item in enumerate(results, start=1):
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                text = str(item.get("text") or "")
                evidence_records.append(
                    {
                        "evidence_index": rank,
                        "dataset_identifier": str(item.get("dataset_identifier") or ""),
                        "dataset_version": int(item.get("dataset_version") or 0),
                        "chunk_index": int(item.get("chunk_index") or 0),
                        "file_path": str(metadata.get("file_path") or "") or None,
                        "text": text,
                        "text_sha256": sha256_bytes(text.encode("utf-8")),
                    }
                )
            serialized = serialize_evidence(results)
            conditions[profile_id] = {
                "profile_hash": profile.config_hash,
                "retrieval": retrieval,
                "top_k": TOP_K,
                "ordered_evidence_identity_sha256": canonical_sha(
                    [
                        [r["dataset_identifier"], r["dataset_version"], r["chunk_index"], r["text_sha256"]]
                        for r in evidence_records
                    ]
                ),
                "serialized_evidence_sha256": sha256_bytes(serialized.encode("utf-8")),
                "serialized_evidence": serialized,
                "evidence": evidence_records,
            }
            done += 1
            if done == 1 or done % 40 == 0 or done == total:
                print(f"PROGRESS={done}/{total}")

        prepared_cases.append(
            {
                "case_id": case_id,
                "source_family": case.get("source_family"),
                "query_type": case.get("query_type"),
                "language_relation": case.get("language_relation"),
                "double_annotation": bool(case.get("double_annotation")),
                "query_text": query,
                "query_language": case.get("query_language"),
                "conditions": conditions,
            }
        )

    snapshot_after = catalog_snapshot_hash(store)
    if snapshot_after != snapshot_before:
        raise SystemExit("RQ3_INPUT_REFUSED_SNAPSHOT_CHANGED_DURING_PREPARATION")

    artifact = {
        "artifact": "pipi-benchmark-v2-rq3-inputs",
        "schema_version": 1,
        "status": "prepared-before-generation-awaiting-freeze-manifest",
        "rq3_protocol_sha256": protocol_sha,
        "catalog_snapshot_hash": snapshot_before,
        "corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "confirmation_cases_sha256": EXPECTED_CONFIRMATION_SHA256,
        "profile_ids": list(PROFILE_IDS),
        "top_k": TOP_K,
        "case_count": len(prepared_cases),
        "condition_count": len(prepared_cases) * len(PROFILE_IDS),
        "contains_chunk_text": True,
        "publication_safe": False,
        "cases": prepared_cases,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
    OUTPUT_PATH.write_text(payload, encoding="utf-8")
    input_sha = sha256_bytes(payload.encode("utf-8"))

    print()
    print(f"RQ3_INPUT={OUTPUT_PATH}")
    print(f"RQ3_PROTOCOL_SHA256={protocol_sha}")
    print(f"RQ3_INPUT_SHA256={input_sha}")
    print("RQ3_INPUT_PREPARED_STOP_BEFORE_GENERATION")
    print("Send the protocol SHA, input SHA, and llama.cpp version for the freeze manifest. Do not run the generator yet.")


if __name__ == "__main__":
    main()
