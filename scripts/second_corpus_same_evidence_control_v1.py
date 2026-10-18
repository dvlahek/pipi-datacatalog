#!/usr/bin/env python3
"""Post-hoc deterministic same-evidence repeat for the frozen C2 Qwen V2 subset.

This validation does not change the frozen C2 answer-drift endpoint. It repeats
all 162 already-frozen query/condition prompts under the exact same Qwen3-8B
llama.cpp contract and compares the repeated answer SHA-256 with the original
answer SHA-256 for that same prompt.
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
BASE_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v1.json"
V2_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v2_context_feasible.json"
INPUT = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2.json"
INPUT_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2_freeze.json"
ORIGINAL_ANSWERS = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "qwen_answers_v2.jsonl"
ORIGINAL_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "qwen_answers_v2_freeze.json"
MODEL = ROOT / "models" / "rq3" / "Qwen3-8B-Q4_K_M.gguf"
OUT = ROOT / "results" / "second_corpus_same_evidence_control_v1"
PROFILE_IDS = ("hybrid-e5-content-v1", "hybrid-e5-metadata-v1")

EXPECTED = {
    "input": "43af919a2b6321858e052f6e8dd0ca51a91d08c7ff4f6745153a9902655a824a",
    "input_freeze": "ec3bb5e56a4ab72639e299cdd4e2beaaf259808ff459408110fb2ac4dc94f5ed",
    "original_answers": "c59a19c51cb05395cb4fbee23edb601f8f3b68e23940c14a54fbac5d434627b3",
    "original_freeze": "e03a321671b7e5f243d033ff506862c12c5b089ad2066a5b99711ed131df64ed",
    "gguf": "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785",
}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as f:
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
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:2000]}") from exc


def build_messages(config: dict, query: str, evidence: str) -> list[dict[str, str]]:
    system = str(config["prompt"]["system"])
    user = str(config["prompt"]["user_template"]).format(query=query, evidence=evidence)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def require_sha(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    got = sha_file(path)
    if got != expected:
        raise RuntimeError(f"{label} SHA mismatch expected={expected} actual={got}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-config", type=Path, default=BASE_CONFIG)
    ap.add_argument("--v2-config", type=Path, default=V2_CONFIG)
    ap.add_argument("--input", type=Path, default=INPUT)
    ap.add_argument("--input-freeze", type=Path, default=INPUT_FREEZE)
    ap.add_argument("--original-answers", type=Path, default=ORIGINAL_ANSWERS)
    ap.add_argument("--original-freeze", type=Path, default=ORIGINAL_FREEZE)
    ap.add_argument("--model-file", type=Path, default=MODEL)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args()

    require_sha(args.input, EXPECTED["input"], "V2 answer input")
    require_sha(args.input_freeze, EXPECTED["input_freeze"], "V2 input freeze")
    require_sha(args.original_answers, EXPECTED["original_answers"], "original V2 answers")
    require_sha(args.original_freeze, EXPECTED["original_freeze"], "original answer freeze")
    require_sha(args.model_file, EXPECTED["gguf"], "Qwen GGUF")

    base_config = read_json(args.base_config)
    v2_config = read_json(args.v2_config)
    inputs = read_json(args.input)
    original_freeze = read_json(args.original_freeze)
    if v2_config.get("status") != "FROZEN_BEFORE_V2_ANSWER_GENERATION":
        raise RuntimeError("V2 config status mismatch")
    if inputs.get("status") != "FROZEN_CONTEXT_FEASIBLE_INPUT_V2":
        raise RuntimeError("V2 input status mismatch")
    if original_freeze.get("status") != "FROZEN_BEFORE_V2_ANSWER_PAIR_JUDGING":
        raise RuntimeError("original answer freeze status mismatch")

    cases = list(inputs.get("cases") or [])
    if len(cases) != 81 or int(inputs.get("condition_count") or 0) != 162:
        raise RuntimeError("expected frozen 81-query / 162-condition V2 subset")

    original_rows = read_jsonl(args.original_answers)
    original: dict[tuple[str, str], dict] = {}
    for row in original_rows:
        key = (str(row["query_id"]), str(row["condition"]))
        if key in original:
            raise RuntimeError(f"duplicate original answer {key}")
        original[key] = row
    if len(original) != 162:
        raise RuntimeError(f"expected 162 original answers, got {len(original)}")

    generation = base_config["generator"]
    if int(generation["context_size"]) != 16384 or int(generation["max_tokens"]) != 384:
        raise RuntimeError("generation contract changed")

    base = args.base_url.rstrip("/")
    models = http_json("GET", base + "/models", None, args.timeout).get("data") or []
    if len(models) != 1:
        raise RuntimeError(f"expected exactly one llama.cpp model, found {len(models)}")
    model_id = str(models[0].get("id") or "")
    if not model_id:
        raise RuntimeError("empty llama.cpp model ID")

    args.out.mkdir(parents=True, exist_ok=True)
    repeat_path = args.out / "same_evidence_repeat_rows.jsonl"
    summary_path = args.out / "same_evidence_control_summary.json"
    freeze_path = args.out / "same_evidence_control_freeze.json"
    if freeze_path.exists():
        raise RuntimeError("SAME_EVIDENCE_CONTROL_ALREADY_FROZEN; refusing mutation")

    done: dict[tuple[str, str], dict] = {}
    for row in read_jsonl(repeat_path):
        key = (str(row["query_id"]), str(row["condition"]))
        if key in done:
            raise RuntimeError(f"duplicate existing repeat row {key}")
        if row.get("original_answers_sha256") != EXPECTED["original_answers"]:
            raise RuntimeError(f"repeat row belongs to a different original answer file {key}")
        done[key] = row

    planned = [(case, pid) for case in cases for pid in PROFILE_IDS]
    print("C2_SAME_EVIDENCE_CONTROL_START")
    print(f"PLANNED={len(planned)} RESUME_COMPLETED={len(done)}")
    started = time.time()

    for case, condition in planned:
        qid = str(case["query_id"])
        key = (qid, condition)
        if key in done:
            continue
        orig = original[key]
        cond = case["conditions"][condition]
        messages = build_messages(base_config, str(case["query_text"]), str(cond["serialized_evidence"]))
        prompt_material = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        prompt_sha = sha_text(prompt_material)
        if prompt_sha != str(orig["prompt_sha256"]):
            raise RuntimeError(f"prompt SHA changed for {key}")
        if str(cond["serialized_evidence_sha256"]) != str(orig["serialized_evidence_sha256"]):
            raise RuntimeError(f"evidence SHA changed for {key}")

        request_body = {
            "model": model_id,
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
            raise RuntimeError(f"no completion for {key}")
        answer = str((choices[0].get("message") or {}).get("content") or "").strip()
        if not answer:
            raise RuntimeError(f"empty repeated answer for {key}")
        repeated_sha = sha_text(answer)
        row = {
            "artifact": "SECOND_CORPUS_C2_SAME_EVIDENCE_REPEAT_V1",
            "query_id": qid,
            "condition": condition,
            "prompt_sha256": prompt_sha,
            "serialized_evidence_sha256": cond["serialized_evidence_sha256"],
            "original_answer_sha256": orig["answer_sha256"],
            "repeated_answer_sha256": repeated_sha,
            "exact_match_original": repeated_sha == orig["answer_sha256"],
            "original_answers_sha256": EXPECTED["original_answers"],
            "gguf_sha256": EXPECTED["gguf"],
            "finish_reason": choices[0].get("finish_reason"),
        }
        append_jsonl(repeat_path, row)
        done[key] = row
        if len(done) == 1 or len(done) % 10 == 0 or len(done) == len(planned):
            print(f"C2_SAME_EVIDENCE_REPEAT_PASS {len(done)}/{len(planned)} query={qid} condition={condition}", flush=True)

    if len(done) != len(planned):
        raise RuntimeError(f"repeat incomplete {len(done)}/{len(planned)}")

    canonical = [done[(str(case["query_id"]), pid)] for case in cases for pid in PROFILE_IDS]
    atomic_text(repeat_path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in canonical))
    matches = sum(bool(r["exact_match_original"]) for r in canonical)
    failures = [
        {"query_id": r["query_id"], "condition": r["condition"], "original_answer_sha256": r["original_answer_sha256"], "repeated_answer_sha256": r["repeated_answer_sha256"]}
        for r in canonical if not r["exact_match_original"]
    ]
    summary = {
        "artifact": "SECOND_CORPUS_C2_SAME_EVIDENCE_CONTROL_SUMMARY_V1",
        "scientific_status": "post-hoc deterministic platform validation; does not alter frozen answer-drift endpoint",
        "condition_count": len(canonical),
        "query_count": len(cases),
        "exact_match_count": matches,
        "exact_match_rate": matches / len(canonical),
        "failure_count": len(failures),
        "failures": failures,
        "original_answers_sha256": EXPECTED["original_answers"],
        "original_answer_freeze_sha256": EXPECTED["original_freeze"],
        "input_sha256": EXPECTED["input"],
        "input_freeze_sha256": EXPECTED["input_freeze"],
        "gguf_sha256": EXPECTED["gguf"],
        "repeat_rows_sha256": sha_file(repeat_path),
        "elapsed_seconds_this_invocation": time.time() - started,
    }
    atomic_json(summary_path, summary)
    freeze = {
        "artifact": "SECOND_CORPUS_C2_SAME_EVIDENCE_CONTROL_FREEZE_V1",
        "status": "FROZEN_POSTHOC_PLATFORM_VALIDATION",
        "runner_sha256": sha_file(Path(__file__)),
        "summary_sha256": sha_file(summary_path),
        "repeat_rows_sha256": sha_file(repeat_path),
        "exact_match_count": matches,
        "condition_count": len(canonical),
        "original_answer_freeze_sha256": EXPECTED["original_freeze"],
    }
    atomic_json(freeze_path, freeze)
    print("C2_SAME_EVIDENCE_CONTROL_FROZEN")
    print(json.dumps({
        "condition_count": len(canonical),
        "exact_match_count": matches,
        "exact_match_rate": matches / len(canonical),
        "failure_count": len(failures),
        "summary_sha256": sha_file(summary_path),
        "freeze_sha256": sha_file(freeze_path),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
