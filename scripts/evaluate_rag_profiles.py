from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.profiles import builtin_retrieval_profiles
from app.rag.search import search_rag

_DEFAULT_CASES = ROOT / "config" / "rag_eval_queries.json"


def _matches(item: dict[str, Any], relevant: dict[str, Any]) -> bool:
    dataset_identifier = str(item.get("dataset_identifier") or "")
    exact = relevant.get("dataset_identifier")
    if exact and dataset_identifier != str(exact):
        return False
    contains = str(relevant.get("dataset_identifier_contains") or "").strip()
    if contains and contains.casefold() not in dataset_identifier.casefold():
        return False

    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    file_path = str(metadata.get("file_path") or "")
    path_terms = [str(value) for value in relevant.get("file_path_contains_any") or []]
    if path_terms and not any(term.casefold() in file_path.casefold() for term in path_terms):
        return False

    text = str(item.get("text") or "")
    text_terms = [str(value) for value in relevant.get("text_contains_any") or []]
    if text_terms and not any(term.casefold() in text.casefold() for term in text_terms):
        return False
    return True


def _rank(results: list[dict[str, Any]], relevant: dict[str, Any]) -> int | None:
    for rank, item in enumerate(results, start=1):
        if _matches(item, relevant):
            return rank
    return None


def _metrics(ranks: list[int | None], limit: int) -> dict[str, float]:
    n = len(ranks)
    return {
        "hit_at_1": sum(rank == 1 for rank in ranks) / n,
        "hit_at_3": sum(rank is not None and rank <= 3 for rank in ranks) / n,
        f"hit_at_{limit}": sum(rank is not None and rank <= limit for rank in ranks) / n,
        "mrr": sum(0.0 if rank is None else 1.0 / rank for rank in ranks) / n,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare frozen PiPi retrieval profiles.")
    parser.add_argument("--cases", type=Path, default=_DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--profiles", nargs="*", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    available = {profile.profile_id: profile for profile in builtin_retrieval_profiles()}
    selected_ids = args.profiles or list(available)
    unknown = [profile_id for profile_id in selected_ids if profile_id not in available]
    if unknown:
        raise SystemExit(f"Unknown profile(s): {', '.join(unknown)}")

    report: dict[str, Any] = {"cases": len(cases), "top_k": args.limit, "profiles": {}}
    for profile_id in selected_ids:
        profile = available[profile_id]
        ranks: list[int | None] = []
        rows: list[dict[str, Any]] = []
        for case in cases:
            payload = search_rag(
                store,
                settings,
                str(case["query"]),
                limit=args.limit,
                profile_id=profile_id,
            )
            results = list(payload.get("data") or [])
            rank = _rank(results, dict(case.get("relevant") or {}))
            ranks.append(rank)
            rows.append({"id": case.get("id"), "rank": rank})
        report["profiles"][profile_id] = {
            "config_hash": profile.config_hash,
            "metrics": _metrics(ranks, args.limit),
            "cases": rows,
        }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"Cases: {len(cases)} · top-k: {args.limit}")
    print()
    for profile_id in selected_ids:
        item = report["profiles"][profile_id]
        metrics = item["metrics"]
        print(f"{profile_id}  hash={item['config_hash'][:12]}")
        print(
            f"  Hit@1={metrics['hit_at_1']:.3f}  "
            f"Hit@3={metrics['hit_at_3']:.3f}  "
            f"Hit@{args.limit}={metrics[f'hit_at_{args.limit}']:.3f}  "
            f"MRR={metrics['mrr']:.3f}"
        )
        misses = [row for row in item["cases"] if row["rank"] is None]
        if misses:
            print("  MISS: " + ", ".join(str(row["id"]) for row in misses))
        print()


if __name__ == "__main__":
    main()
