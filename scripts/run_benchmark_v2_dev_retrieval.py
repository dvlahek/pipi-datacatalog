from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import (
    builtin_retrieval_profiles,
    catalog_snapshot_hash,
    record_retrieval_run,
)
from app.rag.search import search_rag

EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
EXPECTED_CORPUS_FINGERPRINT = "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
EXPECTED_PROTOCOL_SHA256 = "d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde"
EXPECTED_DEV_SHA256 = "c60d2f6083873bb76591ffdd10d19cfe32f4900c20a4117ca39ecc3d2c40b4e9"
DEFAULT_CASES = ROOT / "results" / f"benchmark_v2_dev_queries_frozen_{EXPECTED_DEV_SHA256[:12]}.json"
PROFILE_IDS = (
    "lexical-v1",
    "vector-e5-content-v1",
    "hybrid-e5-content-v1",
    "vector-e5-metadata-v1",
    "hybrid-e5-metadata-v1",
)
POOL_DEPTH = 20


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_result(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "rank": int(item.get("rank") or 0),
        "dataset_identifier": str(item.get("dataset_identifier") or ""),
        "dataset_version": int(item.get("dataset_version") or 0),
        "chunk_index": int(item.get("chunk_index") or 0),
        "file_path": str(metadata.get("file_path") or "") or None,
        "text_sha256": _sha256_text(str(item.get("text") or "")),
        "score": item.get("score"),
        "lexical_rank": item.get("lexical_rank"),
        "vector_rank": item.get("vector_rank"),
    }


def _pool_key(item: dict[str, Any]) -> tuple[str, int, int]:
    return (
        str(item.get("dataset_identifier") or ""),
        int(item.get("dataset_version") or 0),
        int(item.get("chunk_index") or 0),
    )


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the five frozen retrieval profiles on the frozen 48-query Benchmark V2 "
            "development set and construct a pooled annotation artifact."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    snapshot_before = catalog_snapshot_hash(store)
    if snapshot_before != EXPECTED_SNAPSHOT:
        raise SystemExit(
            "DEV_RETRIEVAL_REFUSED_SNAPSHOT_MISMATCH\n"
            f"expected={EXPECTED_SNAPSHOT}\nactual={snapshot_before}"
        )

    if not args.cases.is_file():
        raise SystemExit(f"Frozen development query set not found: {args.cases}")
    query_set = json.loads(args.cases.read_text(encoding="utf-8"))
    if query_set.get("catalog_snapshot_hash") != EXPECTED_SNAPSHOT:
        raise SystemExit("Frozen development query set snapshot mismatch.")
    if query_set.get("corpus_fingerprint_sha256") != EXPECTED_CORPUS_FINGERPRINT:
        raise SystemExit("Frozen development query set corpus fingerprint mismatch.")
    if query_set.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit("Frozen development query set protocol hash mismatch.")
    if query_set.get("development_cases_sha256") != EXPECTED_DEV_SHA256:
        raise SystemExit("Frozen development query set content hash mismatch.")

    cases = list(query_set.get("cases") or [])
    if len(cases) != 48:
        raise SystemExit(f"Expected 48 development cases, found {len(cases)}.")

    profiles = {profile.profile_id: profile for profile in builtin_retrieval_profiles()}
    if any(profile_id not in profiles for profile_id in PROFILE_IDS):
        raise SystemExit("One or more preregistered retrieval profiles are unavailable.")

    run_rows: list[dict[str, Any]] = []
    pools: dict[str, dict[tuple[str, int, int], dict[str, Any]]] = defaultdict(dict)
    total_searches = len(cases) * len(PROFILE_IDS)
    completed = 0

    print("PiPi Benchmark V2 development retrieval")
    print(f"CATALOG_SNAPSHOT_BEFORE={snapshot_before}")
    print(f"DEV_QUERY_SET_SHA256={EXPECTED_DEV_SHA256}")
    print(f"CASES={len(cases)} PROFILES={len(PROFILE_IDS)} SEARCHES={total_searches}")
    print(f"POOL_DEPTH={POOL_DEPTH}")
    print()

    for profile_id in PROFILE_IDS:
        profile = profiles[profile_id]
        print(f"PROFILE={profile_id} HASH={profile.config_hash}")
        for case in cases:
            case_id = str(case["case_id"])
            query = str(case["query_text"])
            payload = search_rag(
                store,
                settings,
                query,
                limit=POOL_DEPTH,
                profile_id=profile_id,
            )

            retrieval = str(payload.get("retrieval") or "")
            warning = payload.get("warning")
            if warning:
                raise SystemExit(
                    f"DEV_RETRIEVAL_REFUSED_WARNING case={case_id} profile={profile_id} warning={warning}"
                )
            if "fallback" in retrieval.casefold():
                raise SystemExit(
                    f"DEV_RETRIEVAL_REFUSED_FALLBACK case={case_id} profile={profile_id} retrieval={retrieval}"
                )

            returned_profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
            if returned_profile.get("profile_id") != profile_id:
                raise SystemExit(f"Profile identity mismatch for {case_id} / {profile_id}.")
            if returned_profile.get("config_hash") != profile.config_hash:
                raise SystemExit(f"Profile hash mismatch for {case_id} / {profile_id}.")

            results = list(payload.get("data") or [])
            run_id = record_retrieval_run(
                store,
                query=query,
                profile=profile,
                retrieval=retrieval,
                top_k=POOL_DEPTH,
                result=payload,
            )

            safe_results = [_safe_result(dict(item)) for item in results]
            run_rows.append(
                {
                    "case_id": case_id,
                    "profile_id": profile_id,
                    "profile_hash": profile.config_hash,
                    "retrieval": retrieval,
                    "db_run_id": run_id,
                    "result_count": len(results),
                    "results": safe_results,
                }
            )

            case_pool = pools[case_id]
            for item in results:
                record = dict(item)
                key = _pool_key(record)
                metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
                existing = case_pool.get(key)
                if existing is None:
                    existing = {
                        "dataset_identifier": key[0],
                        "dataset_version": key[1],
                        "chunk_index": key[2],
                        "source_url": record.get("source_url"),
                        "media_type": record.get("media_type"),
                        "file_path": str(metadata.get("file_path") or "") or None,
                        "text": str(record.get("text") or ""),
                        "metadata": metadata,
                        "retrieved_by": {},
                        "judgment": None,
                        "judgment_notes": None,
                    }
                    case_pool[key] = existing
                existing["retrieved_by"][profile_id] = {
                    "rank": int(record.get("rank") or 0),
                    "score": _jsonable(record.get("score")),
                    "lexical_rank": _jsonable(record.get("lexical_rank")),
                    "vector_rank": _jsonable(record.get("vector_rank")),
                }

            completed += 1
            if completed == 1 or completed % 20 == 0 or completed == total_searches:
                print(f"PROGRESS={completed}/{total_searches}")

    snapshot_after = catalog_snapshot_hash(store)
    if snapshot_after != snapshot_before:
        raise SystemExit(
            "DEV_RETRIEVAL_REFUSED_SNAPSHOT_CHANGED_DURING_RUN\n"
            f"before={snapshot_before}\nafter={snapshot_after}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    run_artifact = {
        "artifact": "pipi-benchmark-v2-development-retrieval-ledger",
        "schema_version": 1,
        "catalog_snapshot_hash": snapshot_before,
        "corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "development_cases_sha256": EXPECTED_DEV_SHA256,
        "pool_depth_per_profile": POOL_DEPTH,
        "profiles": [profiles[profile_id].public_dict() for profile_id in PROFILE_IDS],
        "publication_safe": True,
        "contains_chunk_text": False,
        "runs": run_rows,
    }

    pool_cases: list[dict[str, Any]] = []
    unique_candidate_total = 0
    for case in cases:
        case_id = str(case["case_id"])
        candidates = list(pools[case_id].values())
        candidates.sort(
            key=lambda candidate: (
                min(
                    int(details.get("rank") or 10**9)
                    for details in candidate["retrieved_by"].values()
                ),
                candidate["dataset_identifier"],
                candidate["dataset_version"],
                candidate["chunk_index"],
            )
        )
        unique_candidate_total += len(candidates)
        pool_cases.append(
            {
                "case_id": case_id,
                "source_family": case.get("source_family"),
                "query_type": case.get("query_type"),
                "language_relation": case.get("language_relation"),
                "query_text": case.get("query_text"),
                "query_language": case.get("query_language"),
                "target_evidence_language": case.get("target_evidence_language"),
                "target_dataset_identifiers": case.get("target_dataset_identifiers"),
                "target_file_paths": case.get("target_file_paths"),
                "target_chunk_hints": case.get("target_chunk_hints"),
                "candidates": candidates,
            }
        )

    pool_artifact = {
        "artifact": "pipi-benchmark-v2-development-annotation-pool",
        "schema_version": 1,
        "catalog_snapshot_hash": snapshot_before,
        "corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "development_cases_sha256": EXPECTED_DEV_SHA256,
        "pool_depth_per_profile": POOL_DEPTH,
        "profile_ids": list(PROFILE_IDS),
        "publication_safe": False,
        "contains_chunk_text": True,
        "note": (
            "Local annotation aid. Contains pooled source text and retrieval-rank provenance. "
            "Do not commit this artifact before publication/privacy review."
        ),
        "relevance_scale": {
            "3": "directly answers the information need",
            "2": "clearly relevant supporting evidence but incomplete on its own",
            "1": "topically related but insufficient or weak evidence",
            "0": "irrelevant",
        },
        "cases": pool_cases,
    }

    ledger_path = args.output_dir / f"benchmark_v2_dev_retrieval_ledger_{EXPECTED_DEV_SHA256[:12]}.json"
    pool_path = args.output_dir / f"benchmark_v2_dev_annotation_pool_{EXPECTED_DEV_SHA256[:12]}.json"
    ledger_path.write_text(json.dumps(run_artifact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    pool_path.write_text(json.dumps(pool_artifact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    print()
    print(f"CATALOG_SNAPSHOT_AFTER={snapshot_after}")
    print(f"RETRIEVAL_RUNS={len(run_rows)}")
    print(f"UNIQUE_POOLED_CANDIDATES={unique_candidate_total}")
    print(f"DEV_RETRIEVAL_LEDGER={ledger_path}")
    print(f"DEV_ANNOTATION_POOL={pool_path}")
    print("QUALITY_METRICS_NOT_COMPUTED=NO_GRADED_JUDGMENTS_YET")
    print("BENCHMARK_V2_DEV_RETRIEVAL_POOL_READY")


if __name__ == "__main__":
    main()
