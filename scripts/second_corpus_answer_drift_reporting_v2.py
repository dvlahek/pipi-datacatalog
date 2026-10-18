#!/usr/bin/env python3
"""Recompute publication-safe aggregate C2 Qwen V2 answer-drift results.

The script intentionally does not publish answer text, evidence text, or the
private A/B orientation. It verifies the frozen local inputs and emits only
aggregate descriptive results for the context-feasible C2 answer subset.

Scientific status: post-confirmatory descriptive extension.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible"
DEFAULT_PER_QUERY = ROOT / "results" / "second_corpus_confirmation_v1" / "per_query_metrics.jsonl"

EXPECTED = {
    "blinded_packet": "0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa",
    "private_mapping": "4adca69ad1f496536e967f7174d8214296686214aebc50ba0945ce31c2f93fbb",
    "judgments": "61a82e092fc1ea62887061ada03c19c49fb4810332b8cb2a2f533e5acbd3b144",
    "per_query_metrics": "794be7b504060580910fbc7f8e13274c604cfbdcffaa33781c333b7ad7e94b0b",
}
EXPECTED_PAIR_COUNT = 81
EXPECTED_FULL_C2_QUERY_COUNT = 96


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise RuntimeError(f"invalid JSONL {path}:{line_no}: {exc}") from exc
    return rows


def verify_sha(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    got = sha256_file(path)
    if got != expected:
        raise RuntimeError(f"{label} SHA mismatch: expected {expected}, got {got}")
    return got


def wilson95(k: int, n: int) -> list[float]:
    if n <= 0:
        return [float("nan"), float("nan")]
    z = 1.959963984540054
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / den
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / den
    return [max(0.0, centre - half), min(1.0, centre + half)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grades = Counter(int(r["grade"]) for r in rows)
    material = sum(1 for r in rows if int(r["grade"]) >= 2)
    n = len(rows)
    return {
        "n": n,
        "grade_counts": {str(g): grades.get(g, 0) for g in range(4)},
        "material_count": material,
        "material_rate": material / n if n else None,
        "material_wilson95": wilson95(material, n),
    }


def grouped_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    return {key: summarize(groups[key]) for key in sorted(groups)}


def isclose(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blinded-packet", type=Path, default=DEFAULT_DIR / "qwen_answer_pairs_v2_blinded.json")
    ap.add_argument("--mapping", type=Path, default=DEFAULT_DIR / "qwen_answer_pairs_v2_mapping_PRIVATE.json")
    ap.add_argument("--judgments", type=Path, default=DEFAULT_DIR / "qwen_answer_pairs_v2_judgments_frozen.jsonl")
    ap.add_argument("--per-query", type=Path, default=DEFAULT_PER_QUERY)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_DIR / "c2_qwen_v2_publication_safe_summary.json")
    ap.add_argument("--out-md", type=Path, default=DEFAULT_DIR / "c2_qwen_v2_publication_safe_summary.md")
    args = ap.parse_args()

    input_hashes = {
        "blinded_packet": verify_sha(args.blinded_packet, EXPECTED["blinded_packet"], "blinded packet"),
        "private_mapping": verify_sha(args.mapping, EXPECTED["private_mapping"], "private mapping"),
        "judgments": verify_sha(args.judgments, EXPECTED["judgments"], "judgments"),
        "per_query_metrics": verify_sha(args.per_query, EXPECTED["per_query_metrics"], "per-query metrics"),
    }

    packet = load_json(args.blinded_packet)
    mapping = load_json(args.mapping)
    judgments = load_jsonl(args.judgments)
    per_query = load_jsonl(args.per_query)

    if int(packet.get("pair_count", 0)) != EXPECTED_PAIR_COUNT:
        raise RuntimeError("unexpected blinded pair count")
    if int(mapping.get("pair_count", 0)) != EXPECTED_PAIR_COUNT:
        raise RuntimeError("unexpected mapping pair count")
    if len(judgments) != EXPECTED_PAIR_COUNT:
        raise RuntimeError("unexpected judgment row count")
    if len(per_query) != EXPECTED_FULL_C2_QUERY_COUNT:
        raise RuntimeError("unexpected C2 per-query metric count")

    pair_by_qid = {str(r["query_id"]): r for r in packet["pairs"]}
    map_by_qid = {str(r["query_id"]): r for r in mapping["rows"]}
    judgment_by_qid = {str(r["query_id"]): r for r in judgments}
    metric_by_qid = {str(r["query_id"]): r for r in per_query}
    if not (len(pair_by_qid) == len(map_by_qid) == len(judgment_by_qid) == EXPECTED_PAIR_COUNT):
        raise RuntimeError("duplicate or missing query identities in answer-drift inputs")
    if set(pair_by_qid) != set(map_by_qid) or set(pair_by_qid) != set(judgment_by_qid):
        raise RuntimeError("query identity mismatch across blinded/mapping/judgment inputs")

    joined: list[dict[str, Any]] = []
    for qid in sorted(pair_by_qid):
        pair = pair_by_qid[qid]
        mp = map_by_qid[qid]
        judge = judgment_by_qid[qid]
        metric = metric_by_qid.get(qid)
        if metric is None:
            raise RuntimeError(f"missing per-query metric for {qid}")
        if str(pair["pair_id"]) != str(mp["pair_id"]) or str(pair["pair_id"]) != str(judge["pair_id"]):
            raise RuntimeError(f"pair identity mismatch for {qid}")
        grade = int(judge["grade"])
        if grade not in (0, 1, 2, 3):
            raise RuntimeError(f"invalid grade for {qid}: {grade}")
        joined.append({
            "query_id": qid,
            "theme": str(pair["theme"]),
            "query_type": str(pair["query_type"]),
            "grade": grade,
            "material": grade >= 2,
            "dataset_churn_at_10": float(metric["dataset_churn_at_10"]),
            "dataset_jaccard_at_10": float(metric["dataset_jaccard_at_10"]),
            "chunk_churn_at_10": float(metric["chunk_churn_at_10"]),
            "chunk_jaccard_at_10": float(metric["chunk_jaccard_at_10"]),
        })

    directional_hidden = [r for r in joined if isclose(r["dataset_churn_at_10"], 0.0) and r["chunk_churn_at_10"] > 0.0]
    exact_dataset_hidden = [r for r in joined if isclose(r["dataset_jaccard_at_10"], 1.0) and r["chunk_churn_at_10"] > 0.0]
    exact_same = [r for r in joined if isclose(r["dataset_jaccard_at_10"], 1.0) and isclose(r["chunk_jaccard_at_10"], 1.0)]

    rho, p = spearmanr([r["chunk_churn_at_10"] for r in joined], [r["grade"] for r in joined])
    mat = [r["chunk_churn_at_10"] for r in joined if r["material"]]
    nonmat = [r["chunk_churn_at_10"] for r in joined if not r["material"]]

    result = {
        "artifact": "SECOND_CORPUS_C2_QWEN_V2_PUBLICATION_SAFE_SUMMARY",
        "scientific_status": "post-confirmatory descriptive context-feasible subset",
        "input_sha256": input_hashes,
        "coverage": {
            "included_query_count": EXPECTED_PAIR_COUNT,
            "full_c2_query_count": EXPECTED_FULL_C2_QUERY_COUNT,
            "coverage_rate": EXPECTED_PAIR_COUNT / EXPECTED_FULL_C2_QUERY_COUNT,
        },
        "overall_answer_drift": summarize(joined),
        "by_theme": grouped_summary(joined, "theme"),
        "by_query_type": grouped_summary(joined, "query_type"),
        "directional_hidden_drift": {
            "definition": "dataset_churn_at_10 == 0 and chunk_churn_at_10 > 0",
            **summarize(directional_hidden),
        },
        "exact_dataset_set_hidden_drift": {
            "definition": "dataset_jaccard_at_10 == 1 and chunk_churn_at_10 > 0",
            **summarize(exact_dataset_hidden),
        },
        "exact_dataset_and_chunk_set_same": {
            "definition": "dataset_jaccard_at_10 == 1 and chunk_jaccard_at_10 == 1",
            **summarize(exact_same),
        },
        "exploratory_chunk_churn_vs_ordinal_grade_spearman": {
            "rho": float(rho),
            "p_two_sided": float(p),
            "status": "exploratory descriptive association; not a frozen C2 confirmatory endpoint",
        },
        "mean_chunk_churn": {
            "material": sum(mat) / len(mat),
            "non_material": sum(nonmat) / len(nonmat),
        },
        "guardrails": [
            "The 81-query answer-drift result is not an estimate for all 96 C2 queries without the context-feasible-subset qualification.",
            "C2 answer drift is post-confirmatory descriptive evidence and does not alter C2 H1/H2/H3.",
            "The semantic-change grade is symmetric and does not establish that one retrieval profile produced a more correct answer.",
            "Cross-corpus C1-C2 differences in answer-drift magnitude are descriptive; no cross-corpus inferential comparison was pre-specified.",
        ],
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    o = result["overall_answer_drift"]
    d = result["directional_hidden_drift"]
    e = result["exact_dataset_set_hidden_drift"]
    md = f"""# C2 Qwen V2 publication-safe summary\n\n**Scientific status:** post-confirmatory descriptive context-feasible subset\n\n- Coverage: **{EXPECTED_PAIR_COUNT}/{EXPECTED_FULL_C2_QUERY_COUNT} = {100*EXPECTED_PAIR_COUNT/EXPECTED_FULL_C2_QUERY_COUNT:.2f}%**\n- Material answer drift: **{o['material_count']}/{o['n']} = {100*o['material_rate']:.2f}%**\n- Directional hidden drift (`dataset churn = 0`, `chunk churn > 0`): **{d['material_count']}/{d['n']} = {100*d['material_rate']:.2f}%** material answers\n- Strict hidden drift (`dataset Jaccard@10 = 1`, `chunk churn > 0`): **{e['material_count']}/{e['n']} = {100*e['material_rate']:.2f}%** material answers\n- Chunk churn vs. ordinal answer grade: **Spearman rho = {float(rho):.3f}, p = {float(p):.4f}** (exploratory)\n\nThis summary contains no answer text, evidence text, or private A/B orientation.\n"""
    args.out_md.write_text(md, encoding="utf-8")

    print("C2_QWEN_V2_PUBLICATION_SAFE_REPORT_PASS")
    print(json.dumps({
        "overall_material": f"{o['material_count']}/{o['n']}",
        "directional_hidden_material": f"{d['material_count']}/{d['n']}",
        "exact_dataset_hidden_material": f"{e['material_count']}/{e['n']}",
        "output_json_sha256": sha256_file(args.out_json),
        "output_md_sha256": sha256_file(args.out_md),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
