from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import compare_profiles

_DEFAULT_CASES = ROOT / "config" / "rag_eval_queries.json"
_DEFAULT_TAXONOMY = ROOT / "config" / "rag_eval_taxonomy.json"
_AXES = ("source_family", "language_relation", "query_type")


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rank_shifts = [
        float(row["mean_abs_rank_shift_common"])
        for row in rows
        if row.get("mean_abs_rank_shift_common") is not None
    ]
    return {
        "n": len(rows),
        "mean_retention_at_k": _mean([float(row["retention_at_k"]) for row in rows]),
        "mean_churn_at_k": _mean([float(row["churn_at_k"]) for row in rows]),
        "mean_jaccard_at_k": _mean([float(row["jaccard_at_k"]) for row in rows]),
        "top1_change_rate": _mean([0.0 if row["top1_same"] else 1.0 for row in rows]),
        "exact_order_match_rate": _mean(
            [1.0 if row["ordered_evidence_same"] else 0.0 for row in rows]
        ),
        "mean_rank_shift_common": _mean(rank_shifts),
    }


def _load_inputs(cases_path: Path, taxonomy_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    taxonomy_payload = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    taxonomy = dict(taxonomy_payload.get("cases") or {})

    case_ids = [str(case.get("id") or "") for case in cases]
    missing = [case_id for case_id in case_ids if case_id not in taxonomy]
    extra = sorted(set(taxonomy) - set(case_ids))
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing taxonomy: " + ", ".join(missing))
        if extra:
            parts.append("unknown taxonomy IDs: " + ", ".join(extra))
        raise SystemExit("Taxonomy does not match frozen benchmark (" + "; ".join(parts) + ").")

    for case_id in case_ids:
        labels = taxonomy[case_id]
        absent_axes = [axis for axis in _AXES if not str(labels.get(axis) or "").strip()]
        if absent_axes:
            raise SystemExit(
                f"Taxonomy case {case_id!r} is missing required axis/axes: {', '.join(absent_axes)}"
            )
    return cases, taxonomy


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Decompose retrieval-induced evidence drift by frozen pilot query taxonomy. "
            "The query/relevance benchmark remains unchanged; taxonomy is stored separately."
        )
    )
    parser.add_argument("--cases", type=Path, default=_DEFAULT_CASES)
    parser.add_argument("--taxonomy", type=Path, default=_DEFAULT_TAXONOMY)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--left", default="hybrid-e5-content-v1")
    parser.add_argument("--right", default="hybrid-e5-metadata-v1")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    cases, taxonomy = _load_inputs(args.cases, args.taxonomy)
    rows: list[dict[str, Any]] = []

    for case in cases:
        case_id = str(case["id"])
        comparison = compare_profiles(
            store,
            settings,
            str(case["query"]),
            left_profile_id=args.left,
            right_profile_id=args.right,
            limit=args.limit,
        )
        drift = dict(comparison["drift"])
        rows.append(
            {
                "id": case_id,
                "query": case["query"],
                "taxonomy": taxonomy[case_id],
                "catalog_snapshot_hash": comparison["catalog_snapshot_hash"],
                **drift,
            }
        )

    grouped: dict[str, dict[str, Any]] = {}
    for axis in _AXES:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[str(row["taxonomy"][axis])].append(row)
        grouped[axis] = {
            label: _summarize(bucket_rows)
            for label, bucket_rows in sorted(buckets.items())
        }

    report = {
        "benchmark": "rag_eval_queries-v1-pilot",
        "cases": len(rows),
        "top_k": args.limit,
        "left_profile": args.left,
        "right_profile": args.right,
        "overall": _summarize(rows),
        "by_taxonomy": grouped,
        "cases_detail": rows,
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    overall = report["overall"]
    print(f"Profiles: {args.left}  ->  {args.right}")
    print(f"Benchmark: rag_eval_queries-v1-pilot · cases={len(rows)} · top-k={args.limit}")
    print(
        f"Overall: retention={overall['mean_retention_at_k']:.3f}  "
        f"churn={overall['mean_churn_at_k']:.3f}  "
        f"jaccard={overall['mean_jaccard_at_k']:.3f}  "
        f"top1-change={overall['top1_change_rate']:.3f}  "
        f"rank-shift={overall['mean_rank_shift_common']:.3f}"
    )

    for axis in _AXES:
        print()
        print(f"BY {axis.upper()}")
        for label, summary in grouped[axis].items():
            print(
                f"  {label:28s} n={summary['n']:2d}  "
                f"retention={summary['mean_retention_at_k']:.3f}  "
                f"churn={summary['mean_churn_at_k']:.3f}  "
                f"jaccard={summary['mean_jaccard_at_k']:.3f}  "
                f"top1-change={summary['top1_change_rate']:.3f}  "
                f"rank-shift={summary['mean_rank_shift_common']:.3f}"
            )

    print()
    print("Highest-drift pilot cases (lowest retention first)")
    for row in sorted(rows, key=lambda item: (float(item["retention_at_k"]), float(item["jaccard_at_k"])))[:8]:
        taxonomy_row = row["taxonomy"]
        print(
            f"  {row['id']}: retention={row['retention_at_k']:.2f}  "
            f"jaccard={row['jaccard_at_k']:.2f}  "
            f"top1={'same' if row['top1_same'] else 'CHANGED'}  "
            f"[{taxonomy_row['source_family']}, {taxonomy_row['language_relation']}, "
            f"{taxonomy_row['query_type']}]"
        )


if __name__ == "__main__":
    main()
