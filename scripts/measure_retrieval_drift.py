from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import compare_profiles

_DEFAULT_CASES = ROOT / "config" / "rag_eval_queries.json"


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure retrieval-induced evidence drift between two frozen PiPi profiles."
    )
    parser.add_argument("--cases", type=Path, default=_DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--left", default="hybrid-e5-content-v1")
    parser.add_argument("--right", default="hybrid-e5-metadata-v1")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for case in cases:
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
                "id": case.get("id"),
                "query": case.get("query"),
                "catalog_snapshot_hash": comparison["catalog_snapshot_hash"],
                **drift,
            }
        )

    report = {
        "cases": len(rows),
        "top_k": args.limit,
        "left_profile": args.left,
        "right_profile": args.right,
        "summary": {
            "mean_retention_at_k": _mean([float(row["retention_at_k"]) for row in rows]),
            "mean_churn_at_k": _mean([float(row["churn_at_k"]) for row in rows]),
            "mean_jaccard_at_k": _mean([float(row["jaccard_at_k"]) for row in rows]),
            "top1_change_rate": _mean([0.0 if row["top1_same"] else 1.0 for row in rows]),
            "exact_order_reproduction_rate": _mean(
                [1.0 if row["ordered_evidence_same"] else 0.0 for row in rows]
            ),
            "mean_rank_shift_common": _mean(
                [
                    float(row["mean_abs_rank_shift_common"])
                    for row in rows
                    if row["mean_abs_rank_shift_common"] is not None
                ]
            ),
        },
        "cases_detail": rows,
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    summary = report["summary"]
    print(f"Profiles: {args.left}  ->  {args.right}")
    print(f"Cases: {len(rows)} · top-k: {args.limit}")
    print(
        f"Mean retention@{args.limit}={summary['mean_retention_at_k']:.3f}  "
        f"Mean churn@{args.limit}={summary['mean_churn_at_k']:.3f}  "
        f"Mean Jaccard@{args.limit}={summary['mean_jaccard_at_k']:.3f}"
    )
    print(
        f"Top-1 change rate={summary['top1_change_rate']:.3f}  "
        f"Exact ordered evidence match={summary['exact_order_reproduction_rate']:.3f}  "
        f"Mean rank shift (shared evidence)={summary['mean_rank_shift_common']:.3f}"
    )
    print()
    for row in rows:
        print(
            f"{row['id']}: retention={row['retention_at_k']:.2f}  "
            f"jaccard={row['jaccard_at_k']:.2f}  "
            f"top1={'same' if row['top1_same'] else 'CHANGED'}  "
            f"rank-shift={row['mean_abs_rank_shift_common']}"
        )


if __name__ == "__main__":
    main()
