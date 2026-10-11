from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.models.catalog import CanonicalDataset


_FIELD_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("title", 6),
    ("observed_property.name", 5),
    ("location.name", 4),
    ("source.name", 3),
    ("source.code", 3),
    ("publisher", 2),
    ("observed_property.semantic_uri", 2),
    ("description", 1),
)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().replace("_", " ")
    value = re.sub(r"[^\w\s:/.-]+", " ", value)
    return " ".join(value.split())


def _get_field(dataset: CanonicalDataset, path: str) -> str:
    value: Any = dataset
    for part in path.split("."):
        value = getattr(value, part, None)
        if value is None:
            return ""
    return str(value)


def search_datasets(
    datasets: list[CanonicalDataset],
    query: str,
) -> list[dict[str, object]]:
    """Search canonical datasets using a transparent weighted text match.

    All query terms must occur somewhere in the indexed metadata. Results are
    ranked by weighted field matches. This is intentionally small and
    dependency-free for the first catalog MVP.
    """

    normalized_query = _normalize(query)
    terms = [term for term in normalized_query.split() if term]
    if not terms:
        return []

    results: list[dict[str, object]] = []

    for dataset in datasets:
        fields = {
            path: _normalize(_get_field(dataset, path))
            for path, _ in _FIELD_WEIGHTS
        }
        searchable_text = " ".join(fields.values())
        if not all(term in searchable_text for term in terms):
            continue

        score = 0
        matched_fields: list[str] = []
        for path, weight in _FIELD_WEIGHTS:
            field_text = fields[path]
            field_hits = sum(term in field_text for term in terms)
            if field_hits:
                score += weight * field_hits
                matched_fields.append(path)

        results.append(
            {
                "score": score,
                "matched_fields": matched_fields,
                "dataset": dataset.model_dump(),
            }
        )

    results.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item["dataset"]["title"]),  # type: ignore[index]
        )
    )
    return results
