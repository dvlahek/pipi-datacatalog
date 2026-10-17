from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.drift import compare_profiles, evidence_key


def _label(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    file_path = str(metadata.get("file_path") or "").strip()
    if file_path:
        return file_path
    dataset = str(item.get("dataset_identifier") or "")
    chunk = item.get("chunk_index")
    return f"{dataset} · chunk {chunk}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show which evidence was added, removed or re-ranked between two frozen retrieval profiles."
    )
    parser.add_argument("query", nargs="?", default="vlaga na demo-site-a")
    parser.add_argument("--left", default="hybrid-e5-content-v1")
    parser.add_argument("--right", default="hybrid-e5-metadata-v1")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    payload = compare_profiles(
        store,
        settings,
        args.query,
        left_profile_id=args.left,
        right_profile_id=args.right,
        limit=args.limit,
    )
    drift = payload["drift"]
    left = list(payload["left"].get("data") or [])[: args.limit]
    right = list(payload["right"].get("data") or [])[: args.limit]

    left_rank = {evidence_key(item): index for index, item in enumerate(left, start=1)}
    right_rank = {evidence_key(item): index for index, item in enumerate(right, start=1)}
    left_by_key = {evidence_key(item): item for item in left}
    right_by_key = {evidence_key(item): item for item in right}

    left_only = [key for key in left_rank if key not in right_rank]
    right_only = [key for key in right_rank if key not in left_rank]
    shared = [key for key in left_rank if key in right_rank]
    moved = sorted(
        shared,
        key=lambda key: abs(left_rank[key] - right_rank[key]),
        reverse=True,
    )

    print(f"Query: {args.query}")
    print(f"Profiles: {args.left}  ->  {args.right}")
    print(f"Catalog snapshot: {str(payload['catalog_snapshot_hash'])[:12]}")
    print(
        f"Retention@{args.limit}={drift['retention_at_k']:.3f}  "
        f"Churn@{args.limit}={drift['churn_at_k']:.3f}  "
        f"Jaccard@{args.limit}={drift['jaccard_at_k']:.3f}"
    )
    print(
        f"Top-1: {'same' if drift['top1_same'] else 'CHANGED'}  "
        f"Mean rank shift={drift['mean_abs_rank_shift_common']}"
    )
    print()

    if left:
        print(f"LEFT  #1: {_label(left[0])}")
    if right:
        print(f"RIGHT #1: {_label(right[0])}")
    print()

    print("REMOVED FROM TOP-K")
    if not left_only:
        print("  none")
    for key in left_only:
        print(f"  L#{left_rank[key]:>2}  {_label(left_by_key[key])}")
    print()

    print("ADDED TO TOP-K")
    if not right_only:
        print("  none")
    for key in right_only:
        print(f"  R#{right_rank[key]:>2}  {_label(right_by_key[key])}")
    print()

    print("SHARED EVIDENCE WITH LARGEST RANK MOVES")
    any_move = False
    for key in moved:
        delta = right_rank[key] - left_rank[key]
        if delta == 0:
            continue
        any_move = True
        direction = f"{delta:+d}"
        print(
            f"  L#{left_rank[key]:>2} -> R#{right_rank[key]:>2}  "
            f"delta={direction:>3}  {_label(right_by_key[key])}"
        )
    if not any_move:
        print("  none")


if __name__ == "__main__":
    main()
