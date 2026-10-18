from __future__ import annotations

import argparse
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
from app.rag.drift import evidence_key, replay_retrieval_run
from app.rag.profiles import catalog_snapshot_hash

EXPECTED_SNAPSHOT = "068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419"
EXPECTED_CORPUS_FINGERPRINT = "f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6"
EXPECTED_CONFIRMATION_SHA256 = "c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5"
EXPECTED_LEDGER_FILE_SHA256 = "335555045685798fc27f781b39092d1b1b9f17af8c53dd16d0e2f757db18a1c0"
EXPECTED_RUNS = 960
EXPECTED_CASES = 192
PROFILE_IDS = (
    "lexical-v1",
    "vector-e5-content-v1",
    "hybrid-e5-content-v1",
    "vector-e5-metadata-v1",
    "hybrid-e5-metadata-v1",
)
DEFAULT_LEDGER = ROOT / "results" / "benchmark_v2_confirmation_retrieval_ledger_c725fba20382.json"
DEFAULT_OUTPUT = ROOT / "results" / "benchmark_v2_confirmation_strict_replay_c725fba20382.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ordered_ledger_keys(results: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    ordered = sorted(results, key=lambda item: int(item.get("rank") or 0))
    return [
        (
            str(item.get("dataset_identifier") or ""),
            int(item.get("dataset_version") or 0),
            int(item.get("chunk_index") or 0),
        )
        for item in ordered
    ]


def _ordered_result_keys(results: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    return [evidence_key(item) for item in results]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strictly replay all 960 frozen Benchmark V2 confirmation retrieval runs."
    )
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Diagnostic smoke limit only. A limited run can never emit CONFIRMATION_STRICT_REPLAY_PASS.",
    )
    args = parser.parse_args()

    if not args.ledger.is_file():
        raise SystemExit(f"Frozen confirmation ledger not found: {args.ledger}")

    ledger_sha = _sha256_file(args.ledger)
    if ledger_sha != EXPECTED_LEDGER_FILE_SHA256:
        raise SystemExit(
            "CONFIRMATION_REPLAY_REFUSED_LEDGER_HASH_MISMATCH\n"
            f"expected={EXPECTED_LEDGER_FILE_SHA256}\nactual={ledger_sha}"
        )

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    if ledger.get("artifact") != "pipi-benchmark-v2-confirmation-retrieval-ledger":
        raise SystemExit("Unexpected confirmation retrieval ledger artifact type.")
    if ledger.get("catalog_snapshot_hash") != EXPECTED_SNAPSHOT:
        raise SystemExit("Frozen ledger catalog snapshot mismatch.")
    if ledger.get("corpus_fingerprint_sha256") != EXPECTED_CORPUS_FINGERPRINT:
        raise SystemExit("Frozen ledger corpus fingerprint mismatch.")
    if ledger.get("confirmation_cases_sha256") != EXPECTED_CONFIRMATION_SHA256:
        raise SystemExit("Frozen ledger confirmation query-set hash mismatch.")

    runs = list(ledger.get("runs") or [])
    if len(runs) != EXPECTED_RUNS:
        raise SystemExit(f"Expected {EXPECTED_RUNS} frozen runs, found {len(runs)}.")

    keys = [(str(row.get("case_id") or ""), str(row.get("profile_id") or "")) for row in runs]
    if len(set(keys)) != EXPECTED_RUNS:
        raise SystemExit("Duplicate case/profile run found in frozen confirmation ledger.")
    if len({case_id for case_id, _ in keys}) != EXPECTED_CASES:
        raise SystemExit("Frozen ledger does not contain exactly 192 confirmation cases.")
    if {profile_id for _, profile_id in keys} != set(PROFILE_IDS):
        raise SystemExit("Frozen ledger profile set does not match the five frozen profiles.")
    if any(row.get("db_run_id") is None for row in runs):
        raise SystemExit("At least one frozen confirmation run lacks db_run_id; strict replay cannot proceed.")

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    current_snapshot = catalog_snapshot_hash(store)
    if current_snapshot != EXPECTED_SNAPSHOT:
        raise SystemExit(
            "CONFIRMATION_REPLAY_REFUSED_SNAPSHOT_MISMATCH\n"
            f"expected={EXPECTED_SNAPSHOT}\nactual={current_snapshot}"
        )

    selected = runs
    limited = args.max_runs is not None
    if limited:
        if args.max_runs is None or args.max_runs < 1:
            raise SystemExit("--max-runs must be >= 1")
        selected = runs[: args.max_runs]

    run_reports: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    print("PiPi Benchmark V2 full confirmation strict replay")
    print(f"LEDGER_SHA256={ledger_sha}")
    print(f"CATALOG_SNAPSHOT={current_snapshot}")
    print(f"RUNS_SELECTED={len(selected)}/{EXPECTED_RUNS}")

    for index, row in enumerate(selected, start=1):
        case_id = str(row.get("case_id") or "")
        profile_id = str(row.get("profile_id") or "")
        profile_hash = str(row.get("profile_hash") or "")
        run_id = int(row["db_run_id"])
        report: dict[str, Any] = {
            "case_id": case_id,
            "profile_id": profile_id,
            "profile_hash": profile_hash,
            "db_run_id": run_id,
        }
        try:
            replay = replay_retrieval_run(store, settings, run_id)
            stored_result = replay.get("stored_result") if isinstance(replay.get("stored_result"), dict) else {}
            stored_data = list(stored_result.get("data") or [])
            ledger_keys = _ordered_ledger_keys(list(row.get("results") or []))
            stored_keys = _ordered_result_keys(stored_data)

            profile_identity_ok = replay.get("profile_id") == profile_id
            profile_hash_ok = replay.get("profile_hash") == profile_hash
            ledger_identity_ok = stored_keys == ledger_keys
            exact_replay_ok = bool(replay.get("exact_evidence_reproduced"))
            passed = profile_identity_ok and profile_hash_ok and ledger_identity_ok and exact_replay_ok

            report.update(
                {
                    "profile_identity_ok": profile_identity_ok,
                    "profile_hash_ok": profile_hash_ok,
                    "ledger_stored_evidence_identity_ok": ledger_identity_ok,
                    "exact_ordered_evidence_reproduced": exact_replay_ok,
                    "stored_evidence_count": len(stored_keys),
                    "replayed_evidence_count": int(replay.get("drift", {}).get("right_count") or 0),
                    "stored_evidence_hash": replay.get("drift", {}).get("left_evidence_hash"),
                    "replayed_evidence_hash": replay.get("drift", {}).get("right_evidence_hash"),
                    "passed": passed,
                }
            )
            if not passed:
                failures.append(dict(report))
        except Exception as exc:  # fail closed and preserve the diagnostic
            report.update({"passed": False, "error": f"{type(exc).__name__}: {exc}"})
            failures.append(dict(report))
        run_reports.append(report)

        if index == 1 or index % 25 == 0 or index == len(selected):
            print(f"PROGRESS={index}/{len(selected)} FAILURES={len(failures)}")

    full_run = not limited and len(selected) == EXPECTED_RUNS
    passed_all = full_run and not failures and all(bool(row.get("passed")) for row in run_reports)
    output = {
        "artifact": "pipi-benchmark-v2-confirmation-strict-replay",
        "schema_version": 1,
        "status": "pass" if passed_all else ("diagnostic-limited" if limited else "fail"),
        "catalog_snapshot_hash": current_snapshot,
        "corpus_fingerprint_sha256": EXPECTED_CORPUS_FINGERPRINT,
        "confirmation_cases_sha256": EXPECTED_CONFIRMATION_SHA256,
        "retrieval_ledger_sha256": ledger_sha,
        "expected_run_count": EXPECTED_RUNS,
        "evaluated_run_count": len(selected),
        "failure_count": len(failures),
        "exact_replay_count": sum(bool(row.get("exact_ordered_evidence_reproduced")) for row in run_reports),
        "all_exact_replay": passed_all,
        "failures": failures,
        "runs": run_reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_sha = _sha256_file(args.output)

    print(f"OUTPUT={args.output}")
    print(f"OUTPUT_SHA256={output_sha}")
    if limited:
        print("CONFIRMATION_STRICT_REPLAY_DIAGNOSTIC_ONLY")
        return
    if not passed_all:
        raise SystemExit(f"CONFIRMATION_STRICT_REPLAY_FAIL failures={len(failures)}")
    print("CONFIRMATION_STRICT_REPLAY_PASS")


if __name__ == "__main__":
    main()
