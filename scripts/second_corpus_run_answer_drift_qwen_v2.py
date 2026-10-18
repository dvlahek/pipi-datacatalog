#!/usr/bin/env python3
"""Run C2 Qwen answer drift on the frozen context-feasible V2 query pairs.

V2 preserves the V1 model, prompt, decoding, evidence text/order and 16k
context contract. It operates only on complete query pairs frozen by the V2
preparation script. V1 partial answers are never read or reused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v1.json"
DEFAULT_V2_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v2_context_feasible.json"
DEFAULT_INPUT = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2.json"
DEFAULT_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2_freeze.json"
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


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
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


def atomic_json(path: Path, obj: Any) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def http_json(method: str, url: str, payload: dict | None, timeout: float) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from llama.cpp: {body[:2000]}") from exc


def build_messages(base_config: dict, query: str, evidence: str) -> list[dict[str, str]]:
    system = str(base_config["prompt"]["system"])
    user = str(base_config["prompt"]["user_template"]).format(query=query, evidence=evidence)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG)
    ap.add_argument("--v2-config", type=Path, default=DEFAULT_V2_CONFIG)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--freeze-manifest", type=Path, default=DEFAULT_FREEZE)
    ap.add_argument("--model-file", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args()

    for path in (args.base_config, args.v2_config, args.input, args.freeze_manifest, args.model_file):
        if not path.is_file():
            raise RuntimeError(f"missing required input: {path}")

    base_config = read_json(args.base_config)
    v2_config = read_json(args.v2_config)
    inputs = read_json(args.input)
    freeze = read_json(args.freeze_manifest)

    if v2_config.get("status") != "FROZEN_BEFORE_V2_ANSWER_GENERATION":
        raise RuntimeError("V2 amendment config is not frozen")
    if inputs.get("status") != "FROZEN_CONTEXT_FEASIBLE_INPUT_V2":
        raise RuntimeError("V2 input status mismatch")
    if freeze.get("status") != "FROZEN_BEFORE_V2_ANSWER_GENERATION":
        raise RuntimeError("V2 input freeze status mismatch")

    self_sha = sha_file(Path(__file__))
    base_config_sha = sha_file(args.base_config)
    v2_config_sha = sha_file(args.v2_config)
    input_sha = sha_file(args.input)
    model_sha = sha_file(args.model_file)

    expected_model_sha = str(base_config["generator"]["gguf_sha256"])
    if model_sha != expected_model_sha:
        raise RuntimeError(f"Qwen GGUF SHA mismatch expected={expected_model_sha} actual={model_sha}")
    if v2_config["base_v1"]["config_sha256"] != base_config_sha:
        raise RuntimeError("V2 amendment is not bound to this V1 base config")

    checks = {
        "base_v1_config_sha256": base_config_sha,
        "v2_config_sha256": v2_config_sha,
        "answer_drift_input_v2_sha256": input_sha,
        "generation_runner_v2_sha256": self_sha,
        "qwen_gguf_sha256": model_sha,
    }
    for key, actual in checks.items():
        if freeze.get(key) != actual:
            raise RuntimeError(f"V2 input freeze mismatch {key}: frozen={freeze.get(key)} actual={actual}")

    cases = list(inputs.get("cases") or [])
    query_count = int(inputs.get("query_count") or 0)
    condition_count = int(inputs.get("condition_count") or 0)
    if query_count != len(cases) or query_count <= 0:
        raise RuntimeError("invalid V2 query count")
    if condition_count != 2 * query_count:
        raise RuntimeError("invalid V2 condition count")

    generation = base_config["generator"]
    if int(generation["context_size"]) != 16384 or int(generation["max_tokens"]) != 384:
        raise RuntimeError("V2 generator contract differs from frozen amendment")

    base = args.base_url.rstrip("/")
    model_payload = http_json("GET", base + "/models", None, args.timeout)
    models = model_payload.get("data") or []
    if len(models) != 1:
        raise RuntimeError(f"expected exactly one llama.cpp model, found {len(models)}")
    server_model_id = str(models[0].get("id") or "")
    if not server_model_id:
        raise RuntimeError("llama.cpp returned empty model ID")

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    answers_path = out / "qwen_answers_v2.jsonl"
    summary_path = out / "qwen_generation_summary_v2.json"
    answer_freeze_path = out / "qwen_answers_v2_freeze.json"
    if answer_freeze_path.exists():
        raise RuntimeError("QWEN_V2_ANSWERS_ALREADY_FROZEN; refusing to mutate")

    existing = read_jsonl(answers_path)
    done: dict[tuple[str, str], dict] = {}
    for row in existing:
        key = (str(row["query_id"]), str(row["condition"]))
        if key in done:
            raise RuntimeError(f"duplicate existing V2 answer: {key}")
        if row.get("v2_config_sha256") != v2_config_sha or row.get("answer_drift_input_v2_sha256") != input_sha:
            raise RuntimeError(f"existing V2 answer belongs to different frozen input: {key}")
        if row.get("gguf_sha256") != model_sha:
            raise RuntimeError(f"existing V2 answer model hash mismatch: {key}")
        done[key] = row

    planned = [(case, pid) for case in cases for pid in PROFILE_IDS]
    print("C2_QWEN_ANSWER_DRIFT_V2_START")
    print(f"SERVER_MODEL_ID={server_model_id}")
    print(f"QUERIES={query_count} PLANNED={len(planned)} RESUME_COMPLETED={len(done)}")
    print(f"V2_CONFIG_SHA256={v2_config_sha}")
    print(f"INPUT_V2_SHA256={input_sha}")
    print(f"GGUF_SHA256={model_sha}")
    started = time.time()
    new = 0

    for case, condition in planned:
        qid = str(case["query_id"])
        key = (qid, condition)
        if key in done:
            continue
        cond = case["conditions"][condition]
        messages = build_messages(base_config, str(case["query_text"]), str(cond["serialized_evidence"]))
        request_body = {
            "model": server_model_id,
            "messages": messages,
            "temperature": float(generation["temperature"]),
            "top_p": float(generation["top_p"]),
            "seed": int(generation["seed"]),
            "max_tokens": int(generation["max_tokens"]),
            "stream": False,
        }
        payload = http_json("POST", base + "/chat/completions", request_body, args.timeout)
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"no completion choice for {key}")
        message = choices[0].get("message") or {}
        answer = str(message.get("content") or "").strip()
        if not answer:
            raise RuntimeError(f"empty completion for {key}")

        prompt_material = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        row = {
            "artifact": "SECOND_CORPUS_C2_QWEN_ANSWER_V2_CONTEXT_FEASIBLE",
            "query_id": qid,
            "theme": case["theme"],
            "query_type": case["query_type"],
            "condition": condition,
            "model_key": base_config["generator"]["model_key"],
            "server_model_id": server_model_id,
            "base_v1_config_sha256": base_config_sha,
            "v2_config_sha256": v2_config_sha,
            "answer_drift_input_v2_sha256": input_sha,
            "gguf_sha256": model_sha,
            "query_text_sha256": case["query_text_sha256"],
            "serialized_evidence_sha256": cond["serialized_evidence_sha256"],
            "ordered_evidence_identity_sha256": cond["ordered_evidence_identity_sha256"],
            "audited_input_tokens": int(case["audited_input_tokens"][condition]),
            "prompt_sha256": hashlib.sha256(prompt_material.encode("utf-8")).hexdigest(),
            "answer": answer,
            "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
            "finish_reason": choices[0].get("finish_reason"),
            "usage": payload.get("usage"),
            "generation": {
                "temperature": generation["temperature"],
                "top_p": generation["top_p"],
                "seed": generation["seed"],
                "max_tokens": generation["max_tokens"],
                "context_size": generation["context_size"],
            },
        }
        append_jsonl(answers_path, row)
        done[key] = row
        new += 1
        if new == 1 or new % 10 == 0 or len(done) == len(planned):
            print(f"QWEN_V2_GENERATION_PASS {len(done)}/{len(planned)} query={qid} condition={condition}", flush=True)

    if len(done) != len(planned):
        raise RuntimeError(f"V2 generation incomplete: {len(done)}/{len(planned)}")

    canonical_rows = [done[(str(case["query_id"]), pid)] for case in cases for pid in PROFILE_IDS]
    canonical_text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in canonical_rows)
    atomic_text(answers_path, canonical_text)

    summary = {
        "artifact": "SECOND_CORPUS_C2_QWEN_GENERATION_SUMMARY_V2_CONTEXT_FEASIBLE",
        "status": "COMPLETE",
        "query_count": query_count,
        "answer_count": len(planned),
        "excluded_query_count": int(inputs.get("excluded_query_count") or 0),
        "coverage_rate": inputs.get("coverage_rate"),
        "conditions": list(PROFILE_IDS),
        "server_model_id": server_model_id,
        "gguf_sha256": model_sha,
        "base_v1_config_sha256": base_config_sha,
        "v2_config_sha256": v2_config_sha,
        "answer_drift_input_v2_sha256": input_sha,
        "answers_sha256": sha_file(answers_path),
        "elapsed_seconds_this_invocation": time.time() - started,
        "v1_partial_answers_reused": False,
        "answers_inspected_by_runner": False,
    }
    atomic_json(summary_path, summary)

    answer_freeze = {
        "artifact": "SECOND_CORPUS_C2_QWEN_ANSWERS_FREEZE_V2_CONTEXT_FEASIBLE",
        "status": "FROZEN_BEFORE_V2_ANSWER_PAIR_JUDGING",
        "base_v1_config_sha256": base_config_sha,
        "v2_config_sha256": v2_config_sha,
        "input_freeze_v2_sha256": sha_file(args.freeze_manifest),
        "answer_drift_input_v2_sha256": input_sha,
        "generation_runner_v2_sha256": self_sha,
        "qwen_gguf_sha256": model_sha,
        "answers_sha256": sha_file(answers_path),
        "generation_summary_sha256": sha_file(summary_path),
        "answer_count": len(planned),
        "query_count": query_count,
        "excluded_query_count": int(inputs.get("excluded_query_count") or 0),
        "coverage_rate": inputs.get("coverage_rate"),
        "profile_identity_not_exposed_in_prompt": True,
        "v1_partial_answers_reused": False,
    }
    atomic_json(answer_freeze_path, answer_freeze)

    sums = out / "SHA256SUMS.qwen_answers_v2.txt"
    paths = [args.base_config, args.v2_config, args.input, args.freeze_manifest, Path(__file__), answers_path, summary_path, answer_freeze_path]
    atomic_text(sums, "".join(f"{sha_file(p)}  {p.relative_to(ROOT)}\n" for p in paths))

    print("C2_QWEN_ANSWERS_V2_FROZEN")
    print(json.dumps({
        "query_count": query_count,
        "answer_count": len(planned),
        "excluded_query_count": int(inputs.get("excluded_query_count") or 0),
        "coverage_rate": inputs.get("coverage_rate"),
        "answers_sha256": sha_file(answers_path),
        "generation_summary_sha256": sha_file(summary_path),
        "answers_freeze_sha256": sha_file(answer_freeze_path),
        "server_model_id": server_model_id,
        "gguf_sha256": model_sha,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
