#!/usr/bin/env python3
"""Verify publication summaries and the published replay-verification artifacts.

This script does not rerun retrieval, generation, or human/model judging. It checks
that the retained publication summaries match the manuscript headline values and
that the public frozen replay artifacts retain their recorded hashes, linkage, and
exact-replay counts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPLAY = ROOT / "replay"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(actual, expected, label: str) -> None:
    if actual != expected:
        raise SystemExit(f"FAIL {label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    main_results = load_json(ROOT / "results" / "main_results_summary.json")
    same = load_json(ROOT / "results" / "same_evidence_summary.json")

    a = main_results["corpus_design"]["corpus_a"]
    b = main_results["corpus_design"]["corpus_b"]
    require(a["selected_datasets"], 274, "corpus A datasets")
    require(a["unique_dataset_ids"], 274, "corpus A unique dataset IDs")
    require(a["chunk_occurrences"], 3974, "corpus A chunks")
    require(a["confirmation_queries"], 192, "corpus A confirmation queries")

    require(b["selection_records"], 400, "corpus B selection records")
    require(b["unique_dataset_ids"], 397, "corpus B unique dataset IDs")
    require(b["retained_distributions"], 800, "corpus B distributions")
    require(
        b["chunk_occurrences_before_exact_cross_stratum_deduplication"],
        44520,
        "corpus B chunk occurrences",
    )
    require(
        b["distinct_retrieval_rows_after_exact_cross_stratum_deduplication"],
        44491,
        "corpus B retrieval rows",
    )
    require(b["queries"], 96, "corpus B queries")

    pa = main_results["provenance_granularity"]["corpus_a"]
    pb = main_results["provenance_granularity"]["corpus_b"]
    require(pa["dataset_churn"], 0.1037, "corpus A dataset churn")
    require(pa["intermediate_churn"], 0.1756, "corpus A intermediate churn")
    require(pa["chunk_churn"], 0.2302, "corpus A chunk churn")
    require(pb["dataset_churn"], 0.2089, "corpus B dataset churn")
    require(pb["intermediate_churn"], 0.2407, "corpus B distribution churn")
    require(pb["chunk_churn"], 0.3938, "corpus B chunk churn")
    require(pb["share_of_gap_below_distribution"], 0.828, "corpus B sub-distribution gap share")

    tests = main_results["confirmation_tests"]
    require(tests["h1"]["rank_biserial"], 0.928, "H1 rank-biserial")
    require(tests["h1"]["holm_adjusted_p"], 1.08e-13, "H1 adjusted p")
    require(tests["h2"]["spearman_rho"], 0.155, "H2 Spearman rho")
    require(tests["h2"]["holm_adjusted_p"], 0.131, "H2 adjusted p")
    require(tests["h2"]["supported"], False, "H2 support flag")

    replay = main_results["replay"]
    require(replay["recorded_retrieval_runs"], 1152, "recorded retrieval runs")
    require(replay["exact_ordered_evidence_replays"], 1152, "exact ordered-evidence replays")

    drift_a = main_results["answer_drift"]["corpus_a"]
    require((drift_a["qwen3_8b"]["material"], drift_a["qwen3_8b"]["n"]), (22, 192), "Qwen corpus A drift")
    require((drift_a["ministral_3_8b"]["material"], drift_a["ministral_3_8b"]["n"]), (22, 192), "Ministral corpus A drift")
    require((drift_a["gemma_3_4b"]["material"], drift_a["gemma_3_4b"]["n"]), (20, 192), "Gemma corpus A drift")

    drift_b = main_results["answer_drift"]["corpus_b"]
    require((drift_b["openai_judge_material"], drift_b["n"]), (31, 81), "corpus B primary drift")
    require(drift_b["strict_same_dataset_set_changed_chunks"], 19, "corpus B strict hidden-drift cases")
    require(drift_b["strict_material_openai"], 9, "corpus B strict OpenAI material")
    require(drift_b["strict_material_human_three_rater"], 7, "corpus B strict 3-rater material")
    require(drift_b["strict_material_human_five_rater"], 8, "corpus B strict 5-rater material")

    require((same["combined"]["exact_match_count"], same["combined"]["condition_count"]), (306, 306), "same-evidence controls")
    require((main_results["same_evidence_generation"]["exact"], main_results["same_evidence_generation"]["n"]), (306, 306), "same-evidence headline")

    # Published replay artifacts: exact byte identity and recorded replay linkage.
    a_ledger_path = REPLAY / "corpus_a" / "benchmark_v2_confirmation_retrieval_ledger_c725fba20382.json"
    a_replay_path = REPLAY / "corpus_a" / "benchmark_v2_confirmation_strict_replay_c725fba20382.json"
    b_ledger_path = REPLAY / "corpus_b" / "primary_retrieval_runs.jsonl"
    b_freeze_path = REPLAY / "corpus_b" / "retrieval_freeze.json"
    b_replay_path = REPLAY / "corpus_b" / "replay_audit.json"

    expected_hashes = {
        a_ledger_path: "335555045685798fc27f781b39092d1b1b9f17af8c53dd16d0e2f757db18a1c0",
        a_replay_path: "15d824e5525c4c6376e69a2f58a3cfef8c8a0701984402bdbf291f1f2e229faf",
        b_ledger_path: "5138ae7d90906709b1b5f8792560c8ddde95b57a01614cafbc951e7542294383",
        b_freeze_path: "a8467b3fbd8c0bfa5af8f9f0825ad52332636f813688192dd7c35dda0f9eda6e",
        b_replay_path: "228e913ed08717ccec75c8a1173ff4d3316e749dba7f954059420a57b995d809",
    }
    for path, expected in expected_hashes.items():
        require(sha256(path), expected, f"SHA-256 {path.relative_to(ROOT)}")

    a_replay = load_json(a_replay_path)
    require(a_replay["retrieval_ledger_sha256"], expected_hashes[a_ledger_path], "corpus A ledger linkage")
    require(a_replay["evaluated_run_count"], 960, "corpus A replay run count")
    require(a_replay["exact_replay_count"], 960, "corpus A exact replay count")
    require(a_replay["failure_count"], 0, "corpus A replay failures")
    require(a_replay["all_exact_replay"], True, "corpus A all-exact flag")

    b_freeze = load_json(b_freeze_path)
    require(b_freeze["primary_retrieval_runs_sha256"], expected_hashes[b_ledger_path], "corpus B ledger linkage")
    require(b_freeze["run_count"], 192, "corpus B frozen run count")
    require(b_freeze["logical_chunk_count"], 44491, "corpus B frozen logical chunk count")

    b_ledger_lines = [line for line in b_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    require(len(b_ledger_lines), 192, "corpus B published ledger rows")

    b_replay = load_json(b_replay_path)
    require(b_replay["run_count"], 192, "corpus B replay run count")
    require(b_replay["exact_ordered_evidence_replays"], 192, "corpus B exact replay count")
    require(b_replay["failed_replays"], 0, "corpus B replay failures")
    require(b_replay["confirmation_pass"], True, "corpus B replay pass flag")

    require(
        a_replay["exact_replay_count"] + b_replay["exact_ordered_evidence_replays"],
        1152,
        "combined exact replay count from published artifacts",
    )

    checksum_manifest = (REPLAY / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for path, expected in expected_hashes.items():
        relative = path.relative_to(REPLAY).as_posix()
        require(f"{expected}  {relative}" in checksum_manifest, True, f"checksum manifest entry {relative}")

    print("OK: publication summaries match the manuscript headline values.")
    print("OK: published replay artifacts preserve the frozen hashes and 1,152/1,152 recorded exact replays.")
    print("NOTE: this verifies recorded artifacts and summaries; it does not rerun retrieval or generation.")


if __name__ == "__main__":
    main()
