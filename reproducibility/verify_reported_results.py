#!/usr/bin/env python3
"""Verify the compact publication summaries against the manuscript headline values.

This script does not rerun retrieval, generation, or human/model judging. It checks
that the retained publication summaries are internally consistent with the values
reported in the manuscript.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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

    print("OK: compact publication summaries match the manuscript headline values.")
    print("NOTE: this verifies archived summaries; it does not rerun retrieval or generation.")


if __name__ == "__main__":
    main()
