from __future__ import annotations

import argparse
import copy
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
from app.rag.profiles import catalog_snapshot_hash
from app.rag.store import RagStore

EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
EXPECTED_CORPUS_FINGERPRINT = "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
EXPECTED_PROTOCOL_SHA256 = "d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde"
EXPECTED_DEV_SHA256 = "c60d2f6083873bb76591ffdd10d19cfe32f4900c20a4117ca39ecc3d2c40b4e9"

DEFAULT_FROZEN_QUERIES = ROOT / "results" / f"benchmark_v2_dev_queries_frozen_{EXPECTED_DEV_SHA256[:12]}.json"
DEFAULT_POOL = ROOT / "results" / f"benchmark_v2_dev_annotation_pool_{EXPECTED_DEV_SHA256[:12]}.json"
AMENDMENT_PATH = ROOT / "docs" / "retrieval_benchmark_v2_amendment_2.md"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pool_key(item: dict[str, Any]) -> tuple[str, int, int]:
    return (
        str(item.get("dataset_identifier") or ""),
        int(item.get("dataset_version") or 0),
        int(item.get("chunk_index") or 0),
    )


def _seed_specs(case: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_ids = [str(value) for value in case.get("target_dataset_identifiers") or []]
    file_paths = [str(value) for value in case.get("target_file_paths") or []]
    chunk_hints = [int(value) for value in case.get("target_chunk_hints") or []]

    if not dataset_ids:
        raise ValueError(f"{case.get('case_id')}: no target_dataset_identifiers")
    if not chunk_hints:
        raise ValueError(f"{case.get('case_id')}: no target_chunk_hints; exact seed resolution is ambiguous")

    specs: list[dict[str, Any]] = []
    if file_paths:
        if len(dataset_ids) != 1:
            raise ValueError(
                f"{case.get('case_id')}: software/file-path seed resolution expects exactly one dataset identifier"
            )
        dataset_id = dataset_ids[0]
        if len(file_paths) == 1:
            for chunk_index in chunk_hints:
                specs.append(
                    {
                        "dataset_identifier": dataset_id,
                        "file_path": file_paths[0],
                        "chunk_index": chunk_index,
                    }
                )
        elif len(file_paths) == len(chunk_hints):
            for file_path, chunk_index in zip(file_paths, chunk_hints):
                specs.append(
                    {
                        "dataset_identifier": dataset_id,
                        "file_path": file_path,
                        "chunk_index": chunk_index,
                    }
                )
        else:
            raise ValueError(
                f"{case.get('case_id')}: ambiguous file-path/chunk-hint mapping "
                f"({len(file_paths)} paths, {len(chunk_hints)} hints)"
            )
        return specs

    for dataset_id in dataset_ids:
        for chunk_index in chunk_hints:
            specs.append(
                {
                    "dataset_identifier": dataset_id,
                    "file_path": None,
                    "chunk_index": chunk_index,
                }
            )
    return specs


def _resolve_seed(rag: RagStore, spec: dict[str, Any]) -> dict[str, Any]:
    dataset_identifier = str(spec["dataset_identifier"])
    target_file_path = spec.get("file_path")
    target_chunk_index = int(spec["chunk_index"])

    status = rag.index_status(dataset_identifier)
    if status.get("status") != "indexed":
        raise RuntimeError(
            f"Seed dataset is not current/indexed: {dataset_identifier} status={status.get('status')}"
        )
    version = int(status.get("indexed_version") or 0)
    document = dict(status.get("document") or {})
    chunks = rag.list_chunks(dataset_identifier, dataset_version=version, limit=100000)

    matches: list[dict[str, Any]] = []
    for chunk in chunks:
        if int(chunk.get("chunk_index") or 0) != target_chunk_index:
            continue
        metadata = dict(chunk.get("metadata") or {})
        file_path = str(metadata.get("file_path") or "") or None
        if target_file_path is not None and file_path != str(target_file_path):
            continue
        matches.append(dict(chunk))

    if len(matches) != 1:
        raise RuntimeError(
            "Authoring seed did not resolve uniquely: "
            f"dataset={dataset_identifier} version={version} file_path={target_file_path!r} "
            f"chunk_index={target_chunk_index} matches={len(matches)}"
        )

    chunk = matches[0]
    metadata = dict(chunk.get("metadata") or {})
    file_path = str(metadata.get("file_path") or "") or None
    return {
        "dataset_identifier": dataset_identifier,
        "dataset_version": version,
        "chunk_index": target_chunk_index,
        "source_url": document.get("source_url"),
        "media_type": document.get("media_type"),
        "file_path": file_path,
        "text": str(chunk.get("text") or ""),
        "metadata": metadata,
        "retrieved_by": {},
        "authoring_seed": True,
        "authoring_seed_specs": [
            {
                "dataset_identifier": dataset_identifier,
                "file_path": target_file_path,
                "chunk_index": target_chunk_index,
            }
        ],
        "judgment": None,
        "judgment_notes": None,
    }


def _validate_identity(payload: dict[str, Any], label: str) -> None:
    if payload.get("catalog_snapshot_hash") != EXPECTED_SNAPSHOT:
        raise SystemExit(f"{label} snapshot mismatch.")
    if payload.get("corpus_fingerprint_sha256") != EXPECTED_CORPUS_FINGERPRINT:
        raise SystemExit(f"{label} corpus fingerprint mismatch.")
    if payload.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit(f"{label} protocol hash mismatch.")
    if payload.get("development_cases_sha256") != EXPECTED_DEV_SHA256:
        raise SystemExit(f"{label} development-set hash mismatch.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply Benchmark V2 Protocol Amendment 2 by adding frozen retrieval-blind authoring "
            "evidence seeds to the local development annotation pool without changing retrieval ranks."
        )
    )
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--queries", type=Path, default=DEFAULT_FROZEN_QUERIES)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    if not args.pool.is_file():
        raise SystemExit(f"Development annotation pool not found: {args.pool}")
    if not args.queries.is_file():
        raise SystemExit(f"Frozen development query set not found: {args.queries}")
    if not AMENDMENT_PATH.is_file():
        raise SystemExit(f"Protocol Amendment 2 not found: {AMENDMENT_PATH}")

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    snapshot_before = catalog_snapshot_hash(store)
    if snapshot_before != EXPECTED_SNAPSHOT:
        raise SystemExit(
            "SEED_AUGMENTATION_REFUSED_SNAPSHOT_MISMATCH\n"
            f"expected={EXPECTED_SNAPSHOT}\nactual={snapshot_before}"
        )

    pool_bytes = args.pool.read_bytes()
    pool = json.loads(pool_bytes)
    query_set = json.loads(args.queries.read_text(encoding="utf-8"))
    _validate_identity(pool, "Annotation pool")
    _validate_identity(query_set, "Frozen query set")

    if len(query_set.get("cases") or []) != 48:
        raise SystemExit("Expected exactly 48 frozen development queries.")
    if len(pool.get("cases") or []) != 48:
        raise SystemExit("Expected exactly 48 development pool cases.")

    judged = [
        (case.get("case_id"), candidate)
        for case in pool.get("cases") or []
        for candidate in case.get("candidates") or []
        if candidate.get("judgment") is not None
    ]
    if judged:
        raise SystemExit(
            "SEED_AUGMENTATION_REFUSED_EXISTING_JUDGMENTS: Amendment 2 must be applied before grading."
        )

    cases_by_id = {str(case["case_id"]): case for case in query_set["cases"]}
    pool_by_id = {str(case["case_id"]): case for case in pool["cases"]}
    if set(cases_by_id) != set(pool_by_id):
        raise SystemExit("Frozen query IDs and annotation-pool query IDs do not match.")

    rag = RagStore(store)
    augmented = copy.deepcopy(pool)
    augmented_by_id = {str(case["case_id"]): case for case in augmented["cases"]}

    resolved_seed_specs = 0
    unique_seed_candidates: set[tuple[str, int, int]] = set()
    already_present = 0
    added = 0
    cases_with_added_seeds: list[str] = []

    for case_id in sorted(cases_by_id):
        frozen_case = cases_by_id[case_id]
        pool_case = augmented_by_id[case_id]
        candidates = list(pool_case.get("candidates") or [])
        by_key = {_pool_key(candidate): candidate for candidate in candidates}
        case_added = 0

        for spec in _seed_specs(frozen_case):
            resolved_seed_specs += 1
            seed = _resolve_seed(rag, spec)
            key = _pool_key(seed)
            unique_seed_candidates.add(key)
            existing = by_key.get(key)
            provenance = seed["authoring_seed_specs"][0]

            if existing is not None:
                already_present += 1
                existing["authoring_seed"] = True
                seed_specs = list(existing.get("authoring_seed_specs") or [])
                if provenance not in seed_specs:
                    seed_specs.append(provenance)
                existing["authoring_seed_specs"] = seed_specs
                continue

            candidates.append(seed)
            by_key[key] = seed
            added += 1
            case_added += 1

        if case_added:
            cases_with_added_seeds.append(case_id)
        pool_case["candidates"] = candidates

    # Strict validation: every deterministic authoring seed must now be represented in the pool.
    missing_after: list[str] = []
    for case_id in sorted(cases_by_id):
        frozen_case = cases_by_id[case_id]
        pool_case = augmented_by_id[case_id]
        keys = {_pool_key(candidate) for candidate in pool_case.get("candidates") or []}
        for spec in _seed_specs(frozen_case):
            seed = _resolve_seed(rag, spec)
            if _pool_key(seed) not in keys:
                missing_after.append(
                    f"{case_id}:{spec['dataset_identifier']}:{spec.get('file_path')}:{spec['chunk_index']}"
                )
    if missing_after:
        raise SystemExit("SEED_AUGMENTATION_VALIDATION_FAILED\n" + "\n".join(missing_after))

    snapshot_after = catalog_snapshot_hash(store)
    if snapshot_after != snapshot_before:
        raise SystemExit(
            "SEED_AUGMENTATION_REFUSED_SNAPSHOT_CHANGED_DURING_RUN\n"
            f"before={snapshot_before}\nafter={snapshot_after}"
        )

    amendment_bytes = AMENDMENT_PATH.read_bytes()
    amendment_sha256 = _sha256_bytes(amendment_bytes)
    input_pool_sha256 = _sha256_bytes(pool_bytes)
    total_candidates_before = sum(len(case.get("candidates") or []) for case in pool["cases"])
    total_candidates_after = sum(len(case.get("candidates") or []) for case in augmented["cases"])

    augmented["artifact"] = "pipi-benchmark-v2-development-annotation-pool-augmented-a2"
    augmented["schema_version"] = 2
    augmented["protocol_amendments"] = [
        {
            "id": "A2",
            "path": "docs/retrieval_benchmark_v2_amendment_2.md",
            "sha256": amendment_sha256,
            "rule": "top-20 profile union plus frozen retrieval-blind authoring evidence seeds",
        }
    ]
    augmented["augmentation"] = {
        "input_pool_sha256": input_pool_sha256,
        "resolved_seed_specs": resolved_seed_specs,
        "unique_seed_candidates": len(unique_seed_candidates),
        "already_present_in_retrieval_pool": already_present,
        "added_seed_candidates": added,
        "cases_with_added_seed_candidates": cases_with_added_seeds,
        "candidate_count_before": total_candidates_before,
        "candidate_count_after": total_candidates_after,
        "automatic_relevance_grades_assigned": 0,
        "retrieval_ranks_modified": False,
    }
    augmented["note"] = (
        "Local annotation aid augmented under Protocol Amendment 2. Authoring seeds are provenance, "
        "not automatic relevance labels. Retrieval ranks are unchanged. Contains source text; do not "
        "commit before publication/privacy review."
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"benchmark_v2_dev_annotation_pool_a2_{EXPECTED_DEV_SHA256[:12]}.json"
    output_path.write_text(
        json.dumps(augmented, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print("PiPi Benchmark V2 development annotation-pool augmentation")
    print(f"CATALOG_SNAPSHOT={snapshot_after}")
    print(f"DEV_QUERY_SET_SHA256={EXPECTED_DEV_SHA256}")
    print(f"BASE_PROTOCOL_SHA256={EXPECTED_PROTOCOL_SHA256}")
    print(f"AMENDMENT_2_SHA256={amendment_sha256}")
    print(f"INPUT_POOL_SHA256={input_pool_sha256}")
    print(f"CANDIDATES_BEFORE={total_candidates_before}")
    print(f"RESOLVED_SEED_SPECS={resolved_seed_specs}")
    print(f"UNIQUE_SEED_CANDIDATES={len(unique_seed_candidates)}")
    print(f"SEEDS_ALREADY_PRESENT={already_present}")
    print(f"SEED_CANDIDATES_ADDED={added}")
    print(f"CASES_WITH_ADDED_SEEDS={len(cases_with_added_seeds)}")
    for case_id in cases_with_added_seeds:
        print(f"  ADDED_FOR={case_id}")
    print(f"CANDIDATES_AFTER={total_candidates_after}")
    print("AUTOMATIC_RELEVANCE_GRADES_ASSIGNED=0")
    print("RETRIEVAL_RANKS_MODIFIED=NO")
    print(f"AUGMENTED_ANNOTATION_POOL={output_path}")
    print("AUTHORING_SEED_COVERAGE=PASS")
    print("BENCHMARK_V2_DEV_ANNOTATION_POOL_A2_READY")


if __name__ == "__main__":
    main()
