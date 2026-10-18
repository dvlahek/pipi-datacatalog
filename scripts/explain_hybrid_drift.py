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
from app.rag.profiles import get_retrieval_profile
from app.rag.search import search_rag


def _key(item: dict[str, Any]) -> tuple[str, int, int]:
    return (
        str(item.get("dataset_identifier") or ""),
        int(item.get("dataset_version") or 0),
        int(item.get("chunk_index") or 0),
    )


def _label(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    file_path = str(metadata.get("file_path") or "").strip()
    if file_path:
        return file_path
    return f"{item.get('dataset_identifier')} · chunk {item.get('chunk_index')}"


def _fmt_rank(value: object) -> str:
    return "–" if value is None else str(value)


def _print_result_table(name: str, payload: dict[str, Any], *, limit: int) -> None:
    print(name)
    print("  final  lexical  vector   similarity   rrf-score  evidence")
    for final_rank, item in enumerate(list(payload.get("data") or [])[:limit], start=1):
        similarity = item.get("vector_similarity")
        similarity_text = "–" if similarity is None else f"{float(similarity):.4f}"
        score = item.get("score")
        score_text = "–" if score is None else f"{float(score):.6f}"
        print(
            f"  {final_rank:>5}  {_fmt_rank(item.get('lexical_rank')):>7}  "
            f"{_fmt_rank(item.get('vector_rank')):>6}  {similarity_text:>10}  "
            f"{score_text:>9}  {_label(item)}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Explain hybrid retrieval drift by separating stable lexical ranks from "
            "profile-dependent vector ranks."
        )
    )
    parser.add_argument("query")
    parser.add_argument("--left", default="hybrid-e5-content-v1")
    parser.add_argument("--right", default="hybrid-e5-metadata-v1")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    store = catalog_store(settings)
    if store is None:
        raise SystemExit("Persistent catalog store is required.")

    left_profile = get_retrieval_profile(args.left)
    right_profile = get_retrieval_profile(args.right)
    if left_profile.mode != "hybrid" or right_profile.mode != "hybrid":
        raise SystemExit("This diagnostic expects two hybrid retrieval profiles.")

    controlled_same = {
        "base embedding model": left_profile.embedding_model == right_profile.embedding_model,
        "embedding dimensions": left_profile.embedding_dimensions == right_profile.embedding_dimensions,
        "RRF k": left_profile.rrf_k == right_profile.rrf_k,
        "diversity cap": left_profile.diversity_max_per_file == right_profile.diversity_max_per_file,
    }

    left = search_rag(store, settings, args.query, limit=args.limit, profile_id=args.left)
    right = search_rag(store, settings, args.query, limit=args.limit, profile_id=args.right)

    left_rows = list(left.get("data") or [])[: args.limit]
    right_rows = list(right.get("data") or [])[: args.limit]
    left_by_key = {_key(item): (rank, item) for rank, item in enumerate(left_rows, start=1)}
    right_by_key = {_key(item): (rank, item) for rank, item in enumerate(right_rows, start=1)}

    print(f"Query: {args.query}")
    print(f"Profiles: {args.left}  ->  {args.right}")
    print(
        "Embedding input: "
        f"{left_profile.embedding_input_profile} -> {right_profile.embedding_input_profile}"
    )
    print("Controlled settings:")
    for name, same in controlled_same.items():
        print(f"  {name}: {'same' if same else 'DIFFERENT'}")
    print()

    _print_result_table("LEFT HYBRID", left, limit=args.limit)
    _print_result_table("RIGHT HYBRID", right, limit=args.limit)

    if left_rows and right_rows:
        left_top = left_rows[0]
        right_top = right_rows[0]
        print("TOP-1 COMPONENTS")
        print(
            f"  LEFT : {_label(left_top)} | lexical={_fmt_rank(left_top.get('lexical_rank'))} "
            f"vector={_fmt_rank(left_top.get('vector_rank'))} score={left_top.get('score')}"
        )
        print(
            f"  RIGHT: {_label(right_top)} | lexical={_fmt_rank(right_top.get('lexical_rank'))} "
            f"vector={_fmt_rank(right_top.get('vector_rank'))} score={right_top.get('score')}"
        )
        print()

    shared = set(left_by_key) & set(right_by_key)
    movements: list[tuple[int, tuple[str, int, int], int, int, dict[str, Any], dict[str, Any]]] = []
    lexical_mismatches = 0
    for key in shared:
        left_rank, left_item = left_by_key[key]
        right_rank, right_item = right_by_key[key]
        if left_item.get("lexical_rank") != right_item.get("lexical_rank"):
            lexical_mismatches += 1
        movements.append(
            (
                abs(left_rank - right_rank),
                key,
                left_rank,
                right_rank,
                left_item,
                right_item,
            )
        )

    movements.sort(reverse=True, key=lambda row: row[0])
    print("SHARED EVIDENCE: FINAL AND VECTOR RANK MOVEMENT")
    for _, _, left_rank, right_rank, left_item, right_item in movements:
        left_vector = left_item.get("vector_rank")
        right_vector = right_item.get("vector_rank")
        vector_delta = "n/a"
        if left_vector is not None and right_vector is not None:
            vector_delta = f"{int(right_vector) - int(left_vector):+d}"
        print(
            f"  final {left_rank:>2}->{right_rank:<2}  "
            f"lex={_fmt_rank(left_item.get('lexical_rank')):>3}  "
            f"vec={_fmt_rank(left_vector):>3}->{_fmt_rank(right_vector):<3} "
            f"dvec={vector_delta:>4}  {_label(left_item)}"
        )

    print()
    if lexical_mismatches == 0:
        print("LEXICAL_COMPONENT_STABLE_FOR_SHARED_EVIDENCE")
    else:
        print(f"LEXICAL_RANK_MISMATCHES={lexical_mismatches}")
    print(
        "Interpretation: with the controlled settings above held fixed, differences in the "
        "hybrid ranking are driven by the changed vector representation and can then be "
        "amplified by RRF and post-fusion diversity selection."
    )


if __name__ == "__main__":
    main()
