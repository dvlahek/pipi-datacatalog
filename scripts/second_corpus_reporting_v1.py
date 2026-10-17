#!/usr/bin/env python3
"""Create publication-safe C2 secondary summaries and a C1-C2 comparison.

This script is read-only with respect to all frozen C2 corpus, query, retrieval,
and confirmatory-analysis artifacts. It verifies the complete C2 confirmation
SHA chain first, then writes reporting-only derivatives to a separate directory.
No confirmatory statistic is recomputed or altered here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIRMATION = ROOT / "results" / "second_corpus_confirmation_v1"
DEFAULT_OUT = ROOT / "results" / "second_corpus_reporting_v1"
DEFAULT_C1_DOC = ROOT / "docs" / "benchmark_v2_reproducibility_20261015.md"

EXPECTED_CONFIRMATION_FREEZE_SHA256 = "e7bbe1bfd048103de047a816ebd48ae359a5a74b38f2462463e1a9be752ff841"
EXPECTED_C2 = {
    "mean_chunk_churn_at_10": 0.39375,
    "mean_dataset_churn_at_10": 0.20892857142857144,
    "mean_paired_difference": 0.18482142857142858,
    "H1_p_holm": 1.0752288241335711e-13,
    "H1_rank_biserial": 0.9278996865203761,
    "H2_rho": 0.15539340244407526,
    "H2_p_holm": 0.1305865068521424,
    "H3_exact_replay_rate": 1.0,
}
EXPECTED_C1 = {
    "chunk_churn_at_10": 0.2302,
    "dataset_churn_at_10": 0.1037,
    "chunk_jaccard_at_10": 0.6550,
    "dataset_jaccard_at_10": 0.8383,
    "top1_chunk_change_rate": 0.2604,
    "exact_replay_numerator": 960,
    "exact_replay_denominator": 960,
}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, obj: object) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def verify_sha_manifest(path: Path) -> int:
    checked = 0
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise RuntimeError(f"invalid SHA line {path}:{line_no}")
            expected, rel = parts
            target = Path(rel.strip().lstrip("*"))
            if not target.is_absolute():
                target = ROOT / target
            if not target.is_file():
                raise RuntimeError(f"SHA target missing: {target}")
            actual = sha_file(target)
            if actual != expected:
                raise RuntimeError(f"SHA mismatch {target}: expected={expected} actual={actual}")
            checked += 1
    return checked


def assert_close(name: str, actual: float, expected: float, tol: float = 1e-12) -> None:
    if abs(float(actual) - float(expected)) > tol:
        raise RuntimeError(f"frozen value mismatch {name}: expected={expected} actual={actual}")


def parse_c1_doc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    def grab(pattern: str, name: str) -> float:
        m = re.search(pattern, text)
        if not m:
            raise RuntimeError(f"could not parse C1 field: {name}")
        return float(m.group(1))

    chunk_churn = grab(r"chunk churn@10:\s*([0-9.]+)", "chunk churn")
    source_churn = grab(r"source churn:\s*([0-9.]+)", "source churn")
    chunk_jaccard = grab(r"chunk Jaccard@10:\s*([0-9.]+)", "chunk Jaccard")
    source_jaccard = grab(r"source Jaccard:\s*([0-9.]+)", "source Jaccard")
    top1_chunk = grab(r"top-1 chunk change rate:\s*([0-9.]+)", "top1 chunk change")
    replay = re.search(r"exact ordered evidence set for\s*(\d+)/(\d+)\s*frozen runs", text)
    if not replay:
        raise RuntimeError("could not parse C1 replay count")

    parsed = {
        "chunk_churn_at_10": chunk_churn,
        "dataset_churn_at_10": source_churn,
        "chunk_jaccard_at_10": chunk_jaccard,
        "dataset_jaccard_at_10": source_jaccard,
        "top1_chunk_change_rate": top1_chunk,
        "exact_replay_numerator": int(replay.group(1)),
        "exact_replay_denominator": int(replay.group(2)),
    }
    for key, expected in EXPECTED_C1.items():
        actual = parsed[key]
        if isinstance(expected, int):
            if int(actual) != expected:
                raise RuntimeError(f"C1 frozen value mismatch {key}: expected={expected} actual={actual}")
        else:
            assert_close(f"C1 {key}", float(actual), expected, tol=5e-8)
    parsed["source_document"] = str(path.relative_to(ROOT))
    parsed["source_document_sha256"] = sha_file(path)
    return parsed


def rows_from_secondary(secondary: dict) -> list[dict]:
    rows = []

    def add(scope: str, label: str, values: dict) -> None:
        rows.append({"scope": scope, "label": label, **values})

    add("overall", "ALL", secondary["overall"])
    for label, values in sorted(secondary["by_theme"].items()):
        add("theme", label, values)
    for label, values in sorted(secondary["by_query_type"].items()):
        add("query_type", label, values)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError("cannot write empty CSV")
    fields = list(rows[0].keys())
    extras = sorted({k for row in rows for k in row.keys()} - set(fields))
    fields.extend(extras)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(tmp, path)


def fmt_pct(value: float) -> str:
    return f"{100.0 * float(value):.2f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmation", type=Path, default=DEFAULT_CONFIRMATION)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--c1-doc", type=Path, default=DEFAULT_C1_DOC)
    args = ap.parse_args()

    manifest = args.confirmation / "SHA256SUMS.confirmation.txt"
    freeze_path = args.confirmation / "confirmation_freeze.json"
    result_path = args.confirmation / "confirmatory_results.json"
    per_query_path = args.confirmation / "per_query_metrics.jsonl"
    replay_path = args.confirmation / "replay_audit.json"
    for path in (manifest, freeze_path, result_path, per_query_path, replay_path, args.c1_doc):
        if not path.is_file():
            raise RuntimeError(f"missing required reporting input: {path}")

    checked = verify_sha_manifest(manifest)
    actual_freeze_sha = sha_file(freeze_path)
    if actual_freeze_sha != EXPECTED_CONFIRMATION_FREEZE_SHA256:
        raise RuntimeError(
            f"confirmation freeze mismatch: expected={EXPECTED_CONFIRMATION_FREEZE_SHA256} actual={actual_freeze_sha}"
        )

    freeze = read_json(freeze_path)
    result = read_json(result_path)
    if freeze.get("status") != "FROZEN_AFTER_CONFIRMATORY_ANALYSIS":
        raise RuntimeError("unexpected confirmation freeze status")
    if freeze.get("confirmatory_results_sha256") != sha_file(result_path):
        raise RuntimeError("confirmation freeze/result hash mismatch")
    if freeze.get("per_query_metrics_sha256") != sha_file(per_query_path):
        raise RuntimeError("confirmation freeze/per-query hash mismatch")
    if freeze.get("replay_audit_sha256") != sha_file(replay_path):
        raise RuntimeError("confirmation freeze/replay hash mismatch")

    h1, h2, h3 = result["H1"], result["H2"], result["H3"]
    assert_close("C2 mean chunk churn", h1["mean_chunk_churn_at_10"], EXPECTED_C2["mean_chunk_churn_at_10"])
    assert_close("C2 mean dataset churn", h1["mean_dataset_churn_at_10"], EXPECTED_C2["mean_dataset_churn_at_10"])
    assert_close("C2 mean gap", h1["mean_paired_difference"], EXPECTED_C2["mean_paired_difference"])
    assert_close("C2 H1 Holm p", h1["p_holm"], EXPECTED_C2["H1_p_holm"], tol=1e-24)
    assert_close("C2 H1 rank-biserial", h1["rank_biserial"], EXPECTED_C2["H1_rank_biserial"])
    assert_close("C2 H2 rho", h2["rho"], EXPECTED_C2["H2_rho"])
    assert_close("C2 H2 Holm p", h2["p_holm"], EXPECTED_C2["H2_p_holm"])
    assert_close("C2 H3 replay", h3["exact_replay_rate"], EXPECTED_C2["H3_exact_replay_rate"])

    if args.out.exists() and any(args.out.iterdir()):
        raise RuntimeError("REPORTING_OUTPUT_EXISTS; refusing to overwrite")
    args.out.mkdir(parents=True, exist_ok=True)

    secondary = result["secondary_descriptive"]
    subgroup_rows = rows_from_secondary(secondary)
    subgroup_csv = args.out / "c2_subgroup_summary.csv"
    write_csv(subgroup_csv, subgroup_rows)
    atomic_json(args.out / "c2_secondary_summary.json", secondary)

    c1 = parse_c1_doc(args.c1_doc)
    c2_overall = secondary["overall"]
    c2 = {
        "query_count": int(h1["n_queries"]),
        "chunk_churn_at_10": float(h1["mean_chunk_churn_at_10"]),
        "dataset_churn_at_10": float(h1["mean_dataset_churn_at_10"]),
        "chunk_minus_dataset_gap": float(h1["mean_paired_difference"]),
        "distribution_churn_at_10": float(c2_overall["mean_distribution_churn_at_10"]),
        "chunk_jaccard_at_10": float(c2_overall["mean_chunk_jaccard_at_10"]),
        "distribution_jaccard_at_10": float(c2_overall["mean_distribution_jaccard_at_10"]),
        "dataset_jaccard_at_10": float(c2_overall["mean_dataset_jaccard_at_10"]),
        "top1_chunk_change_rate": float(c2_overall["top1_chunk_change_rate"]),
        "top1_distribution_change_rate": float(c2_overall["top1_distribution_change_rate"]),
        "top1_dataset_change_rate": float(c2_overall["top1_dataset_change_rate"]),
        "hidden_chunk_drift_given_dataset_stability_rate": float(c2_overall["hidden_chunk_drift_given_dataset_stability_rate"]),
        "H1_p_holm": float(h1["p_holm"]),
        "H1_rank_biserial": float(h1["rank_biserial"]),
        "H2_rho": float(h2["rho"]),
        "H2_p_holm": float(h2["p_holm"]),
        "exact_replay_numerator": int(h3["exact_ordered_evidence_replays"]),
        "exact_replay_denominator": int(h3["run_count"]),
    }
    c1["chunk_minus_dataset_gap"] = c1["chunk_churn_at_10"] - c1["dataset_churn_at_10"]
    c1["exact_replay_rate"] = c1["exact_replay_numerator"] / c1["exact_replay_denominator"]
    c2["exact_replay_rate"] = c2["exact_replay_numerator"] / c2["exact_replay_denominator"]

    comparison = {
        "artifact": "PIPI_C1_C2_PROVENANCE_COMPARISON_V1",
        "status": "REPORTING_DERIVATIVE_FROM_FROZEN_RESULTS",
        "confirmation_freeze_sha256": actual_freeze_sha,
        "C1": c1,
        "C2": c2,
        "differences_C2_minus_C1": {
            "chunk_churn_at_10": c2["chunk_churn_at_10"] - c1["chunk_churn_at_10"],
            "dataset_churn_at_10": c2["dataset_churn_at_10"] - c1["dataset_churn_at_10"],
            "chunk_minus_dataset_gap": c2["chunk_minus_dataset_gap"] - c1["chunk_minus_dataset_gap"],
            "top1_chunk_change_rate": c2["top1_chunk_change_rate"] - c1["top1_chunk_change_rate"],
        },
        "interpretation_guardrail": (
            "C1 and C2 differ in corpus construction and evidence content. Differences in magnitudes are descriptive; "
            "the confirmatory C2 claim is replication of the granularity ordering, not equality of effect sizes."
        ),
    }
    comparison_json = args.out / "c1_c2_comparison.json"
    atomic_json(comparison_json, comparison)

    comparison_rows = [
        {"metric": "chunk_churn_at_10", "C1": c1["chunk_churn_at_10"], "C2": c2["chunk_churn_at_10"]},
        {"metric": "dataset_churn_at_10", "C1": c1["dataset_churn_at_10"], "C2": c2["dataset_churn_at_10"]},
        {"metric": "chunk_minus_dataset_gap", "C1": c1["chunk_minus_dataset_gap"], "C2": c2["chunk_minus_dataset_gap"]},
        {"metric": "chunk_jaccard_at_10", "C1": c1["chunk_jaccard_at_10"], "C2": c2["chunk_jaccard_at_10"]},
        {"metric": "dataset_jaccard_at_10", "C1": c1["dataset_jaccard_at_10"], "C2": c2["dataset_jaccard_at_10"]},
        {"metric": "top1_chunk_change_rate", "C1": c1["top1_chunk_change_rate"], "C2": c2["top1_chunk_change_rate"]},
        {"metric": "exact_replay_rate", "C1": c1["exact_replay_rate"], "C2": c2["exact_replay_rate"]},
    ]
    write_csv(args.out / "c1_c2_comparison.csv", comparison_rows)

    md = f"""# C1-C2 provenance comparison\n\nStatus: reporting derivative from frozen results. No confirmatory endpoint is recomputed here.\n\n| Metric | C1 | C2 |\n|---|---:|---:|\n| Chunk churn@10 | {fmt_pct(c1['chunk_churn_at_10'])} | {fmt_pct(c2['chunk_churn_at_10'])} |\n| Dataset churn@10 | {fmt_pct(c1['dataset_churn_at_10'])} | {fmt_pct(c2['dataset_churn_at_10'])} |\n| Chunk-dataset churn gap | {fmt_pct(c1['chunk_minus_dataset_gap'])} | {fmt_pct(c2['chunk_minus_dataset_gap'])} |\n| Chunk Jaccard@10 | {c1['chunk_jaccard_at_10']:.4f} | {c2['chunk_jaccard_at_10']:.4f} |\n| Dataset Jaccard@10 | {c1['dataset_jaccard_at_10']:.4f} | {c2['dataset_jaccard_at_10']:.4f} |\n| Top-1 chunk change | {fmt_pct(c1['top1_chunk_change_rate'])} | {fmt_pct(c2['top1_chunk_change_rate'])} |\n| Exact ordered-evidence replay | {c1['exact_replay_numerator']}/{c1['exact_replay_denominator']} | {c2['exact_replay_numerator']}/{c2['exact_replay_denominator']} |\n\n## C2 confirmatory status\n\n- H1: supported. Holm-adjusted p = {h1['p_holm']:.6g}; paired rank-biserial = {h1['rank_biserial']:.3f}.\n- H2: expected positive direction observed, but not statistically supported. Spearman rho = {h2['rho']:.3f}; Holm-adjusted p = {h2['p_holm']:.3f}.\n- H3: exact replay passed for {h3['exact_ordered_evidence_replays']}/{h3['run_count']} frozen runs.\n\n## Reporting guardrail\n\nC1 and C2 differ in corpus construction and evidence content. Magnitude differences are descriptive. The C2 confirmation concerns the replicated ordering that chunk-level churn exceeds dataset-level churn under the frozen content-versus-metadata intervention.\n"""
    markdown_path = args.out / "c1_c2_comparison.md"
    atomic_text(markdown_path, md)

    report_manifest = {
        "artifact": "SECOND_CORPUS_C2_REPORTING_FREEZE_V1",
        "status": "FROZEN_REPORTING_DERIVATIVES",
        "confirmation_freeze_sha256": actual_freeze_sha,
        "confirmation_manifest_entries_verified": checked,
        "confirmatory_results_sha256": sha_file(result_path),
        "c1_source_document_sha256": sha_file(args.c1_doc),
        "c2_secondary_summary_sha256": sha_file(args.out / "c2_secondary_summary.json"),
        "c2_subgroup_summary_csv_sha256": sha_file(subgroup_csv),
        "c1_c2_comparison_json_sha256": sha_file(comparison_json),
        "c1_c2_comparison_csv_sha256": sha_file(args.out / "c1_c2_comparison.csv"),
        "c1_c2_comparison_md_sha256": sha_file(markdown_path),
        "reporting_script_sha256": sha_file(Path(__file__)),
    }
    report_freeze = args.out / "reporting_freeze.json"
    atomic_json(report_freeze, report_manifest)

    hash_paths = [
        manifest,
        freeze_path,
        result_path,
        per_query_path,
        replay_path,
        args.c1_doc,
        Path(__file__),
        args.out / "c2_secondary_summary.json",
        subgroup_csv,
        comparison_json,
        args.out / "c1_c2_comparison.csv",
        markdown_path,
        report_freeze,
    ]
    atomic_text(
        args.out / "SHA256SUMS.reporting.txt",
        "".join(f"{sha_file(path)}  {path.relative_to(ROOT)}\n" for path in hash_paths),
    )

    print("C2_REPORTING_FROZEN")
    print(json.dumps({
        "confirmation_freeze_sha256": actual_freeze_sha,
        "reporting_freeze_sha256": sha_file(report_freeze),
        "C2_overall": c2,
        "C2_minus_C1": comparison["differences_C2_minus_C1"],
        "subgroup_rows": len(subgroup_rows),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
