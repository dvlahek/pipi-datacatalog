#!/usr/bin/env python3
"""Publication-safe post-hoc diagnostics for the frozen second corpus.

Produces no source text. It reports structure/context distributions, authoring-
source recovery diagnostics, and one pre-declared exploratory retrieved-set
multiplicity association. Frozen H1/H2/H3 are not recomputed or replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_9_100"
RETRIEVAL = ROOT / "results" / "second_corpus_retrieval_v1"
CONFIRMATION = ROOT / "results" / "second_corpus_confirmation_v1"
CONTEXT_AUDIT = ROOT / "results" / "second_corpus_answer_drift_v1" / "context_compatibility_audit_v1.json"
V2_INPUT = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2.json"
OUT = ROOT / "results" / "second_corpus_posthoc_diagnostics_v1"

EXPECTED = {
    "selected_manifest": "a2454093e05c3308fb0b42606fc9d59b472cb0307992c21adea521c637b63a27",
    "chunk_manifest": "fe336487e2c7cb7dd37225df13612936c7972bb24959e90b43f0a2fe47285172",
    "logical_chunk_order": "05dcd6aa4cf0e23b932dc691ad5861fe2f4f5971adc66968556993e03e09e00a",
    "retrieval_runs": "5138ae7d90906709b1b5f8792560c8ddde95b57a01614cafbc951e7542294383",
    "per_query_metrics": "794be7b504060580910fbc7f8e13274c604cfbdcffaa33781c333b7ad7e94b0b",
    "context_audit": "4af1779c50cc05a7a688fb08014f1a3e7f60cdd37bea1a2ec2523ed3ba7937cc",
    "v2_input": "43af919a2b6321858e052f6e8dd0ca51a91d08c7ff4f6745153a9902655a824a",
}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def require(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    got = sha_file(path)
    if got != expected:
        raise RuntimeError(f"{label} SHA mismatch expected={expected} actual={got}")


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def dist_summary(values: list[float]) -> dict[str, Any]:
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    return {
        "n": len(values),
        "median": statistics.median(values) if values else None,
        "q1": q1 if values else None,
        "q3": q3 if values else None,
        "iqr": (q3 - q1) if values else None,
        "p95": percentile(values, 0.95) if values else None,
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--retrieval", type=Path, default=RETRIEVAL)
    ap.add_argument("--confirmation", type=Path, default=CONFIRMATION)
    ap.add_argument("--context-audit", type=Path, default=CONTEXT_AUDIT)
    ap.add_argument("--v2-input", type=Path, default=V2_INPUT)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    selected_path = args.corpus / "selected_corpus_manifest.jsonl"
    chunk_path = args.corpus / "chunk_manifest.jsonl"
    logical_path = args.retrieval / "logical_chunk_order.jsonl"
    runs_path = args.retrieval / "primary_retrieval_runs.jsonl"
    pq_path = args.confirmation / "per_query_metrics.jsonl"
    require(selected_path, EXPECTED["selected_manifest"], "selected manifest")
    require(chunk_path, EXPECTED["chunk_manifest"], "chunk manifest")
    require(logical_path, EXPECTED["logical_chunk_order"], "logical chunk order")
    require(runs_path, EXPECTED["retrieval_runs"], "retrieval runs")
    require(pq_path, EXPECTED["per_query_metrics"], "per-query metrics")
    require(args.context_audit, EXPECTED["context_audit"], "context audit")
    require(args.v2_input, EXPECTED["v2_input"], "V2 answer input")

    selected = read_jsonl(selected_path)
    chunks = read_jsonl(chunk_path)
    logical = read_jsonl(logical_path)
    runs = read_jsonl(runs_path)
    per_query = read_jsonl(pq_path)
    context = read_json(args.context_audit)
    v2_input = read_json(args.v2_input)
    if len(selected) != 400 or len(chunks) != 44520 or len(logical) != 44491 or len(runs) != 192 or len(per_query) != 96:
        raise RuntimeError("unexpected frozen row counts")

    format_by_key: dict[tuple[str, str, str], str] = {}
    record_chunk_counts = []
    for row in selected:
        total = 0
        for dist in row.get("distributions") or []:
            key = (str(row["theme"]), str(row["dataset_id"]), str(dist["distribution_id"]))
            format_by_key[key] = str(dist["format"]).upper()
            total += int(dist["chunk_count"])
        record_chunk_counts.append(total)

    char_by_format: dict[str, list[float]] = defaultdict(list)
    for row in chunks:
        key = (str(row["theme"]), str(row["dataset_id"]), str(row["distribution_id"]))
        fmt = format_by_key.get(key)
        if fmt is None:
            raise RuntimeError(f"chunk references unknown distribution {key}")
        char_by_format[fmt].append(float(row["character_count"]))
    chunk_length_by_format = {}
    for fmt in sorted(char_by_format):
        vals = char_by_format[fmt]
        chunk_length_by_format[fmt] = {
            **dist_summary(vals),
            "count_gt_1200_chars": sum(v > 1200 for v in vals),
            "fraction_gt_1200_chars": sum(v > 1200 for v in vals) / len(vals),
        }

    logical_chunks_per_dataset = Counter(str(r["dataset_id"]) for r in logical)
    unique_dataset_chunk_counts = list(logical_chunks_per_dataset.values())

    all_token_rows = list(context.get("all_conditions") or [])
    input_tokens = [int(r["input_tokens"]) for r in all_token_rows]
    included_tokens = []
    for case in v2_input.get("cases") or []:
        for pid in ("hybrid-e5-content-v1", "hybrid-e5-metadata-v1"):
            included_tokens.append(int(case["audited_input_tokens"][pid]))

    by_profile = defaultdict(list)
    retrieved_density_by_query_profile: dict[tuple[str, str], float] = {}
    for run in runs:
        qid = str(run["query_id"])
        pid = str(run["profile_id"])
        targets = [str(x) for x in run.get("source_dataset_ids") or []]
        target_set = set(targets)
        evidence = list(run.get("ordered_evidence") or [])
        ranks = [int(e["rank"]) for e in evidence if str(e["dataset_id"]) in target_set]
        unique_retrieved = []
        seen = set()
        for e in evidence:
            ds = str(e["dataset_id"])
            if ds not in seen:
                seen.add(ds)
                unique_retrieved.append(ds)
        coverage = (len(target_set & set(unique_retrieved)) / len(target_set)) if target_set else None
        by_profile[pid].append({
            "hit": bool(ranks),
            "rr": (1.0 / min(ranks)) if ranks else 0.0,
            "target_coverage": coverage,
        })
        densities = [math.log1p(logical_chunks_per_dataset[ds]) for ds in unique_retrieved]
        retrieved_density_by_query_profile[(qid, pid)] = statistics.fmean(densities) if densities else 0.0

    source_target = {}
    for pid, vals in sorted(by_profile.items()):
        source_target[pid] = {
            "query_count": len(vals),
            "any_authoring_source_hit_at_10": sum(v["hit"] for v in vals) / len(vals),
            "first_authoring_source_mrr_at_10": statistics.fmean(v["rr"] for v in vals),
            "mean_authoring_source_coverage_at_10": statistics.fmean(v["target_coverage"] for v in vals if v["target_coverage"] is not None),
            "interpretation": "descriptive authoring-source recovery; not a relevance-judged IR metric",
        }

    pq_by_id = {str(r["query_id"]): r for r in per_query}
    retrieved_density = []
    gaps = []
    for qid in sorted(pq_by_id):
        a = retrieved_density_by_query_profile[(qid, "hybrid-e5-content-v1")]
        b = retrieved_density_by_query_profile[(qid, "hybrid-e5-metadata-v1")]
        retrieved_density.append((a + b) / 2.0)
        gaps.append(float(pq_by_id[qid]["churn_gap_chunk_minus_dataset"]))
    rho, p = spearmanr(retrieved_density, gaps)

    result = {
        "artifact": "SECOND_CORPUS_POSTHOC_DIAGNOSTICS_V1",
        "scientific_status": "post-hoc descriptive/exploratory; frozen H1/H2/H3 unchanged",
        "input_sha256": {k: EXPECTED[k] for k in EXPECTED},
        "structure": {
            "record_count": len(selected),
            "unique_logical_dataset_count": len(logical_chunks_per_dataset),
            "physical_chunk_count": len(chunks),
            "logical_chunk_count": len(logical),
            "chunks_per_selected_record": dist_summary([float(x) for x in record_chunk_counts]),
            "logical_chunks_per_unique_dataset": dist_summary([float(x) for x in unique_dataset_chunk_counts]),
            "chunk_character_count_by_format": chunk_length_by_format,
        },
        "answer_context_tokens": {
            "all_192_frozen_conditions": dist_summary([float(x) for x in input_tokens]),
            "over_16384_input_only_count": int(context["input_only_over_context_count"]),
            "over_16384_with_reserved_output_count": int(context["prompt_plus_reserved_output_over_context_count"]),
            "max_single_evidence_text_chars_in_largest_audit_prompts": max(int(r.get("max_single_evidence_text_chars") or 0) for r in all_token_rows),
            "context_feasible_162_conditions": dist_summary([float(x) for x in included_tokens]),
        },
        "source_target_diagnostics": source_target,
        "retrieved_set_density_exploratory": {
            "definition": "for each profile, mean log1p(total logical chunks of each unique dataset appearing in top-10); query predictor is the average of the two profile-specific values",
            "outcome": "frozen chunk-minus-dataset churn gap",
            "n": 96,
            "spearman_rho": float(rho),
            "p_two_sided": float(p),
            "status": "post-hoc exploratory; does not replace frozen query-source H2",
        },
        "frozen_h2_reference": {
            "predictor": "mean log1p(chunks_per_dataset) of frozen query-authoring source dataset(s)",
            "spearman_rho": 0.1553934024,
            "holm_adjusted_p": 0.13058650685,
            "interpretation": "directionally positive, not statistically supported; not refuted",
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "posthoc_diagnostics_v1.json"
    md_path = args.out / "posthoc_diagnostics_v1.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    s_record = result["structure"]["chunks_per_selected_record"]
    s_ds = result["structure"]["logical_chunks_per_unique_dataset"]
    md = f"""# Second-corpus post-hoc diagnostics V1\n\nScientific status: post-hoc descriptive/exploratory. Frozen H1/H2/H3 are unchanged.\n\n- Chunks per selected record: median {s_record['median']:.1f}, IQR {s_record['q1']:.1f}-{s_record['q3']:.1f}, max {s_record['max']:.0f}.\n- Logical chunks per unique dataset: median {s_ds['median']:.1f}, IQR {s_ds['q1']:.1f}-{s_ds['q3']:.1f}, max {s_ds['max']:.0f}.\n- Frozen prompt-token audit: median {result['answer_context_tokens']['all_192_frozen_conditions']['median']:.1f}, max {result['answer_context_tokens']['all_192_frozen_conditions']['max']:.0f}; {result['answer_context_tokens']['over_16384_with_reserved_output_count']} conditions exceed the unchanged context budget with reserved output.\n- Retrieved-set density vs. chunk-minus-dataset gap: Spearman rho {float(rho):.3f}, p {float(p):.4g} (post-hoc exploratory).\n\nAuthoring-source recovery metrics and per-format chunk-length summaries are in the JSON artifact.\n"""
    md_path.write_text(md, encoding="utf-8")
    print("C2_POSTHOC_DIAGNOSTICS_PASS")
    print(json.dumps({
        "json_sha256": sha_file(json_path),
        "md_sha256": sha_file(md_path),
        "retrieved_density_rho": float(rho),
        "retrieved_density_p": float(p),
        "source_target_diagnostics": source_target,
        "chunks_per_record": s_record,
        "logical_chunks_per_unique_dataset": s_ds,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
