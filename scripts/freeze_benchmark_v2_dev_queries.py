from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import catalog_snapshot_hash

EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
EXPECTED_CORPUS_FINGERPRINT = "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
EXPECTED_PROTOCOL_SHA256 = "d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde"
EXPECTED_DEV_SHA256 = "c60d2f6083873bb76591ffdd10d19cfe32f4900c20a4117ca39ecc3d2c40b4e9"
DEFAULT_INPUT = ROOT / "results" / "benchmark_v2_dev48_audited_068e1b0df74a.json"

CANONICAL_FIELDS = (
    "case_id",
    "split",
    "source_family",
    "query_type",
    "cell_position",
    "language_relation",
    "information_need",
    "query_text",
    "query_language",
    "target_evidence_language",
    "target_dataset_identifiers",
    "target_file_paths",
    "target_chunk_hints",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _development_sha256(cases: list[dict[str, Any]]) -> str:
    payload = [{key: case.get(key) for key in CANONICAL_FIELDS} for case in cases]
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and freeze the human-audited 48-query Benchmark V2 development set."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    snapshot = catalog_snapshot_hash(store)
    if snapshot != EXPECTED_SNAPSHOT:
        raise SystemExit(
            "DEV_QUERY_FREEZE_REFUSED_SNAPSHOT_MISMATCH\n"
            f"expected={EXPECTED_SNAPSHOT}\nactual={snapshot}"
        )

    protocol_path = ROOT / "config" / "rag_benchmark_v2_protocol.json"
    protocol_sha256 = _sha256_bytes(protocol_path.read_bytes())
    if protocol_sha256 != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit(
            "DEV_QUERY_FREEZE_REFUSED_PROTOCOL_MISMATCH\n"
            f"expected={EXPECTED_PROTOCOL_SHA256}\nactual={protocol_sha256}"
        )

    if not args.input.is_file():
        raise SystemExit(
            f"Audited development authoring file not found: {args.input}\n"
            "Place benchmark_v2_dev48_audited_068e1b0df74a.json in results/ or pass --input."
        )

    source = json.loads(args.input.read_text(encoding="utf-8"))
    if source.get("catalog_snapshot_hash") != EXPECTED_SNAPSHOT:
        raise SystemExit("Audited file catalog snapshot does not match the frozen V2 snapshot.")
    if source.get("corpus_fingerprint_sha256") != EXPECTED_CORPUS_FINGERPRINT:
        raise SystemExit("Audited file corpus fingerprint does not match the frozen V2 corpus.")
    if source.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit("Audited file protocol hash does not match the frozen V2 protocol.")

    all_cases = list(source.get("cases") or [])
    dev = [dict(case) for case in all_cases if case.get("split") == "development"]
    confirmation = [dict(case) for case in all_cases if case.get("split") == "confirmation"]

    if len(dev) != 48:
        raise SystemExit(f"Expected 48 development cases, found {len(dev)}.")
    if len(confirmation) != 192:
        raise SystemExit(f"Expected 192 untouched confirmation slots, found {len(confirmation)}.")
    if any(case.get("authoring_status") != "authored" for case in dev):
        raise SystemExit("All 48 development cases must have authoring_status=authored.")
    if any(case.get("query_text") in {None, ""} for case in dev):
        raise SystemExit("All 48 development cases must contain query_text.")
    if any(case.get("authoring_status") != "empty" or case.get("query_text") is not None for case in confirmation):
        raise SystemExit("Confirmation slots are no longer untouched; freeze refused.")

    case_ids = [str(case.get("case_id") or "") for case in dev]
    if len(set(case_ids)) != 48 or any(not value for value in case_ids):
        raise SystemExit("Development case IDs must be 48 unique non-empty values.")

    family_counts = Counter(str(case.get("source_family") or "") for case in dev)
    type_counts = Counter(str(case.get("query_type") or "") for case in dev)
    cell_counts = Counter(
        (str(case.get("source_family") or ""), str(case.get("query_type") or ""))
        for case in dev
    )
    relation_counts = Counter(str(case.get("language_relation") or "") for case in dev)

    if sorted(family_counts.values()) != [12, 12, 12, 12]:
        raise SystemExit(f"Unexpected source-family development balance: {dict(family_counts)}")
    if len(type_counts) != 6 or any(value != 8 for value in type_counts.values()):
        raise SystemExit(f"Unexpected query-type development balance: {dict(type_counts)}")
    if len(cell_counts) != 24 or any(value != 2 for value in cell_counts.values()):
        raise SystemExit("Every source-family x query-type cell must contain exactly 2 development cases.")
    if relation_counts != Counter({"cross-language": 24, "same-language": 24}):
        raise SystemExit(f"Unexpected language-relation balance: {dict(relation_counts)}")

    for case in dev:
        relation = str(case.get("language_relation") or "")
        query_language = str(case.get("query_language") or "")
        evidence_language = str(case.get("target_evidence_language") or "")
        if relation == "cross-language" and query_language == evidence_language:
            raise SystemExit(f"Cross-language violation: {case['case_id']}")
        if relation == "same-language" and query_language != evidence_language:
            raise SystemExit(f"Same-language violation: {case['case_id']}")
        if not list(case.get("target_dataset_identifiers") or []):
            raise SystemExit(f"Missing target dataset identity: {case['case_id']}")

    dev_sha256 = _development_sha256(dev)
    if dev_sha256 != EXPECTED_DEV_SHA256:
        raise SystemExit(
            "DEV_QUERY_FREEZE_REFUSED_CONTENT_HASH_MISMATCH\n"
            f"expected={EXPECTED_DEV_SHA256}\nactual={dev_sha256}"
        )

    frozen_cases = [
        {key: case.get(key) for key in CANONICAL_FIELDS if key != "split"}
        for case in dev
    ]
    artifact = {
        "artifact": "pipi-benchmark-v2-frozen-development-query-set",
        "schema_version": 1,
        "catalog_snapshot_hash": EXPECTED_SNAPSHOT,
        "corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "development_cases_sha256": dev_sha256,
        "case_count": 48,
        "authoring_boundary": {
            "retrieval_output_inspected_before_freeze": False,
            "human_design_audit": "PASS_WITH_8_PRE_RETRIEVAL_REVISIONS",
            "confirmation_cases_remained_untouched": True,
        },
        "source_file": args.input.name,
        "cases": frozen_cases,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"benchmark_v2_dev_queries_frozen_{dev_sha256[:12]}.json"
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"CATALOG_SNAPSHOT={snapshot}")
    print(f"CORPUS_FINGERPRINT_SHA256={EXPECTED_CORPUS_FINGERPRINT}")
    print(f"PROTOCOL_SHA256={protocol_sha256}")
    print(f"DEVELOPMENT_CASES=48")
    print(f"CONFIRMATION_UNTOUCHED=192")
    print(f"DEV_QUERY_SET_SHA256={dev_sha256}")
    print(f"FROZEN_DEV_QUERY_SET={output}")
    print("BENCHMARK_V2_DEV_QUERY_SET_FROZEN")


if __name__ == "__main__":
    main()
