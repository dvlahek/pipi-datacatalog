#!/usr/bin/env python3
"""Analyze the frozen three-rater C2 human answer-drift audit.

Run only after all three blinded CSVs are completed independently. Outputs are
publication-safe aggregates plus a local freeze bound to the rated files.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "results" / "second_corpus_human_audit_v1"
PRIVATE_SAMPLE = DIR / "human_audit_sampling_PRIVATE.json"
PACKET_FREEZE = DIR / "human_audit_packet_freeze.json"
JUDGMENTS = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "qwen_answer_pairs_v2_judgments_frozen.jsonl"
PROTOCOL = ROOT / "docs" / "second_corpus_human_audit_protocol_v1.md"
RATER_FILES = {
    "colleague_1": DIR / "c2_human_audit_colleague_1.csv",
    "colleague_2": DIR / "c2_human_audit_colleague_2.csv",
    "author": DIR / "c2_human_audit_author.csv",
}
EXPECTED_JUDGMENTS_SHA = "61a82e092fc1ea62887061ada03c19c49fb4810332b8cb2a2f533e5acbd3b144"


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise RuntimeError(f"invalid JSONL {path}:{line_no}: {exc}") from exc
    return rows


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_rater_csv(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"missing completed rater file: {path}")
    out = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"audit_id", "query", "answer_A", "answer_B", "human_grade_0_3", "notes"}
        if set(reader.fieldnames or []) != required:
            raise RuntimeError(f"unexpected CSV columns in {path}: {reader.fieldnames}")
        for line_no, row in enumerate(reader, 2):
            aid = str(row["audit_id"]).strip()
            if not aid or aid in out:
                raise RuntimeError(f"duplicate/blank audit_id in {path}:{line_no}")
            raw = str(row["human_grade_0_3"]).strip()
            if raw not in {"0", "1", "2", "3"}:
                raise RuntimeError(f"grade must be 0,1,2,3 in {path}:{line_no}; got {raw!r}")
            out[aid] = {
                "grade": int(raw),
                "query": str(row["query"]),
                "answer_A": str(row["answer_A"]),
                "answer_B": str(row["answer_B"]),
                "notes": str(row.get("notes") or ""),
            }
    if len(out) != 44:
        raise RuntimeError(f"expected 44 ratings in {path}, got {len(out)}")
    return out


def qwk(a: list[int], b: list[int], k: int = 4) -> float:
    if len(a) != len(b) or not a:
        return float("nan")
    n = len(a)
    observed = [[0.0] * k for _ in range(k)]
    hist_a = [0.0] * k
    hist_b = [0.0] * k
    for x, y in zip(a, b):
        observed[x][y] += 1.0
        hist_a[x] += 1.0
        hist_b[y] += 1.0
    denom_scale = float((k - 1) ** 2)
    num = 0.0
    den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / denom_scale
            num += w * observed[i][j]
            expected = hist_a[i] * hist_b[j] / n
            den += w * expected
    if den == 0.0:
        return 1.0 if num == 0.0 else 0.0
    return 1.0 - num / den


def pair_agreement(a: list[int], b: list[int]) -> dict[str, Any]:
    n = len(a)
    exact = sum(x == y for x, y in zip(a, b))
    within = sum(abs(x - y) <= 1 for x, y in zip(a, b))
    binary = sum((x >= 2) == (y >= 2) for x, y in zip(a, b))
    return {
        "n": n,
        "exact_agreement_count": exact,
        "exact_agreement_rate": exact / n,
        "within_one_count": within,
        "within_one_rate": within / n,
        "quadratic_weighted_kappa": qwk(a, b),
        "binary_material_agreement_count": binary,
        "binary_material_agreement_rate": binary / n,
    }


def grade_counts(values: list[int]) -> dict[str, int]:
    return {str(g): sum(v == g for v in values) for g in range(4)}


def confusion_binary(human: list[int], model: list[int]) -> list[list[int]]:
    # rows human non-material/material; cols model non-material/material
    out = [[0, 0], [0, 0]]
    for h, m in zip(human, model):
        out[1 if h >= 2 else 0][1 if m >= 2 else 0] += 1
    return out


def wilson95(k: int, n: int) -> list[float]:
    if n <= 0:
        return [float("nan"), float("nan")]
    z = 1.959963984540054
    p = k / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [max(0.0, centre-half), min(1.0, centre+half)]


def main() -> None:
    for p in (PRIVATE_SAMPLE, PACKET_FREEZE, JUDGMENTS, PROTOCOL):
        if not p.is_file():
            raise RuntimeError(f"missing required frozen input: {p}")
    if sha_file(JUDGMENTS) != EXPECTED_JUDGMENTS_SHA:
        raise RuntimeError("frozen C2 primary judgments SHA mismatch")
    freeze = load_json(PACKET_FREEZE)
    if freeze.get("status") != "FROZEN_BEFORE_ANY_C2_HUMAN_RATINGS" or int(freeze.get("sample_count") or 0) != 44:
        raise RuntimeError("human-audit packet freeze mismatch")
    if freeze.get("protocol_sha256") != sha_file(PROTOCOL):
        raise RuntimeError("human-audit protocol changed after packet freeze")
    if freeze.get("private_sampling_manifest_sha256") != sha_file(PRIVATE_SAMPLE):
        raise RuntimeError("private sampling manifest changed after packet freeze")

    private = load_json(PRIVATE_SAMPLE)
    sample_rows = list(private.get("rows") or [])
    if len(sample_rows) != 44:
        raise RuntimeError("private sample does not contain 44 rows")
    sample_by_id = {str(r["audit_id"]): r for r in sample_rows}
    if len(sample_by_id) != 44:
        raise RuntimeError("duplicate audit IDs in private sample")

    ratings = {role: read_rater_csv(path) for role, path in RATER_FILES.items()}
    expected_ids = set(sample_by_id)
    for role, rows in ratings.items():
        if set(rows) != expected_ids:
            raise RuntimeError(f"audit IDs differ for {role}")
        for aid, row in rows.items():
            fingerprint = sha_text("\0".join([row["query"], row["answer_A"], row["answer_B"]]))
            if fingerprint != sample_by_id[aid]["content_fingerprint_sha256"]:
                raise RuntimeError(f"blinded content changed in {role} {aid}")

    llm_rows = load_jsonl(JUDGMENTS)
    llm_by_qid = {str(r["query_id"]): int(r["grade"]) for r in llm_rows}
    if len(llm_by_qid) != 81:
        raise RuntimeError("unexpected frozen LLM judgment count")

    audit_ids = [str(r["audit_id"]) for r in sample_rows]
    c1 = [ratings["colleague_1"][aid]["grade"] for aid in audit_ids]
    c2 = [ratings["colleague_2"][aid]["grade"] for aid in audit_ids]
    au = [ratings["author"][aid]["grade"] for aid in audit_ids]
    consensus = [int(statistics.median([x, y, z])) for x, y, z in zip(c1, c2, au)]
    model = [llm_by_qid[str(sample_by_id[aid]["query_id"])] for aid in audit_ids]
    strict_mask = [sample_by_id[aid]["stratum"] == "strict_hidden" for aid in audit_ids]

    def subset(values: list[int], mask: list[bool]) -> list[int]:
        return [v for v, keep in zip(values, mask) if keep]

    strict_consensus = subset(consensus, strict_mask)
    strict_model = subset(model, strict_mask)
    if len(strict_consensus) != 19:
        raise RuntimeError("strict hidden audit subset is not 19")

    material_n = sum(g >= 2 for g in consensus)
    strict_material_n = sum(g >= 2 for g in strict_consensus)
    colleague_binary_disagree = [((x >= 2) != (y >= 2)) for x, y in zip(c1, c2)]
    author_dependent_count = sum(colleague_binary_disagree)

    pairwise = {
        "colleague_1_vs_colleague_2": pair_agreement(c1, c2),
        "colleague_1_vs_author": pair_agreement(c1, au),
        "colleague_2_vs_author": pair_agreement(c2, au),
    }
    human_vs_llm = pair_agreement(consensus, model)
    human_vs_llm["binary_confusion_rows_human_cols_llm_nonmaterial_material"] = confusion_binary(consensus, model)
    strict_human_vs_llm = pair_agreement(strict_consensus, strict_model)
    strict_human_vs_llm["binary_confusion_rows_human_cols_llm_nonmaterial_material"] = confusion_binary(strict_consensus, strict_model)

    result = {
        "artifact": "SECOND_CORPUS_C2_HUMAN_AUDIT_RESULTS_V1",
        "scientific_status": "post-hoc human validation; does not replace frozen C2 endpoints or LLM judgments",
        "sample": {
            "n": 44,
            "strict_hidden_census_n": 19,
            "control_validation_n": 25,
            "control_note": "controls are deterministic validation cases and are not an unweighted prevalence sample of all 81 C2 answer pairs",
        },
        "assessors": {
            "count": 3,
            "roles": ["colleague_1", "colleague_2", "study_author"],
            "all_external_independent": False,
            "ratings_completed_separately": True,
        },
        "three_rater_consensus": {
            "rule": "ordinal median of three grades; material if median >= 2",
            "grade_counts": grade_counts(consensus),
            "material_count": material_n,
            "material_rate": material_n / 44,
            "material_wilson95": wilson95(material_n, 44),
            "unanimous_ordinal_count": sum(x == y == z for x, y, z in zip(c1, c2, au)),
            "unanimous_ordinal_rate": sum(x == y == z for x, y, z in zip(c1, c2, au)) / 44,
            "unanimous_binary_count": sum((x >= 2) == (y >= 2) == (z >= 2) for x, y, z in zip(c1, c2, au)),
            "unanimous_binary_rate": sum((x >= 2) == (y >= 2) == (z >= 2) for x, y, z in zip(c1, c2, au)) / 44,
        },
        "strict_hidden_19": {
            "definition": "dataset Jaccard@10 = 1 and chunk churn@10 > 0 within the context-feasible C2 answer set",
            "n": 19,
            "human_consensus_grade_counts": grade_counts(strict_consensus),
            "human_material_count": strict_material_n,
            "human_material_rate": strict_material_n / 19,
            "human_material_wilson95": wilson95(strict_material_n, 19),
            "frozen_llm_material_count": sum(g >= 2 for g in strict_model),
            "frozen_llm_material_rate": sum(g >= 2 for g in strict_model) / 19,
            "human_vs_frozen_llm": strict_human_vs_llm,
        },
        "pairwise_human_agreement": pairwise,
        "colleague_only_sensitivity": {
            "colleague_1_vs_colleague_2": pairwise["colleague_1_vs_colleague_2"],
            "binary_material_disagreement_count": author_dependent_count,
            "binary_material_disagreement_rate": author_dependent_count / 44,
            "author_vote_determines_three_rater_binary_consensus_count": author_dependent_count,
        },
        "human_consensus_vs_frozen_primary_llm": human_vs_llm,
        "input_sha256": {
            "protocol": sha_file(PROTOCOL),
            "packet_freeze": sha_file(PACKET_FREEZE),
            "private_sample": sha_file(PRIVATE_SAMPLE),
            "frozen_primary_llm_judgments": sha_file(JUDGMENTS),
            **{role: sha_file(path) for role, path in RATER_FILES.items()},
        },
    }

    out_json = DIR / "human_audit_publication_safe_summary.json"
    out_md = DIR / "human_audit_publication_safe_summary.md"
    analysis_freeze = DIR / "human_audit_analysis_freeze.json"
    if analysis_freeze.exists():
        raise RuntimeError("C2_HUMAN_AUDIT_ANALYSIS_ALREADY_FROZEN; refusing overwrite")
    atomic_json(out_json, result)
    md = f"""# C2 human answer-drift audit V1\n\nScientific status: post-hoc human validation.\n\n- Human raters: three (two colleagues and the study author).\n- Audit sample: 44 pairs = all 19 strict hidden-drift pairs + 25 deterministic controls.\n- Three-rater consensus material drift: **{material_n}/44 = {100*material_n/44:.1f}%**.\n- Strict hidden-drift census: **{strict_material_n}/19 = {100*strict_material_n/19:.1f}%** human-consensus material drift.\n- Frozen primary LLM on the same 19 cases: **{sum(g >= 2 for g in strict_model)}/19** material.\n- Colleague-only QWK: **{pairwise['colleague_1_vs_colleague_2']['quadratic_weighted_kappa']:.3f}**.\n- Colleague binary material disagreement: **{author_dependent_count}/44** cases; these are the cases in which the author's third vote determines the three-rater binary consensus.\n- Human-consensus vs frozen primary LLM QWK: **{human_vs_llm['quadratic_weighted_kappa']:.3f}**.\n\nThe 25 controls are validation cases, not a prevalence sample of the full 81-pair answer set.\n"""
    out_md.write_text(md, encoding="utf-8")
    freeze_out = {
        "artifact": "SECOND_CORPUS_C2_HUMAN_AUDIT_ANALYSIS_FREEZE_V1",
        "status": "FROZEN_AFTER_ALL_THREE_HUMAN_RATINGS",
        "analyzer_sha256": sha_file(Path(__file__)),
        "summary_json_sha256": sha_file(out_json),
        "summary_md_sha256": sha_file(out_md),
        "rated_file_sha256": {role: sha_file(path) for role, path in RATER_FILES.items()},
        "sample_count": 44,
        "strict_hidden_count": 19,
    }
    atomic_json(analysis_freeze, freeze_out)

    print("C2_HUMAN_AUDIT_ANALYSIS_FROZEN")
    print(json.dumps({
        "consensus_material": f"{material_n}/44",
        "strict_hidden_human_material": f"{strict_material_n}/19",
        "strict_hidden_frozen_llm_material": f"{sum(g >= 2 for g in strict_model)}/19",
        "colleague_qwk": pairwise["colleague_1_vs_colleague_2"]["quadratic_weighted_kappa"],
        "author_dependent_binary_cases": author_dependent_count,
        "human_vs_llm_qwk": human_vs_llm["quadratic_weighted_kappa"],
        "summary_json_sha256": sha_file(out_json),
        "analysis_freeze_sha256": sha_file(analysis_freeze),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
