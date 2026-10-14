from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config" / "rq3_answer_drift_protocol.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_messages(protocol: dict[str, Any], query: str, evidence: str) -> list[dict[str, str]]:
    system = str(protocol["prompt"]["system"])
    user = str(protocol["prompt"]["user_template"]).format(query=query, evidence=evidence)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one frozen PiPi Benchmark V2 RQ3 generator through a local llama.cpp server.")
    parser.add_argument("--model-key", required=True, choices=["qwen3-8b-q4km", "ministral3-8b-q4km", "gemma3-4b-q4km"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "rq3")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    protocol_bytes = PROTOCOL_PATH.read_bytes()
    protocol_sha = sha256_bytes(protocol_bytes)
    protocol = json.loads(protocol_bytes)
    input_bytes = args.input.read_bytes()
    input_sha = sha256_bytes(input_bytes)
    inputs = json.loads(input_bytes)
    manifest = load_json(args.freeze_manifest)

    if manifest.get("artifact") != "pipi-benchmark-v2-rq3-input-freeze":
        raise SystemExit("RQ3_GENERATION_REFUSED_INVALID_FREEZE_MANIFEST")
    if manifest.get("rq3_protocol_sha256") != protocol_sha:
        raise SystemExit("RQ3_GENERATION_REFUSED_PROTOCOL_SHA_MISMATCH")
    if manifest.get("rq3_input_sha256") != input_sha:
        raise SystemExit("RQ3_GENERATION_REFUSED_INPUT_SHA_MISMATCH")
    if manifest.get("status") != "frozen-before-answer-generation":
        raise SystemExit("RQ3_GENERATION_REFUSED_MANIFEST_NOT_FROZEN")
    if inputs.get("status") != "prepared-before-generation-awaiting-freeze-manifest":
        raise SystemExit("RQ3_GENERATION_REFUSED_INPUT_STATUS")
    if inputs.get("rq3_protocol_sha256") != protocol_sha:
        raise SystemExit("RQ3_GENERATION_REFUSED_INPUT_PROTOCOL_SHA")
    if int(inputs.get("case_count") or 0) != 192:
        raise SystemExit("RQ3_GENERATION_REFUSED_CASE_COUNT")

    model_cfg = protocol["models"][args.model_key]
    frozen_models = manifest.get("models") if isinstance(manifest.get("models"), dict) else {}
    frozen_model = frozen_models.get(args.model_key) if isinstance(frozen_models.get(args.model_key), dict) else None
    if not frozen_model:
        raise SystemExit(f"RQ3_GENERATION_REFUSED_MODEL_NOT_IN_FREEZE_MANIFEST {args.model_key}")
    if frozen_model.get("gguf_sha256") != model_cfg.get("gguf_sha256"):
        raise SystemExit("RQ3_GENERATION_REFUSED_MODEL_HASH_MISMATCH")

    client = httpx.Client(base_url=args.base_url.rstrip("/") + "/", timeout=args.timeout)
    model_payload = client.get("models")
    model_payload.raise_for_status()
    models = model_payload.json().get("data") or []
    if len(models) != 1:
        raise SystemExit(f"Expected exactly one model in llama.cpp server, found {len(models)}")
    server_model_id = str(models[0].get("id") or "")

    generation = protocol["generation"]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"rq3_answers_{args.model_key}_{input_sha[:12]}.jsonl"
    summary_path = output_dir / f"rq3_answers_{args.model_key}_{input_sha[:12]}_summary.json"

    completed: set[tuple[str, str, str]] = set()
    if jsonl_path.is_file():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            completed.add((str(row["case_id"]), str(row["condition"]), str(row.get("run_kind") or "main")))

    planned: list[tuple[dict[str, Any], str, str]] = []
    for case in inputs["cases"]:
        for condition in protocol["retrieval_profiles"]:
            planned.append((case, condition, "main"))
    if protocol["same_evidence_stability_control"]["enabled"]:
        for case in inputs["cases"]:
            if bool(case.get("double_annotation")):
                planned.append((case, "hybrid-e5-content-v1", "same-evidence-repeat"))

    print("PiPi Benchmark V2 RQ3 generation")
    print(f"MODEL_KEY={args.model_key}")
    print(f"SERVER_MODEL_ID={server_model_id}")
    print(f"RQ3_PROTOCOL_SHA256={protocol_sha}")
    print(f"RQ3_INPUT_SHA256={input_sha}")
    print(f"PLANNED={len(planned)} ALREADY_COMPLETED={len(completed)}")

    started = time.time()
    made = 0
    for case, condition, run_kind in planned:
        key = (str(case["case_id"]), condition, run_kind)
        if key in completed:
            continue
        cond = case["conditions"][condition]
        messages = build_messages(protocol, str(case["query_text"]), str(cond["serialized_evidence"]))
        request_body = {
            "model": server_model_id,
            "messages": messages,
            "temperature": float(generation["temperature"]),
            "top_p": float(generation["top_p"]),
            "seed": int(generation["seed"]),
            "max_tokens": int(generation["max_tokens"]),
            "stream": False,
        }
        response = client.post("chat/completions", json=request_body)
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"No completion choice for {key}")
        answer = str(((choices[0].get("message") or {}).get("content")) or "").strip()
        if not answer:
            raise RuntimeError(f"Empty completion for {key}")

        prompt_material = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        row = {
            "artifact": "pipi-benchmark-v2-rq3-answer",
            "schema_version": 1,
            "case_id": str(case["case_id"]),
            "model_key": args.model_key,
            "server_model_id": server_model_id,
            "condition": condition,
            "run_kind": run_kind,
            "rq3_protocol_sha256": protocol_sha,
            "rq3_input_sha256": input_sha,
            "gguf_sha256": model_cfg["gguf_sha256"],
            "query_text": str(case["query_text"]),
            "serialized_evidence_sha256": cond["serialized_evidence_sha256"],
            "ordered_evidence_identity_sha256": cond["ordered_evidence_identity_sha256"],
            "prompt_sha256": sha256_bytes(prompt_material.encode("utf-8")),
            "answer": answer,
            "answer_sha256": sha256_bytes(answer.encode("utf-8")),
            "finish_reason": choices[0].get("finish_reason"),
            "usage": payload.get("usage"),
            "generation": {
                "temperature": generation["temperature"],
                "top_p": generation["top_p"],
                "seed": generation["seed"],
                "max_tokens": generation["max_tokens"],
            },
        }
        with jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
        completed.add(key)
        made += 1
        if made == 1 or made % 20 == 0:
            print(f"NEW_COMPLETIONS={made} TOTAL_COMPLETED={len(completed)}/{len(planned)}")

    client.close()
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    main_rows = [r for r in rows if r.get("run_kind") == "main"]
    control_rows = [r for r in rows if r.get("run_kind") == "same-evidence-repeat"]
    expected_main = 192 * 2
    expected_control = 48
    status = "complete" if len(main_rows) == expected_main and len(control_rows) == expected_control else "incomplete"
    output_sha = sha256_bytes(jsonl_path.read_bytes())
    summary = {
        "artifact": "pipi-benchmark-v2-rq3-model-generation-summary",
        "schema_version": 1,
        "status": status,
        "model_key": args.model_key,
        "server_model_id": server_model_id,
        "gguf_sha256": model_cfg["gguf_sha256"],
        "rq3_protocol_sha256": protocol_sha,
        "rq3_input_sha256": input_sha,
        "main_count": len(main_rows),
        "same_evidence_control_count": len(control_rows),
        "expected_main_count": expected_main,
        "expected_same_evidence_control_count": expected_control,
        "answers_jsonl": str(jsonl_path),
        "answers_jsonl_sha256": output_sha,
        "elapsed_seconds_this_invocation": time.time() - started,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"STATUS={status}")
    print(f"MAIN={len(main_rows)}/{expected_main}")
    print(f"SAME_EVIDENCE_CONTROL={len(control_rows)}/{expected_control}")
    print(f"ANSWERS_JSONL={jsonl_path}")
    print(f"ANSWERS_JSONL_SHA256={output_sha}")
    print(f"SUMMARY={summary_path}")


if __name__ == "__main__":
    main()
