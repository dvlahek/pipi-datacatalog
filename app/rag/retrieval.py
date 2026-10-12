from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

_TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def query_tokens(query: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(query) if token.strip()]


def lexical_score(query: str, text: str) -> float:
    """Return a simple deterministic lexical relevance score.

    This is intentionally embedding-free. It provides a transparent baseline that
    can be tested before pgvector/semantic retrieval is introduced.
    """
    tokens = query_tokens(query)
    if not tokens:
        return 0.0

    normalized = normalize_text(text)
    matched = sum(1 for token in tokens if token in normalized)
    if matched == 0:
        return 0.0

    score = matched / len(tokens)
    normalized_query = normalize_text(query)
    if normalized_query and normalized_query in normalized:
        score += 0.25
    return round(score, 6)


def rank_chunk_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        score = lexical_score(query, str(candidate.get("text", "")))
        if score <= 0:
            continue
        item = dict(candidate)
        item["score"] = score
        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            -float(item["score"]),
            str(item.get("dataset_identifier", "")),
            int(item.get("chunk_index", 0)),
        )
    )
    return ranked[:limit]


def _source_diversity_key(item: dict[str, Any]) -> tuple[str, str] | None:
    """Return a source key only when a finer-grained source is known.

    A GitHub repository is one catalog Dataset, so diversifying by dataset would
    incorrectly suppress useful results from different files. GitHub chunks carry
    immutable ``file_path`` metadata, which is the appropriate retrieval source.
    Other modalities keep their normal ranking until an equivalent source boundary
    is available.
    """

    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        return None
    file_path = str(metadata.get("file_path") or "").strip()
    if not file_path:
        return None
    return (str(item.get("dataset_identifier") or ""), file_path)


def diversify_ranked_results(
    ranked: list[dict[str, Any]],
    *,
    limit: int,
    max_per_source: int = 2,
) -> list[dict[str, Any]]:
    """Prefer source diversity while preserving the original relevance order.

    For sources with a known fine-grained identity (currently GitHub ``file_path``),
    keep at most ``max_per_source`` results during the first pass. If the candidate
    pool does not contain enough distinct sources, deferred results are appended in
    their original order so retrieval still returns up to ``limit`` items.
    """

    if limit <= 0:
        return []
    cap = max(1, int(max_per_source))
    counts: dict[tuple[str, str], int] = defaultdict(int)
    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for item in ranked:
        key = _source_diversity_key(item)
        if key is not None and counts[key] >= cap:
            deferred.append(item)
            continue

        selected.append(item)
        if key is not None:
            counts[key] += 1
        if len(selected) >= limit:
            return selected[:limit]

    for item in deferred:
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected[:limit]
