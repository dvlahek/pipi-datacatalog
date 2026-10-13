from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import compare_profiles, compare_ranked_sources
from app.rag.profiles import catalog_snapshot_hash, get_retrieval_profile

DEFAULT_CASES = ROOT / "config" / "rag_eval_queries.json"
DEFAULT_TAXONOMY = ROOT / "config" / "rag_eval_query_taxonomy.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _summary(rows: list[dict[str, Any]], prefix: str) -> dict[str, float]:
    return {
        "mean_retention": _mean([float(row[f"{prefix}_retention"]) for row in rows]),
        "mean_churn": _mean([float(row[f"{prefix}_churn"]) for row in rows]),
        "mean_jaccard": _mean([float(row[f"{prefix}_jaccard"]) for row in rows]),
        "top1_change_rate": _mean(
            [0.0 if bool(row[f"{prefix}_top1_same"]) else 1.0 for row in rows]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the PiPi retrieval-profile pilot as a provenance-rich JSON artifact."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--left", default="hybrid-e5-content-v1")
    parser.add_argument("--right", default="hybrid-e5-metadata-v1")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    taxonomy_payload = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    taxonomy_rows = taxonomy_payload.get("cases", taxonomy_payload)
    taxonomy = {
        str(item["id"]): item
        for item in taxonomy_rows
        if isinstance(item, dict) and item.get("id")
    }

    left_profile = get_retrieval_profile(args.left)
    right_profile = get_retrieval_profile(args.right)
    frozen_snapshot = catalog_snapshot_hash(store)

    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("id") or "")
        comparison = compare_profiles(
            store,
            settings,
            str(case["query"]),
            left_profile_id=args.left,
            right_profile_id=args.right,
            limit=args.limit,
        )
        if comparison["catalog_snapshot_hash"] != frozen_snapshot:
            raise SystemExit("Catalog snapshot changed while freezing the pilot. Run again on a stable catalog.")

        chunk = dict(comparison["drift"])
        left_data = list(comparison["left"].get("data") or [])
        right_data = list(comparison["right"].get("data") or [])
        source = compare_ranked_sources(left_data, right_data, limit=args.limit)
        tag = taxonomy.get(case_id, {})
        rows.append(
            {
                "id": case_id,
                "query": case.get("query"),
                "taxonomy": {
                    key: tag.get(key)
                    for key in ("source_family", "language_relation", "query_type")
                    if tag.get(key) is not None
                },
                "chunk_retention": chunk["retention_at_k"],
                "chunk_churn": chunk["churn_at_k"],
                "chunk_jaccard": chunk["jaccard_at_k"],
                "chunk_top1_same": chunk["top1_same"],
                "chunk_mean_rank_shift": chunk["mean_abs_rank_shift_common"],
                "chunk_left_evidence_hash": chunk["left_evidence_hash"],
                "chunk_right_evidence_hash": chunk["right_evidence_hash"],
                "source_retention": source["retention_at_k"],
                "source_churn": source["churn_at_k"],
                "source_jaccard": source["jaccard_at_k"],
                "source_top1_same": source["top1_same"],
                "left_top1": left_data[0] if left_data else None,
                "right_top1": right_data[0] if right_data else None,
            }
        )

    chunk_summary = _summary(rows, "chunk")
    rank_shifts = [
        float(row["chunk_mean_rank_shift"])
        for row in rows
        if row["chunk_mean_rank_shift"] is not None
    ]
    chunk_summary["mean_rank_shift_shared"] = _mean(rank_shifts)

    artifact = {
        "artifact": "pipi-retrieval-pilot-p1",
        "artifact_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "benchmark": {
            "case_count": len(cases),
            "top_k": args.limit,
            "cases_path": str(args.cases.relative_to(ROOT)) if args.cases.is_relative_to(ROOT) else str(args.cases),
            "cases_sha256": _sha256(args.cases),
            "taxonomy_path": str(args.taxonomy.relative_to(ROOT)) if args.taxonomy.is_relative_to(ROOT) else str(args.taxonomy),
            "taxonomy_sha256": _sha256(args.taxonomy),
        },
        "catalog_snapshot_hash": frozen_snapshot,
        "left_profile": {
            "profile_id": left_profile.profile_id,
            "config_hash": left_profile.config_hash,
            "config": left_profile.config(),
        },
        "right_profile": {
            "profile_id": right_profile.profile_id,
            "config_hash": right_profile.config_hash,
            "config": right_profile.config(),
        },
        "summary": {
            "chunk_level": chunk_summary,
            "source_level": _summary(rows, "source"),
        },
        "cases": rows,
        "interpretation_boundary": (
            "Pilot artifact only. Subgroup effects are descriptive because the benchmark contains 16 cases "
            "and several taxonomy cells have very small n."
        ),
    }

    output = args.output
    if output is None:
        output = ROOT / "results" / f"retrieval_pilot_p1_{frozen_snapshot[:12]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"FROZEN_PILOT_ARTIFACT={output}")
    print(f"CATALOG_SNAPSHOT={frozen_snapshot}")
    print(f"LEFT_PROFILE_HASH={left_profile.config_hash}")
    print(f"RIGHT_PROFILE_HASH={right_profile.config_hash}")
    print(
        "CHUNK: "
        f"retention={chunk_summary['mean_retention']:.3f} "
        f"churn={chunk_summary['mean_churn']:.3f} "
        f"jaccard={chunk_summary['mean_jaccard']:.3f} "
        f"top1-change={chunk_summary['top1_change_rate']:.3f}"
    )
    source_summary = artifact["summary"]["source_level"]
    print(
        "SOURCE: "
        f"retention={source_summary['mean_retention']:.3f} "
        f"churn={source_summary['mean_churn']:.3f} "
        f"jaccard={source_summary['mean_jaccard']:.3f} "
        f"top1-change={source_summary['top1_change_rate']:.3f}"
    )
    print("PILOT_P1_FROZEN")


if __name__ == "__main__":
    main()
