#!/usr/bin/env python3
"""Audit frozen C2 answer-drift prompt sizes without generating or inspecting answers.

This script is diagnostic only. It verifies the frozen C2 answer-drift input,
uses llama.cpp's token-counting endpoint with the exact frozen chat messages,
and reports prompt-size compatibility with the frozen 16,384-token context.
It never reads or prints answer text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v1.json"
DEFAULT_INPUT = ROOT / "results" / "second_corpus_answer_drift_v1" / "answer_drift_input.json"
DEFAULT_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v1" / "answer_drift_input_freeze.json"
DEFAULT_ANSWERS = ROOT / "results" / "second_corpus_answer_drift_v1" / "qwen_answers.jsonl"
DEFAULT_OUT = ROOT / "results" / "second_corpus_answer_drift_v1" / "context_compatibility_audit_v1.json"
PROFILE_IDS = ("hybrid-e5-content-v1", "hybrid-e5-metadata-v1")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def http_json(method: str, url: str, payload: dict | None, timeout: float) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from llama.cpp: {body[:2000]}") from exc


def build_messages(config: dict, query: str, evidence: str) -> list[dict[str, str]]:
    system = str(config["prompt"]["system"])
    user = str(config["prompt"]["user_template"]).format(query=query, evidence=evidence)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def count_existing_answers_without_reading_text(path: Path) -> tuple[int, list[dict[str, str]]]:
    if not path.exists():
        return 0, []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append({
                "query_id": str(row.get("query_id") or ""),
                "condition": str(row.get("condition") or ""),
                "answer_sha256": str(row.get("answer_sha256") or ""),
            })
    return len(rows), rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--freeze-manifest", type=Path, default=DEFAULT_FREEZE)
    ap.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    for p in (args.config, args.input, args.freeze_manifest):
        if not p.is_file():
            raise RuntimeError(f"missing required frozen input: {p}")

    config = read_json(args.config)
    inputs = read_json(args.input)
    freeze = read_json(args.freeze_manifest)
    if config.get("status") != "FROZEN_BEFORE_ANY_C2_ANSWER_GENERATION":
        raise RuntimeError("config status mismatch")
    if inputs.get("status") != "PREPARED_BEFORE_C2_ANSWER_GENERATION":
        raise RuntimeError("input status mismatch")
    if freeze.get("status") != "FROZEN_BEFORE_C2_ANSWER_GENERATION":
        raise RuntimeError("freeze status mismatch")
    if freeze.get("config_sha256") != sha_file(args.config):
        raise RuntimeError("config SHA differs from frozen manifest")
    if freeze.get("answer_drift_input_sha256") != sha_file(args.input):
        raise RuntimeError("input SHA differs from frozen manifest")

    n_ctx = int(config["generator"]["context_size"])
    max_tokens = int(config["generator"]["max_tokens"])
    base = args.base_url.rstrip("/")
    models = http_json("GET", base + "/v1/models", None, args.timeout).get("data") or []
    if len(models) != 1:
        raise RuntimeError(f"expected exactly one llama.cpp model, found {len(models)}")
    model_id = str(models[0].get("id") or "")
    if not model_id:
        raise RuntimeError("empty llama.cpp model id")

    rows = []
    for case in inputs.get("cases") or []:
        qid = str(case["query_id"])
        for condition in PROFILE_IDS:
            cond = case["conditions"][condition]
            evidence = str(cond["serialized_evidence"])
            messages = build_messages(config, str(case["query_text"]), evidence)
            request_body = {
                "model": model_id,
                "messages": messages,
                "temperature": float(config["generator"]["temperature"]),
                "top_p": float(config["generator"]["top_p"]),
                "seed": int(config["generator"]["seed"]),
                "max_tokens": max_tokens,
                "stream": False,
            }
            token_payload = http_json("POST", base + "/v1/chat/completions/input_tokens", request_body, args.timeout)
            input_tokens = int(token_payload["input_tokens"])
            evidence_records = list(cond.get("evidence") or [])
            text_lengths = [len(str(e.get("text") or "")) for e in evidence_records]
            max_rank = (text_lengths.index(max(text_lengths)) + 1) if text_lengths else None
            rows.append({
                "query_id": qid,
                "theme": case.get("theme"),
                "query_type": case.get("query_type"),
                "condition": condition,
                "input_tokens": input_tokens,
                "frozen_context_size": n_ctx,
                "frozen_max_output_tokens": max_tokens,
                "prompt_fits_input_only": input_tokens < n_ctx,
                "prompt_plus_reserved_output_fits": input_tokens + max_tokens <= n_ctx,
                "serialized_evidence_chars": len(evidence),
                "max_single_evidence_text_chars": max(text_lengths) if text_lengths else 0,
                "max_single_evidence_rank": max_rank,
                "ordered_evidence_identity_sha256": cond.get("ordered_evidence_identity_sha256"),
            })

    over_input = [r for r in rows if not r["prompt_fits_input_only"]]
    over_reserved = [r for r in rows if not r["prompt_plus_reserved_output_fits"]]
    existing_count, existing_answer_metadata = count_existing_answers_without_reading_text(args.answers)
    sorted_rows = sorted(rows, key=lambda r: r["input_tokens"], reverse=True)

    artifact = {
        "artifact": "SECOND_CORPUS_C2_ANSWER_CONTEXT_COMPATIBILITY_AUDIT_V1",
        "scientific_status": "diagnostic_after_generation_transport_failure; no answer text inspected",
        "config_sha256": sha_file(args.config),
        "answer_drift_input_sha256": sha_file(args.input),
        "input_freeze_sha256": sha_file(args.freeze_manifest),
        "server_model_id": model_id,
        "frozen_context_size": n_ctx,
        "frozen_max_output_tokens": max_tokens,
        "condition_count": len(rows),
        "input_only_over_context_count": len(over_input),
        "prompt_plus_reserved_output_over_context_count": len(over_reserved),
        "max_input_tokens": max(r["input_tokens"] for r in rows),
        "median_input_tokens": sorted(r["input_tokens"] for r in rows)[len(rows)//2],
        "existing_generated_answer_count": existing_count,
        "existing_generated_answer_metadata_only": existing_answer_metadata,
        "largest_20_prompts": sorted_rows[:20],
        "all_conditions": rows,
    }
    atomic_json(args.out, artifact)
    print("C2_ANSWER_CONTEXT_AUDIT_PASS")
    print(json.dumps({
        "condition_count": len(rows),
        "input_only_over_context_count": len(over_input),
        "prompt_plus_reserved_output_over_context_count": len(over_reserved),
        "max_input_tokens": artifact["max_input_tokens"],
        "median_input_tokens": artifact["median_input_tokens"],
        "existing_generated_answer_count": existing_count,
        "audit_sha256": sha_file(args.out),
        "largest_10": [
            {
                "query_id": r["query_id"],
                "condition": r["condition"],
                "input_tokens": r["input_tokens"],
                "serialized_evidence_chars": r["serialized_evidence_chars"],
                "max_single_evidence_text_chars": r["max_single_evidence_text_chars"],
                "max_single_evidence_rank": r["max_single_evidence_rank"],
            }
            for r in sorted_rows[:10]
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
