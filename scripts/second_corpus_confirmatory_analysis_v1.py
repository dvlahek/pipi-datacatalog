#!/usr/bin/env python3
"""Compute frozen C2 confirmatory H1/H2/H3 after primary retrieval freeze.

The statistical endpoints were frozen before C2 retrieval:
H1: paired two-sided Wilcoxon, chunk churn@10 vs dataset churn@10.
H2: two-sided Spearman between frozen M_q and chunk-minus-dataset churn gap.
H3: 100% exact ordered-evidence replay.

The script is bound to the frozen C2 retrieval hashes and never mutates corpus,
queries, embeddings, or retrieval ledgers.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Hashable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_9_100"
DEFAULT_QUERIES = ROOT / "results" / "second_corpus_queries_v1"
DEFAULT_RETRIEVAL = ROOT / "results" / "second_corpus_retrieval_v1"
DEFAULT_OUT = ROOT / "results" / "second_corpus_confirmation_v1"
DEFAULT_RUNNER = ROOT / "scripts" / "second_corpus_run_retrieval_v1.py"
DEFAULT_CONFIG = ROOT / "config" / "second_corpus_retrieval_v1.json"
DEFAULT_ADAPTER = ROOT / "docs" / "second_corpus_v2_preretrieval_adapter_10_distribution_identity.md"

EXPECTED = {
    "queries_sha256": "4257116b4d9ec417217b2030df58b5de3ba479fe0125f021a3ca50b7022699f7",
    "retrieval_input_freeze_sha256": "8ba8756b8896086ba52116d8ee0f849faecf65ada55c6cd84e5dbd64a133a1e1",
    "embedding_manifest_sha256": "0abdf9adb0c3ea0e43d1ea54ab563798b6b33c6126d240656fe8617c0fb32b76",
    "primary_retrieval_runs_sha256": "5138ae7d90906709b1b5f8792560c8ddde95b57a01614cafbc951e7542294383",
    "retrieval_config_sha256": "55527ac1d3e8bc99c81b339bc531aba7dfef0e77f2aeb0f296e06034c77887f1",
    "runner_script_sha256": "baddf83f50b62894f2cc9c8237ca5218a6a5b66f7090fd51158380dfdd67edbe",
    "adapter_sha256": "d315374f8b4a7eda34b2e8a181fd7c0a67349e03f3c435ff3c522dfd2ec8e4a2",
    "logical_chunk_order_sha256": "05dcd6aa4cf0e23b932dc691ad5861fe2f4f5971adc66968556993e03e09e00a",
    "hybrid-e5-content-v1": "04fd11fb3c56e9273f7b312a376d5c975a852489276f87fc796f7e0c716f7a45",
    "hybrid-e5-metadata-v1": "7b63711593b091d1c21a1548f1b672f4572c69b4fca380779114cad6163211e4",
}
PROFILE_A = "hybrid-e5-content-v1"
PROFILE_B = "hybrid-e5-metadata-v1"
TOP_K = 10


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise RuntimeError(f"invalid JSONL {path}:{line_no}: {exc}") from exc
    return rows


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, obj: object) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    atomic_text(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))


def verify_sha_manifest(path: Path) -> int:
    checked = 0
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise RuntimeError(f"invalid SHA manifest line {path}:{line_no}")
            expected, rel = parts
            target = Path(rel.strip().lstrip("*"))
            if not target.is_absolute():
                target = ROOT / target
            if not target.is_file():
                raise RuntimeError(f"SHA target missing: {target}")
            actual = sha_file(target)
            if actual != expected:
                raise RuntimeError(f"SHA mismatch {target}: expected={expected} actual={actual}")
            checked += 1
    return checked


def ordered_unique(values: list[Hashable]) -> list[Hashable]:
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def drift_from_keys(left: list[Hashable], right: list[Hashable]) -> dict[str, Any]:
    left_set, right_set = set(left), set(right)
    shared = left_set & right_set
    union = left_set | right_set
    available = min(len(left), len(right))
    retention = len(shared) / available if available else 1.0
    jaccard = len(shared) / len(union) if union else 1.0
    return {
        "left_count": len(left),
        "right_count": len(right),
        "shared_count": len(shared),
        "retention_at_10": retention,
        "churn_at_10": 1.0 - retention,
        "jaccard_at_10": jaccard,
        "top1_same": bool(left and right and left[0] == right[0]),
    }


def chunk_key(e: dict) -> str:
    return str(e["logical_chunk_identity_sha256"])


def distribution_key(e: dict) -> str:
    return str(e["distribution_identity_sha256"])


def dataset_key(e: dict) -> str:
    return str(e["dataset_id"])


def drift_layers(left: list[dict], right: list[dict]) -> dict[str, dict]:
    left, right = left[:TOP_K], right[:TOP_K]
    return {
        "chunk": drift_from_keys([chunk_key(e) for e in left], [chunk_key(e) for e in right]),
        "distribution": drift_from_keys(
            ordered_unique([distribution_key(e) for e in left]),
            ordered_unique([distribution_key(e) for e in right]),
        ),
        "dataset": drift_from_keys(
            ordered_unique([dataset_key(e) for e in left]),
            ordered_unique([dataset_key(e) for e in right]),
        ),
    }


def rank_biserial_paired(differences) -> dict[str, Any]:
    import numpy as np
    from scipy.stats import rankdata

    diff = np.asarray(differences, dtype=float)
    values = diff[diff != 0.0]
    if values.size == 0:
        return {
            "rank_biserial": 0.0,
            "positive_rank_sum": 0.0,
            "negative_rank_sum": 0.0,
            "nonzero_pairs": 0,
        }
    ranks = rankdata(np.abs(values), method="average")
    w_pos = float(ranks[values > 0].sum())
    w_neg = float(ranks[values < 0].sum())
    denom = w_pos + w_neg
    return {
        "rank_biserial": (w_pos - w_neg) / denom if denom else 0.0,
        "positive_rank_sum": w_pos,
        "negative_rank_sum": w_neg,
        "nonzero_pairs": int(values.size),
    }


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(ordered)
    adjusted = {}
    running = 0.0
    for index, (name, pvalue) in enumerate(ordered):
        raw = min(1.0, (m - index) * float(pvalue))
        running = max(running, raw)
        adjusted[name] = min(1.0, running)
    return adjusted


def aggregate_group(rows: list[dict]) -> dict[str, Any]:
    import numpy as np

    fields = [
        "chunk_churn_at_10",
        "distribution_churn_at_10",
        "dataset_churn_at_10",
        "churn_gap_chunk_minus_dataset",
        "chunk_jaccard_at_10",
        "distribution_jaccard_at_10",
        "dataset_jaccard_at_10",
    ]
    out = {"n": len(rows)}
    for field in fields:
        values = np.asarray([float(r[field]) for r in rows], dtype=float)
        out[f"mean_{field}"] = float(values.mean())
        out[f"median_{field}"] = float(np.median(values))
    out["top1_chunk_change_rate"] = sum(not r["top1_chunk_same"] for r in rows) / len(rows)
    out["top1_distribution_change_rate"] = sum(not r["top1_distribution_same"] for r in rows) / len(rows)
    out["top1_dataset_change_rate"] = sum(not r["top1_dataset_same"] for r in rows) / len(rows)
    hidden = sum(r["dataset_churn_at_10"] == 0.0 and r["chunk_churn_at_10"] > 0.0 for r in rows)
    out["hidden_chunk_drift_given_dataset_stability_count"] = hidden
    out["hidden_chunk_drift_given_dataset_stability_rate"] = hidden / len(rows)
    return out


def load_runner(path: Path):
    spec = importlib.util.spec_from_file_location("second_corpus_run_retrieval_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen retrieval runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_replay(*, runner, corpus: Path, queries_dir: Path, retrieval_dir: Path, config_path: Path, frozen_runs: dict[tuple[str, str], dict]) -> dict[str, Any]:
    import numpy as np

    config, selected, physical_chunks, queries = runner.load_and_validate_inputs(corpus, queries_dir, config_path)
    rows, logical_audit = runner.build_logical_chunks(selected, physical_chunks)
    if sha_file(retrieval_dir / "logical_chunk_order.jsonl") != EXPECTED["logical_chunk_order_sha256"]:
        raise RuntimeError("logical chunk order hash changed before replay")
    manifest = runner.verify_embedding_manifest(retrieval_dir)
    if sha_file(retrieval_dir / "embedding_manifest.json") != EXPECTED["embedding_manifest_sha256"]:
        raise RuntimeError("embedding manifest changed before replay")

    query_vectors = np.load(ROOT / manifest["query_embeddings"]["path"], allow_pickle=False).astype(np.float32, copy=False)
    matrices = {
        "content-v1": runner.load_embedding_matrix(manifest["profiles"]["content-v1"]),
        "metadata-v1": runner.load_embedding_matrix(manifest["profiles"]["metadata-v1"]),
    }
    norms = {name: np.linalg.norm(matrix, axis=1).astype(np.float32) for name, matrix in matrices.items()}
    normalized_texts = [runner.normalize_lexical(r["chunk_text"]) for r in rows]
    candidate_limit = int(config["retrieval"]["candidate_limit"])
    top_k = int(config["retrieval"]["top_k"])
    rrf_k = int(config["retrieval"]["rrf_k"])
    cap = int(config["retrieval"]["diversity_max_per_source"])
    profile_by_id = {p["profile_id"]: p for p in config["primary_profiles"]}

    total = exact = 0
    mismatches = []
    for qidx, query in enumerate(queries):
        lexical = runner.lexical_candidates(query["query_text"], normalized_texts, rows, candidate_limit)
        for profile_id in (PROFILE_A, PROFILE_B):
            total += 1
            p = profile_by_id[profile_id]
            vec = runner.vector_candidates(
                query_vectors[qidx], matrices[p["input_profile"]], norms[p["input_profile"]], rows, candidate_limit
            )
            fused = runner.rrf_fuse(lexical, vec, rows, candidate_limit, rrf_k)
            final = runner.diversify(fused, rows, top_k, cap)
            replay = [runner.evidence_record(rank, item, rows) for rank, item in enumerate(final, 1)]
            frozen = frozen_runs[(query["query_id"], profile_id)]["ordered_evidence"]
            frozen_ids = [chunk_key(e) for e in frozen]
            replay_ids = [chunk_key(e) for e in replay]
            if frozen_ids == replay_ids:
                exact += 1
            else:
                first = next((i for i, pair in enumerate(zip(frozen_ids, replay_ids), 1) if pair[0] != pair[1]), None)
                if first is None and len(frozen_ids) != len(replay_ids):
                    first = min(len(frozen_ids), len(replay_ids)) + 1
                mismatches.append({
                    "query_id": query["query_id"],
                    "profile_id": profile_id,
                    "first_mismatch_rank": first,
                    "frozen_order": frozen_ids,
                    "replay_order": replay_ids,
                })
    return {
        "run_count": total,
        "exact_ordered_evidence_replays": exact,
        "failed_replays": total - exact,
        "exact_replay_rate": exact / total if total else 0.0,
        "target_rate": 1.0,
        "confirmation_pass": total > 0 and exact == total,
        "logical_audit_rebuilt_for_replay": logical_audit,
        "mismatches": mismatches,
    }


def package_versions() -> dict[str, str | None]:
    out = {}
    for name in ("numpy", "scipy"):
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    ap.add_argument("--retrieval", type=Path, default=DEFAULT_RETRIEVAL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    args = ap.parse_args()

    required = [
        args.retrieval / "retrieval_freeze.json",
        args.retrieval / "primary_retrieval_runs.jsonl",
        args.retrieval / "SHA256SUMS.retrieval.txt",
        args.retrieval / "embedding_manifest.json",
        args.retrieval / "embedding_contract.json",
        args.retrieval / "retrieval_input_freeze.json",
        args.retrieval / "logical_chunk_order.jsonl",
        args.queries / "queries.jsonl",
        args.queries / "query_freeze.json",
        args.corpus / "corpus_freeze.json",
        args.runner,
        args.config,
        args.adapter,
    ]
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"missing required frozen input: {path}")
    if args.out.exists():
        if any(args.out.iterdir()):
            raise RuntimeError("CONFIRMATORY_OUTPUT_EXISTS; refusing to overwrite")
    else:
        args.out.mkdir(parents=True)

    checked_retrieval = verify_sha_manifest(args.retrieval / "SHA256SUMS.retrieval.txt")
    retrieval_freeze = read_json(args.retrieval / "retrieval_freeze.json")
    if retrieval_freeze.get("status") != "FROZEN_BEFORE_CONFIRMATORY_ANALYSIS":
        raise RuntimeError("unexpected retrieval freeze status")
    if retrieval_freeze.get("statistics_executed") is not False:
        raise RuntimeError("retrieval freeze does not preserve pre-analysis boundary")

    direct_hash_checks = {
        "queries_sha256": sha_file(args.queries / "queries.jsonl"),
        "retrieval_input_freeze_sha256": sha_file(args.retrieval / "retrieval_input_freeze.json"),
        "embedding_manifest_sha256": sha_file(args.retrieval / "embedding_manifest.json"),
        "primary_retrieval_runs_sha256": sha_file(args.retrieval / "primary_retrieval_runs.jsonl"),
        "retrieval_config_sha256": sha_file(args.config),
        "runner_script_sha256": sha_file(args.runner),
        "adapter_sha256": sha_file(args.adapter),
        "logical_chunk_order_sha256": sha_file(args.retrieval / "logical_chunk_order.jsonl"),
    }
    for key, actual in direct_hash_checks.items():
        if actual != EXPECTED[key]:
            raise RuntimeError(f"frozen C2 retrieval mismatch {key}: expected={EXPECTED[key]} actual={actual}")
        if key in retrieval_freeze and retrieval_freeze[key] != actual:
            raise RuntimeError(f"retrieval_freeze.json disagrees for {key}")
    for profile_id in (PROFILE_A, PROFILE_B):
        if (retrieval_freeze.get("profile_hashes") or {}).get(profile_id) != EXPECTED[profile_id]:
            raise RuntimeError(f"profile hash mismatch: {profile_id}")

    queries = read_jsonl(args.queries / "queries.jsonl")
    runs = read_jsonl(args.retrieval / "primary_retrieval_runs.jsonl")
    if len(queries) != 96 or len(runs) != 192:
        raise RuntimeError(f"unexpected frozen sizes: queries={len(queries)} runs={len(runs)}")
    run_map = {}
    for run in runs:
        key = (str(run["query_id"]), str(run["profile_id"]))
        if key in run_map:
            raise RuntimeError(f"duplicate frozen retrieval run: {key}")
        if len(run.get("ordered_evidence") or []) != TOP_K:
            raise RuntimeError(f"non-top10 frozen retrieval run: {key}")
        run_map[key] = run

    per_query = []
    for query in queries:
        qid = query["query_id"]
        layers = drift_layers(
            run_map[(qid, PROFILE_A)]["ordered_evidence"],
            run_map[(qid, PROFILE_B)]["ordered_evidence"],
        )
        chunk_churn = float(layers["chunk"]["churn_at_10"])
        dataset_churn = float(layers["dataset"]["churn_at_10"])
        per_query.append({
            "query_id": qid,
            "theme": query["theme"],
            "query_type": query["query_type"],
            "cell_replicate": int(query["cell_replicate"]),
            "source_multiplicity_Mq_from_frozen_sources": float(query["source_multiplicity_Mq_from_frozen_sources"]),
            "chunk_churn_at_10": chunk_churn,
            "distribution_churn_at_10": float(layers["distribution"]["churn_at_10"]),
            "dataset_churn_at_10": dataset_churn,
            "churn_gap_chunk_minus_dataset": chunk_churn - dataset_churn,
            "chunk_jaccard_at_10": float(layers["chunk"]["jaccard_at_10"]),
            "distribution_jaccard_at_10": float(layers["distribution"]["jaccard_at_10"]),
            "dataset_jaccard_at_10": float(layers["dataset"]["jaccard_at_10"]),
            "top1_chunk_same": bool(layers["chunk"]["top1_same"]),
            "top1_distribution_same": bool(layers["distribution"]["top1_same"]),
            "top1_dataset_same": bool(layers["dataset"]["top1_same"]),
            "left_dataset_count": int(layers["dataset"]["left_count"]),
            "right_dataset_count": int(layers["dataset"]["right_count"]),
            "left_distribution_count": int(layers["distribution"]["left_count"]),
            "right_distribution_count": int(layers["distribution"]["right_count"]),
        })

    import numpy as np
    from scipy.stats import spearmanr, wilcoxon

    chunk = np.asarray([r["chunk_churn_at_10"] for r in per_query], dtype=float)
    dataset = np.asarray([r["dataset_churn_at_10"] for r in per_query], dtype=float)
    diff = chunk - dataset
    if np.all(diff == 0.0):
        w_stat, h1_p = 0.0, 1.0
    else:
        w = wilcoxon(chunk, dataset, alternative="two-sided", zero_method="wilcox", correction=False)
        w_stat, h1_p = float(w.statistic), float(w.pvalue)
    rbc = rank_biserial_paired(diff)

    multiplicity = np.asarray([r["source_multiplicity_Mq_from_frozen_sources"] for r in per_query], dtype=float)
    rho_result = spearmanr(multiplicity, diff)
    h2_rho = float(rho_result.statistic)
    h2_p = float(rho_result.pvalue)
    if not math.isfinite(h2_rho) or not math.isfinite(h2_p):
        raise RuntimeError("H2 Spearman result is non-finite")
    adjusted = holm_adjust({"H1": h1_p, "H2": h2_p})
    alpha = 0.05

    h1 = {
        "test": "paired Wilcoxon signed-rank, two-sided",
        "n_queries": len(per_query),
        "expected_direction": "chunk_churn_at_10 > dataset_churn_at_10",
        "wilcoxon_statistic": w_stat,
        "p_raw": h1_p,
        "p_holm": adjusted["H1"],
        "holm_significant_0_05": adjusted["H1"] < alpha,
        "mean_chunk_churn_at_10": float(chunk.mean()),
        "median_chunk_churn_at_10": float(np.median(chunk)),
        "mean_dataset_churn_at_10": float(dataset.mean()),
        "median_dataset_churn_at_10": float(np.median(dataset)),
        "mean_paired_difference": float(diff.mean()),
        "median_paired_difference": float(np.median(diff)),
        "positive_pairs": int(np.sum(diff > 0)),
        "negative_pairs": int(np.sum(diff < 0)),
        "zero_pairs": int(np.sum(diff == 0)),
        **rbc,
    }
    h2 = {
        "test": "Spearman rank correlation, two-sided",
        "n_queries": len(per_query),
        "expected_direction": "rho(M_q, chunk_churn_at_10 - dataset_churn_at_10) > 0",
        "rho": h2_rho,
        "p_raw": h2_p,
        "p_holm": adjusted["H2"],
        "holm_significant_0_05": adjusted["H2"] < alpha,
        "multiplicity_min": float(multiplicity.min()),
        "multiplicity_max": float(multiplicity.max()),
        "multiplicity_mean": float(multiplicity.mean()),
    }

    runner = load_runner(args.runner)
    h3 = exact_replay(
        runner=runner,
        corpus=args.corpus,
        queries_dir=args.queries,
        retrieval_dir=args.retrieval,
        config_path=args.config,
        frozen_runs=run_map,
    )

    by_theme = defaultdict(list)
    by_type = defaultdict(list)
    for row in per_query:
        by_theme[row["theme"]].append(row)
        by_type[row["query_type"]].append(row)
    secondary = {
        "overall": aggregate_group(per_query),
        "by_theme": {k: aggregate_group(v) for k, v in sorted(by_theme.items())},
        "by_query_type": {k: aggregate_group(v) for k, v in sorted(by_type.items())},
        "note": "Distribution-layer and subgroup summaries are descriptive. RBO is not computed here because the frozen C2 protocol did not specify its persistence parameter.",
    }

    result = {
        "artifact": "SECOND_CORPUS_C2_CONFIRMATORY_RESULTS_V1",
        "status": "FROZEN_CONFIRMATORY_ANALYSIS",
        "protocol_endpoints": {
            "H1": "chunk churn@10 vs dataset churn@10",
            "H2": "Spearman frozen M_q vs chunk-minus-dataset churn gap",
            "H3": "100% exact ordered-evidence replay",
            "holm_family": ["H1", "H2"],
            "familywise_alpha": alpha,
        },
        "frozen_inputs": {
            **direct_hash_checks,
            "retrieval_freeze_sha256": sha_file(args.retrieval / "retrieval_freeze.json"),
            "sha256_retrieval_manifest_entries_verified": checked_retrieval,
            "profile_hashes": {PROFILE_A: EXPECTED[PROFILE_A], PROFILE_B: EXPECTED[PROFILE_B]},
        },
        "software": package_versions(),
        "H1": h1,
        "H2": h2,
        "H3": {k: v for k, v in h3.items() if k != "mismatches"},
        "confirmatory_summary": {
            "H1_expected_direction_observed": h1["median_paired_difference"] > 0,
            "H1_holm_significant": h1["holm_significant_0_05"],
            "H2_expected_direction_observed": h2["rho"] > 0,
            "H2_holm_significant": h2["holm_significant_0_05"],
            "H3_exact_replay_pass": h3["confirmation_pass"],
        },
        "secondary_descriptive": secondary,
    }

    per_query_path = args.out / "per_query_metrics.jsonl"
    replay_path = args.out / "replay_audit.json"
    result_path = args.out / "confirmatory_results.json"
    write_jsonl(per_query_path, per_query)
    atomic_json(replay_path, h3)
    atomic_json(result_path, result)
    freeze = {
        "artifact": "SECOND_CORPUS_C2_CONFIRMATORY_FREEZE_V1",
        "status": "FROZEN_AFTER_CONFIRMATORY_ANALYSIS",
        "retrieval_freeze_sha256": sha_file(args.retrieval / "retrieval_freeze.json"),
        "primary_retrieval_runs_sha256": sha_file(args.retrieval / "primary_retrieval_runs.jsonl"),
        "per_query_metrics_sha256": sha_file(per_query_path),
        "replay_audit_sha256": sha_file(replay_path),
        "confirmatory_results_sha256": sha_file(result_path),
        "analysis_script_sha256": sha_file(Path(__file__)),
    }
    freeze_path = args.out / "confirmation_freeze.json"
    atomic_json(freeze_path, freeze)
    hash_paths = [
        args.retrieval / "retrieval_freeze.json",
        args.retrieval / "primary_retrieval_runs.jsonl",
        args.retrieval / "SHA256SUMS.retrieval.txt",
        args.queries / "queries.jsonl",
        args.corpus / "corpus_freeze.json",
        args.config,
        args.adapter,
        args.runner,
        Path(__file__),
        per_query_path,
        replay_path,
        result_path,
        freeze_path,
    ]
    atomic_text(
        args.out / "SHA256SUMS.confirmation.txt",
        "".join(f"{sha_file(path)}  {path.relative_to(ROOT)}\n" for path in hash_paths),
    )
    print("C2_CONFIRMATORY_ANALYSIS_FROZEN")
    print(json.dumps({
        "H1": h1,
        "H2": h2,
        "H3": {
            "run_count": h3["run_count"],
            "exact_ordered_evidence_replays": h3["exact_ordered_evidence_replays"],
            "failed_replays": h3["failed_replays"],
            "exact_replay_rate": h3["exact_replay_rate"],
            "confirmation_pass": h3["confirmation_pass"],
        },
        "confirmatory_summary": result["confirmatory_summary"],
        "confirmation_freeze_sha256": sha_file(freeze_path),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
