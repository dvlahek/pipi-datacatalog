from __future__ import annotations

import re
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
