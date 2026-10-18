#!/usr/bin/env python3
"""Publication-safe robustness analysis for three blinded C2 Qwen V2 judges.

This script verifies the frozen blinded packet and three local judgment files,
then emits aggregate agreement and sensitivity summaries only. It never emits
answer text, evidence text, or hidden retrieval-profile identity.

Scientific status: post-confirmatory judging-robustness analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible"

EXPECTED = {
    "packet": "0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa",
    "chatgpt": "61a82e092fc1ea62887061ada03c19c49fb4810332b8cb2a2f533e5acbd3b144",
    "gemini": "e0c83139f02f598802d4895e70ce3d025db589b8193f434ea4cdf25fa1a1afe4",
    "claude": "7fdc956e7294e0fcd73455e58f583b37609980b3d216210a6047645f5ba3fccf",
}
PAIR_COUNT = 81


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
    z = 1.959963984540054
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / den
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / den
    return [centre - half, centre + half]


def quadratic_weighted_kappa(a: list[int], b: list[int], k: int = 4) -> float:
    n = len(a)
    observed = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[x][y] += 1
    ca = Counter(a)
    cb = Counter(b)
    num = 0.0
    den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) / (k - 1)) ** 2
            num += w * (observed[i][j] / n)
            den += w * ((ca[i] / n) * (cb[j] / n))
    if den == 0.0:
        raise RuntimeError("quadratic weighted kappa denominator is zero")
    return 1.0 - num / den


def judge_summary(grades: list[int]) -> dict[str, Any]:
    counts = Counter(grades)
    material = sum(g >= 2 for g in grades)
    return {
        "grade_counts": {str(i): counts.get(i, 0) for i in range(4)},
        "material_count": material,
        "n": len(grades),
        "material_rate": material / len(grades),
        "material_wilson95": wilson95(material, len(grades)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", type=Path, default=DEFAULT_DIR / "qwen_answer_pairs_v2_blinded.json")
    ap.add_argument("--chatgpt", type=Path, default=DEFAULT_DIR / "qwen_answer_pairs_v2_judgments_frozen.jsonl")
    ap.add_argument("--gemini", type=Path, default=DEFAULT_DIR / "c2_qwen_v2_judgments_gemini_v1.jsonl")
    ap.add_argument("--claude", type=Path, default=DEFAULT_DIR / "c2_qwen_v2_judgments_claude_v1.jsonl")
    ap.add_argument("--out-json", type=Path, default=DEFAULT_DIR / "c2_secondary_judge_robustness_results_v1.json")
    ap.add_argument("--out-md", type=Path, default=DEFAULT_DIR / "c2_secondary_judge_robustness_results_v1.md")
    args = ap.parse_args()

    verify_sha(args.packet, EXPECTED["packet"], "blinded packet")
    judge_paths = {
        "ChatGPT": (args.chatgpt, EXPECTED["chatgpt"]),
        "Gemini": (args.gemini, EXPECTED["gemini"]),
        "Claude": (args.claude, EXPECTED["claude"]),
    }
    for name, (path, expected) in judge_paths.items():
        verify_sha(path, expected, f"{name} judgments")

    packet = load_json(args.packet)
    expected_ids = [(str(r["pair_id"]), str(r["query_id"])) for r in packet["pairs"]]
    if len(expected_ids) != PAIR_COUNT:
        raise RuntimeError("unexpected packet pair count")

    rows: dict[str, list[dict[str, Any]]] = {}
    grades: dict[str, list[int]] = {}
    for name, (path, _) in judge_paths.items():
        rs = load_jsonl(path)
        ids = [(str(r.get("pair_id")), str(r.get("query_id"))) for r in rs]
        gs = [r.get("grade") for r in rs]
        if len(rs) != PAIR_COUNT or len(set(ids)) != PAIR_COUNT:
            raise RuntimeError(f"invalid row count or duplicate IDs for {name}")
        if ids != expected_ids:
            raise RuntimeError(f"packet order/identity mismatch for {name}")
        if not all(isinstance(g, int) and g in (0, 1, 2, 3) for g in gs):
            raise RuntimeError(f"invalid grade for {name}")
        rows[name] = rs
        grades[name] = [int(g) for g in gs]

    names = ["ChatGPT", "Gemini", "Claude"]
    pairwise: dict[str, Any] = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            left, right = names[i], names[j]
            a, b = grades[left], grades[right]
            pairwise[f"{left}__{right}"] = {
                "exact_ordinal_agreement": sum(x == y for x, y in zip(a, b)) / PAIR_COUNT,
                "within_one_grade_agreement": sum(abs(x - y) <= 1 for x, y in zip(a, b)) / PAIR_COUNT,
                "quadratic_weighted_kappa": quadratic_weighted_kappa(a, b),
                "binary_material_agreement": sum((x >= 2) == (y >= 2) for x, y in zip(a, b)) / PAIR_COUNT,
            }

    triples = list(zip(*(grades[n] for n in names)))
    medians = [sorted(t)[1] for t in triples]
    median_counts = Counter(medians)
    median_material = sum(g >= 2 for g in medians)
    material_votes = Counter(sum(g >= 2 for g in t) for t in triples)
    all_exact = sum(len(set(t)) == 1 for t in triples)
    binary_unanimous = sum(len(set(g >= 2 for g in t)) == 1 for t in triples)

    result = {
        "artifact": "SECOND_CORPUS_C2_QWEN_V2_SECONDARY_JUDGE_ROBUSTNESS_RESULTS_V1",
        "scientific_status": "post-confirmatory judging-robustness analysis",
        "input_sha256": {"packet": EXPECTED["packet"], **{k.lower(): v for k, v in EXPECTED.items() if k != "packet"}},
        "per_judge": {name: judge_summary(grades[name]) for name in names},
        "pairwise": pairwise,
        "three_judge": {
            "all_exact_ordinal_count": all_exact,
            "all_exact_ordinal_rate": all_exact / PAIR_COUNT,
            "binary_unanimity_count": binary_unanimous,
            "binary_unanimity_rate": binary_unanimous / PAIR_COUNT,
            "material_vote_count_distribution": {str(i): material_votes.get(i, 0) for i in range(4)},
            "median_grade_counts": {str(i): median_counts.get(i, 0) for i in range(4)},
            "median_grade_material_count": median_material,
            "median_grade_material_rate": median_material / PAIR_COUNT,
            "median_grade_material_wilson95": wilson95(median_material, PAIR_COUNT),
        },
        "interpretation": "Judge choice has little effect on the binary material-drift rate. The three-judge median/majority result is a pre-specified robustness summary and does not replace the original frozen ChatGPT endpoint.",
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    c = result["per_judge"]
    t = result["three_judge"]
    md = f"""# C2 Qwen V2 secondary-judge robustness\n\n**Scientific status:** post-confirmatory judging robustness.\n\n| Judge | Material | Rate |\n|---|---:|---:|\n| ChatGPT | {c['ChatGPT']['material_count']}/81 | {100*c['ChatGPT']['material_rate']:.2f}% |\n| Gemini | {c['Gemini']['material_count']}/81 | {100*c['Gemini']['material_rate']:.2f}% |\n| Claude | {c['Claude']['material_count']}/81 | {100*c['Claude']['material_rate']:.2f}% |\n\nThree-judge binary unanimity: **{t['binary_unanimity_count']}/81 = {100*t['binary_unanimity_rate']:.2f}%**.\n\nPre-specified median/majority sensitivity: **{t['median_grade_material_count']}/81 = {100*t['median_grade_material_rate']:.2f}% material drift**.\n\nThis analysis tests robustness to judge choice only and does not alter the frozen C2 retrieval endpoints or the original ChatGPT answer-drift endpoint.\n"""
    args.out_md.write_text(md, encoding="utf-8")

    print("C2_SECONDARY_JUDGE_ROBUSTNESS_PASS")
    print(json.dumps({
        "chatgpt_material": c["ChatGPT"]["material_count"],
        "gemini_material": c["Gemini"]["material_count"],
        "claude_material": c["Claude"]["material_count"],
        "median_material": t["median_grade_material_count"],
        "binary_unanimity": t["binary_unanimity_count"],
        "output_json_sha256": sha256_file(args.out_json),
        "output_md_sha256": sha256_file(args.out_md),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
