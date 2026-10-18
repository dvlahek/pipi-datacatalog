#!/usr/bin/env python3
"""Freeze the context-feasible complete-pair C2 answer-drift V2 input.

Selection uses only the frozen V1 prompt token audit. Answer text and V1 partial
answer outcomes are never read. Evidence text/order and query text are copied
unchanged for included complete query pairs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v1.json"
DEFAULT_V2_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v2_context_feasible.json"
DEFAULT_V1_INPUT = ROOT / "results" / "second_corpus_answer_drift_v1" / "answer_drift_input.json"
DEFAULT_V1_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v1" / "answer_drift_input_freeze.json"
DEFAULT_AUDIT = ROOT / "results" / "second_corpus_answer_drift_v1" / "context_compatibility_audit_v1.json"
DEFAULT_GENERATION_RUNNER = ROOT / "scripts" / "second_corpus_run_answer_drift_qwen_v2.py"
DEFAULT_MODEL = ROOT / "models" / "rq3" / "Qwen3-8B-Q4_K_M.gguf"
DEFAULT_OUT = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible"
PROFILE_IDS = ("hybrid-e5-content-v1", "hybrid-e5-metadata-v1")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, obj: Any) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG)
    ap.add_argument("--v2-config", type=Path, default=DEFAULT_V2_CONFIG)
    ap.add_argument("--v1-input", type=Path, default=DEFAULT_V1_INPUT)
    ap.add_argument("--v1-freeze", type=Path, default=DEFAULT_V1_FREEZE)
    ap.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    ap.add_argument("--generation-runner", type=Path, default=DEFAULT_GENERATION_RUNNER)
    ap.add_argument("--model-file", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    required = [
        args.base_config,
        args.v2_config,
        args.v1_input,
        args.v1_freeze,
        args.audit,
        args.generation_runner,
        args.model_file,
    ]
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"missing required input: {path}")

    out = args.out
    input_path = out / "answer_drift_input_v2.json"
    freeze_path = out / "answer_drift_input_v2_freeze.json"
    exclusion_path = out / "context_feasibility_exclusions_v2.json"
    sums_path = out / "SHA256SUMS.answer_drift_input_v2.txt"
    if any(p.exists() for p in (input_path, freeze_path, exclusion_path, sums_path)):
        raise RuntimeError("ANSWER_DRIFT_V2_INPUT_ALREADY_EXISTS; refusing to overwrite")

    base_config = read_json(args.base_config)
    v2_config = read_json(args.v2_config)
    v1_input = read_json(args.v1_input)
    v1_freeze = read_json(args.v1_freeze)
    audit = read_json(args.audit)

    base_config_sha = sha_file(args.base_config)
    v2_config_sha = sha_file(args.v2_config)
    v1_input_sha = sha_file(args.v1_input)
    v1_freeze_sha = sha_file(args.v1_freeze)
    audit_sha = sha_file(args.audit)
    runner_sha = sha_file(args.generation_runner)
    model_sha = sha_file(args.model_file)

    if v2_config.get("status") != "FROZEN_BEFORE_V2_ANSWER_GENERATION":
        raise RuntimeError("V2 amendment config status mismatch")
    if base_config.get("status") != "FROZEN_BEFORE_ANY_C2_ANSWER_GENERATION":
        raise RuntimeError("V1 base config status mismatch")
    if v1_input.get("status") != "PREPARED_BEFORE_C2_ANSWER_GENERATION":
        raise RuntimeError("V1 input status mismatch")
    if v1_freeze.get("status") != "FROZEN_BEFORE_C2_ANSWER_GENERATION":
        raise RuntimeError("V1 input freeze status mismatch")

    expected = v2_config["base_v1"]
    checks = {
        "config_sha256": base_config_sha,
        "answer_drift_input_sha256": v1_input_sha,
        "input_freeze_sha256": v1_freeze_sha,
        "context_audit_sha256": audit_sha,
    }
    for key, actual in checks.items():
        if str(expected.get(key)) != actual:
            raise RuntimeError(f"V2 amendment binding mismatch {key}: expected={expected.get(key)} actual={actual}")

    if v1_freeze.get("config_sha256") != base_config_sha:
        raise RuntimeError("V1 freeze/base config mismatch")
    if v1_freeze.get("answer_drift_input_sha256") != v1_input_sha:
        raise RuntimeError("V1 freeze/input mismatch")
    if model_sha != str(v2_config["unchanged_generation_contract"]["gguf_sha256"]):
        raise RuntimeError("Qwen GGUF hash mismatch")

    if audit.get("answer_drift_input_sha256") != v1_input_sha:
        raise RuntimeError("context audit belongs to a different V1 input")
    if int(audit.get("condition_count") or 0) != 192:
        raise RuntimeError("context audit does not cover 192 V1 conditions")

    audit_rows = list(audit.get("all_conditions") or [])
    audit_map = {(str(r["query_id"]), str(r["condition"])): r for r in audit_rows}
    if len(audit_map) != 192:
        raise RuntimeError(f"expected 192 unique audited conditions, got {len(audit_map)}")

    n_ctx = int(v2_config["unchanged_generation_contract"]["context_size"])
    max_tokens = int(v2_config["unchanged_generation_contract"]["max_tokens"])
    if n_ctx != 16384 or max_tokens != 384:
        raise RuntimeError("unexpected V2 feasibility boundary")

    included_cases: list[dict] = []
    exclusions: list[dict] = []
    excluded_condition_counts = Counter()
    excluded_theme_counts = Counter()
    excluded_type_counts = Counter()
    included_input_tokens: list[int] = []

    cases = list(v1_input.get("cases") or [])
    if len(cases) != 96:
        raise RuntimeError(f"expected 96 V1 cases, got {len(cases)}")

    for case in cases:
        qid = str(case["query_id"])
        token_map: dict[str, int] = {}
        failed: list[str] = []
        for pid in PROFILE_IDS:
            row = audit_map.get((qid, pid))
            if row is None:
                raise RuntimeError(f"missing audited condition {qid}/{pid}")
            input_tokens = int(row["input_tokens"])
            token_map[pid] = input_tokens
            recomputed_fit = input_tokens + max_tokens <= n_ctx
            if bool(row.get("prompt_plus_reserved_output_fits")) != recomputed_fit:
                raise RuntimeError(f"audit feasibility flag mismatch {qid}/{pid}")
            if not recomputed_fit:
                failed.append(pid)
                excluded_condition_counts[pid] += 1

        if failed:
            theme = str(case.get("theme") or "")
            qtype = str(case.get("query_type") or "")
            excluded_theme_counts[theme] += 1
            excluded_type_counts[qtype] += 1
            exclusions.append({
                "query_id": qid,
                "theme": theme,
                "query_type": qtype,
                "failed_conditions": failed,
                "audited_input_tokens": token_map,
                "selection_reason": "excluded because at least one paired condition fails input_tokens + 384 <= 16384",
            })
            continue

        copied = dict(case)
        copied["audited_input_tokens"] = token_map
        copied["context_feasibility_rule"] = "both_conditions_input_tokens_plus_384_le_16384"
        included_cases.append(copied)
        included_input_tokens.extend(token_map.values())

    included_query_count = len(included_cases)
    excluded_query_count = len(exclusions)
    if included_query_count + excluded_query_count != 96:
        raise RuntimeError("V2 inclusion accounting mismatch")
    if included_query_count <= 0:
        raise RuntimeError("no context-feasible query pairs")

    coverage_rate = included_query_count / 96.0
    artifact = {
        "artifact": "SECOND_CORPUS_C2_ANSWER_DRIFT_INPUT_V2_CONTEXT_FEASIBLE",
        "status": "FROZEN_CONTEXT_FEASIBLE_INPUT_V2",
        "scientific_status": v2_config["scientific_status"],
        "base_v1_config_sha256": base_config_sha,
        "v2_config_sha256": v2_config_sha,
        "v1_answer_drift_input_sha256": v1_input_sha,
        "v1_input_freeze_sha256": v1_freeze_sha,
        "context_audit_sha256": audit_sha,
        "selection_rule": "include query iff both frozen profile conditions satisfy input_tokens + 384 <= 16384",
        "v1_partial_answers_reused": False,
        "query_count": included_query_count,
        "condition_count": 2 * included_query_count,
        "excluded_query_count": excluded_query_count,
        "coverage_rate": coverage_rate,
        "profile_ids": list(PROFILE_IDS),
        "context_size": n_ctx,
        "max_tokens": max_tokens,
        "contains_chunk_text": True,
        "publication_safe": False,
        "cases": included_cases,
    }
    atomic_json(input_path, artifact)

    exclusion_artifact = {
        "artifact": "SECOND_CORPUS_C2_ANSWER_DRIFT_V2_CONTEXT_EXCLUSIONS",
        "scientific_status": "technical coverage report; no answer outcomes used",
        "context_audit_sha256": audit_sha,
        "total_query_count": 96,
        "included_query_count": included_query_count,
        "excluded_query_count": excluded_query_count,
        "coverage_rate": coverage_rate,
        "excluded_condition_count": sum(excluded_condition_counts.values()),
        "excluded_conditions_by_profile": dict(sorted(excluded_condition_counts.items())),
        "excluded_queries_by_theme": dict(sorted(excluded_theme_counts.items())),
        "excluded_queries_by_query_type": dict(sorted(excluded_type_counts.items())),
        "excluded_queries": exclusions,
    }
    atomic_json(exclusion_path, exclusion_artifact)

    freeze = {
        "artifact": "SECOND_CORPUS_C2_ANSWER_DRIFT_INPUT_FREEZE_V2_CONTEXT_FEASIBLE",
        "status": "FROZEN_BEFORE_V2_ANSWER_GENERATION",
        "scientific_status": v2_config["scientific_status"],
        "base_v1_config_sha256": base_config_sha,
        "v2_config_sha256": v2_config_sha,
        "v1_answer_drift_input_sha256": v1_input_sha,
        "v1_input_freeze_sha256": v1_freeze_sha,
        "context_audit_sha256": audit_sha,
        "answer_drift_input_v2_sha256": sha_file(input_path),
        "context_exclusions_v2_sha256": sha_file(exclusion_path),
        "generation_runner_v2_sha256": runner_sha,
        "qwen_gguf_sha256": model_sha,
        "query_count": included_query_count,
        "condition_count": 2 * included_query_count,
        "excluded_query_count": excluded_query_count,
        "coverage_rate": coverage_rate,
        "max_included_input_tokens": max(included_input_tokens),
        "max_included_input_plus_reserved_output_tokens": max(included_input_tokens) + max_tokens,
        "v1_partial_answers_reused": False,
        "answers_generated_v2": False,
    }
    atomic_json(freeze_path, freeze)

    paths = [args.base_config, args.v2_config, args.v1_input, args.v1_freeze, args.audit, args.generation_runner, input_path, exclusion_path, freeze_path]
    atomic_text(sums_path, "".join(f"{sha_file(p)}  {p.relative_to(ROOT)}\n" for p in paths))

    print("C2_ANSWER_DRIFT_V2_INPUT_FROZEN")
    print(json.dumps({
        "included_query_count": included_query_count,
        "excluded_query_count": excluded_query_count,
        "coverage_rate": coverage_rate,
        "condition_count": 2 * included_query_count,
        "excluded_condition_count": sum(excluded_condition_counts.values()),
        "excluded_conditions_by_profile": dict(sorted(excluded_condition_counts.items())),
        "excluded_queries_by_theme": dict(sorted(excluded_theme_counts.items())),
        "excluded_queries_by_query_type": dict(sorted(excluded_type_counts.items())),
        "max_included_input_tokens": freeze["max_included_input_tokens"],
        "answer_drift_input_v2_sha256": freeze["answer_drift_input_v2_sha256"],
        "context_exclusions_v2_sha256": freeze["context_exclusions_v2_sha256"],
        "input_freeze_v2_sha256": sha_file(freeze_path),
        "answers_generated_v2": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
