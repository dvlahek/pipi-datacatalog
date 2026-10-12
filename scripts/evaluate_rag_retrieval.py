from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from app.catalog.service import catalog_store
from app.config import get_settings
from app.rag.search import search_rag

_DEFAULT_CASES = _REPOSITORY_ROOT / "config" / "rag_eval_queries.json"


def _matches_relevance(item: dict[str, Any], relevant: dict[str, Any]) -> bool:
    dataset_identifier = str(item.get("dataset_identifier") or "")
    exact_dataset = relevant.get("dataset_identifier")
    if exact_dataset and dataset_identifier != str(exact_dataset):
        return False

    dataset_contains = str(relevant.get("dataset_identifier_contains") or "").strip()
    if dataset_contains and dataset_contains.casefold() not in dataset_identifier.casefold():
        return False

    metadata = item.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    file_path = str(metadata.get("file_path") or "")
    path_terms = [str(value) for value in relevant.get("file_path_contains_any") or []]
    if path_terms and not any(term.casefold() in file_path.casefold() for term in path_terms):
        return False

    text = str(item.get("text") or "")
    text_terms = [str(value) for value in relevant.get("text_contains_any") or []]
    if text_terms and not any(term.casefold() in text.casefold() for term in text_terms):
        return False

    return True


def _first_relevant_rank(results: list[dict[str, Any]], relevant: dict[str, Any]) -> int | None:
    for rank, item in enumerate(results, start=1):
        if _matches_relevance(item, relevant):
            return rank
    return None


def _summary(ranks: list[int | None], *, limit: int) -> dict[str, float | int]:
    count = len(ranks)
    reciprocal = [0.0 if rank is None else 1.0 / rank for rank in ranks]
    return {
        "queries": count,
        "hit_at_1": sum(rank == 1 for rank in ranks) / count if count else 0.0,
        "hit_at_3": sum(rank is not None and rank <= 3 for rank in ranks) / count if count else 0.0,
        f"hit_at_{limit}": sum(rank is not None and rank <= limit for rank in ranks) / count if count else 0.0,
        "mrr": sum(reciprocal) / count if count else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PiPi lexical/vector/hybrid retrieval.")
    parser.add_argument("--cases", type=Path, default=_DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["lexical", "vector", "hybrid"],
        default=["lexical", "vector", "hybrid"],
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required. Set CATALOG_STORE_ENABLED=true.")

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise SystemExit("Evaluation case file must contain a non-empty JSON list.")

    report: dict[str, Any] = {
        "embedding_provider": settings.rag_embedding_provider,
        "embedding_model": settings.rag_embedding_model,
        "limit": args.limit,
        "modes": {},
    }

    for mode in args.modes:
        ranks: list[int | None] = []
        rows: list[dict[str, Any]] = []
        for case in cases:
            query = str(case["query"])
            payload = search_rag(store, settings, query, limit=args.limit, mode=mode)
            results = list(payload.get("data") or [])
            relevant = dict(case.get("relevant") or {})
            rank = _first_relevant_rank(results, relevant)
            ranks.append(rank)
            rows.append(
                {
                    "id": case.get("id"),
                    "query": query,
                    "rank": rank,
                    "hit": rank is not None,
                    "top_dataset": results[0].get("dataset_identifier") if results else None,
                    "top_file": (
                        (results[0].get("metadata") or {}).get("file_path")
                        if results and isinstance(results[0].get("metadata"), dict)
                        else None
                    ),
                }
            )
        report["modes"][mode] = {
            "metrics": _summary(ranks, limit=args.limit),
            "cases": rows,
        }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"Embedding: {report['embedding_provider']} · {report['embedding_model']}")
    print(f"Cases: {len(cases)} · top-k: {args.limit}")
    for mode in args.modes:
        mode_report = report["modes"][mode]
        metrics = mode_report["metrics"]
        print()
        print(mode.upper())
        print(
            f"Hit@1={metrics['hit_at_1']:.3f}  "
            f"Hit@3={metrics['hit_at_3']:.3f}  "
            f"Hit@{args.limit}={metrics[f'hit_at_{args.limit}']:.3f}  "
            f"MRR={metrics['mrr']:.3f}"
        )
        for row in mode_report["cases"]:
            rank = "MISS" if row["rank"] is None else f"#{row['rank']}"
            source = row["top_file"] or row["top_dataset"] or "—"
            print(f"  {rank:>4}  {row['id']}: {row['query']}  [top: {source}]")


if __name__ == "__main__":
    main()
