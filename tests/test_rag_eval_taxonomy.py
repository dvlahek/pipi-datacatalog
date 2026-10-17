import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "config" / "rag_eval_queries.json"
TAXONOMY = ROOT / "config" / "rag_eval_taxonomy.json"


def test_pilot_taxonomy_covers_frozen_query_set_exactly() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))

    case_ids = {str(case["id"]) for case in cases}
    taxonomy_cases = dict(taxonomy["cases"])

    assert set(taxonomy_cases) == case_ids
    assert len(case_ids) == 16


def test_pilot_taxonomy_has_required_analysis_axes() -> None:
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    required = {"source_family", "language", "language_relation", "query_type"}

    for case_id, labels in taxonomy["cases"].items():
        assert required.issubset(labels), case_id
        assert all(str(labels[key]).strip() for key in required), case_id


def test_cross_language_cases_are_explicit_not_inferred_from_query_language() -> None:
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))["cases"]

    assert taxonomy["csv-temperature-b-hr"]["language"] == "hr"
    assert taxonomy["csv-temperature-b-hr"]["language_relation"] == "cross-language"
    assert taxonomy["csv-humidity-a-hr"]["language_relation"] == "cross-language"
    assert taxonomy["foi-gender-equality"]["language"] == "hr"
    assert taxonomy["foi-gender-equality"]["language_relation"] == "same-language"
