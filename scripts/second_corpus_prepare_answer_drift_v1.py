#!/usr/bin/env python3
"""Prepare and freeze C2 Qwen answer-drift inputs before any C2 answer generation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_9_100"
DEFAULT_QUERIES = ROOT / "results" / "second_corpus_queries_v1"
DEFAULT_RETRIEVAL = ROOT / "results" / "second_corpus_retrieval_v1"
DEFAULT_CONFIRMATION = ROOT / "results" / "second_corpus_confirmation_v1"
DEFAULT_OUT = ROOT / "results" / "second_corpus_answer_drift_v1"
DEFAULT_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v1.json"
DEFAULT_EXTENSION = ROOT / "docs" / "second_corpus_c2_answer_drift_extension_v1.md"
DEFAULT_C1_PROTOCOL = ROOT / "config" / "rq3_answer_drift_protocol.json"
DEFAULT_RETRIEVAL_RUNNER = ROOT / "scripts" / "second_corpus_run_retrieval_v1.py"
DEFAULT_GENERATION_RUNNER = ROOT / "scripts" / "second_corpus_run_answer_drift_qwen_v1.py"
DEFAULT_RETRIEVAL_CONFIG = ROOT / "config" / "second_corpus_retrieval_v1.json"
DEFAULT_MODEL = ROOT / "models" / "rq3" / "Qwen3-8B-Q4_K_M.gguf"
DEFAULT_LLAMA_VERSION = ROOT / "results" / "c2_llama_cpp_version.txt"
PROFILE_IDS = ("hybrid-e5-content-v1", "hybrid-e5-metadata-v1")
EXPECTED_CONFIRMATION_FREEZE = "e7bbe1bfd048103de047a816ebd48ae359a5a74b38f2462463e1a9be752ff841"
EXPECTED_RETRIEVAL_RUNS = "5138ae7d90906709b1b5f8792560c8ddde95b57a01614cafbc951e7542294383"
EXPECTED_QUERIES = "4257116b4d9ec417217b2030df58b5de3ba479fe0125f021a3ca50b7022699f7"


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def atomic_json(path: Path, obj: Any) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


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


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serialize_evidence(evidence: list[dict]) -> str:
    blocks = []
    for idx, item in enumerate(evidence, 1):
        blocks.append("\n".join([
            f"[E{idx}]",
            f"dataset_identifier: {item['dataset_identifier']}",
            f"distribution_identifier: {item['distribution_identifier']}",
            f"chunk_index: {item['chunk_index']}",
            f"file_path: {item.get('file_path') or ''}",
            "text:",
            str(item["text"]).strip(),
        ]))
    return "\n\n".join(blocks).strip()


def validate_c1_generation_contract(c1: dict, c2: dict) -> None:
    expected_model = c1["models"]["qwen3-8b-q4km"]
    g = c2["generator"]
    pairs = {
        "gguf_file": (expected_model["gguf_file"], g["gguf_file"]),
        "gguf_sha256": (expected_model["gguf_sha256"], g["gguf_sha256"]),
        "reasoning_mode": (expected_model["reasoning_mode"], g["reasoning_mode"]),
        "temperature": (c1["generation"]["temperature"], g["temperature"]),
        "top_p": (c1["generation"]["top_p"], g["top_p"]),
        "seed": (c1["generation"]["seed"], g["seed"]),
        "max_tokens": (c1["generation"]["max_tokens"], g["max_tokens"]),
        "max_answer_words": (c1["generation"]["max_answer_words"], g["max_answer_words"]),
        "context_size": (c1["generation"]["context_size"], g["context_size"]),
        "system_prompt": (c1["prompt"]["system"], c2["prompt"]["system"]),
        "user_template": (c1["prompt"]["user_template"], c2["prompt"]["user_template"]),
    }
    for key, (left, right) in pairs.items():
        if left != right:
            raise RuntimeError(f"C1/C2 generation contract mismatch {key}: {left!r} != {right!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    ap.add_argument("--retrieval", type=Path, default=DEFAULT_RETRIEVAL)
    ap.add_argument("--confirmation", type=Path, default=DEFAULT_CONFIRMATION)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--extension", type=Path, default=DEFAULT_EXTENSION)
    ap.add_argument("--c1-protocol", type=Path, default=DEFAULT_C1_PROTOCOL)
    ap.add_argument("--retrieval-runner", type=Path, default=DEFAULT_RETRIEVAL_RUNNER)
    ap.add_argument("--generation-runner", type=Path, default=DEFAULT_GENERATION_RUNNER)
    ap.add_argument("--retrieval-config", type=Path, default=DEFAULT_RETRIEVAL_CONFIG)
    ap.add_argument("--model-file", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--llama-version-file", type=Path, default=DEFAULT_LLAMA_VERSION)
    args = ap.parse_args()

    required = [
        args.corpus / "SHA256SUMS.prequery.txt",
        args.queries / "SHA256SUMS.query_freeze.txt",
        args.retrieval / "SHA256SUMS.retrieval.txt",
        args.retrieval / "primary_retrieval_runs.jsonl",
        args.confirmation / "SHA256SUMS.confirmation.txt",
        args.confirmation / "confirmation_freeze.json",
        args.config,
        args.extension,
        args.c1_protocol,
        args.retrieval_runner,
        args.generation_runner,
        args.retrieval_config,
        args.model_file,
        args.llama_version_file,
    ]
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"missing required frozen input: {path}")

    out = args.out
    input_path = out / "answer_drift_input.json"
    freeze_path = out / "answer_drift_input_freeze.json"
    sums_path = out / "SHA256SUMS.answer_drift_input.txt"
    if any(p.exists() for p in (input_path, freeze_path, sums_path)):
        raise RuntimeError("ANSWER_DRIFT_INPUT_ALREADY_EXISTS; refusing to overwrite")

    checked_prequery = verify_sha_manifest(args.corpus / "SHA256SUMS.prequery.txt")
    checked_queries = verify_sha_manifest(args.queries / "SHA256SUMS.query_freeze.txt")
    checked_retrieval = verify_sha_manifest(args.retrieval / "SHA256SUMS.retrieval.txt")
    checked_confirmation = verify_sha_manifest(args.confirmation / "SHA256SUMS.confirmation.txt")

    config = read_json(args.config)
    c1 = read_json(args.c1_protocol)
    validate_c1_generation_contract(c1, config)
    if config.get("status") != "FROZEN_BEFORE_ANY_C2_ANSWER_GENERATION":
        raise RuntimeError("C2 answer-drift config status mismatch")
    if sha_file(args.queries / "queries.jsonl") != EXPECTED_QUERIES:
        raise RuntimeError("queries hash mismatch")
    if sha_file(args.retrieval / "primary_retrieval_runs.jsonl") != EXPECTED_RETRIEVAL_RUNS:
        raise RuntimeError("retrieval runs hash mismatch")
    if sha_file(args.confirmation / "confirmation_freeze.json") != EXPECTED_CONFIRMATION_FREEZE:
        raise RuntimeError("confirmation freeze hash mismatch")
    if config["frozen_inputs"]["queries_sha256"] != EXPECTED_QUERIES:
        raise RuntimeError("config queries hash mismatch")
    if config["frozen_inputs"]["primary_retrieval_runs_sha256"] != EXPECTED_RETRIEVAL_RUNS:
        raise RuntimeError("config retrieval hash mismatch")
    if config["frozen_inputs"]["confirmation_freeze_sha256"] != EXPECTED_CONFIRMATION_FREEZE:
        raise RuntimeError("config confirmation hash mismatch")

    model_sha = sha_file(args.model_file)
    if model_sha != config["generator"]["gguf_sha256"]:
        raise RuntimeError(f"Qwen model SHA mismatch expected={config['generator']['gguf_sha256']} actual={model_sha}")
    llama_version = args.llama_version_file.read_text(encoding="utf-8-sig").strip()
    if not llama_version:
        raise RuntimeError("empty llama.cpp version file")

    retrieval_runner = load_module(args.retrieval_runner, "c2_retrieval_runner_for_answer_input")
    retrieval_cfg, selected, physical_chunks, queries = retrieval_runner.load_and_validate_inputs(
        args.corpus, args.queries, args.retrieval_config
    )
    logical_rows, logical_audit = retrieval_runner.build_logical_chunks(selected, physical_chunks)
    row_by_id = {r["logical_chunk_identity_sha256"]: r for r in logical_rows}
    if len(row_by_id) != len(logical_rows):
        raise RuntimeError("duplicate logical chunk identity during answer input preparation")

    runs = read_jsonl(args.retrieval / "primary_retrieval_runs.jsonl")
    run_map = {(r["query_id"], r["profile_id"]): r for r in runs}
    if len(run_map) != 192:
        raise RuntimeError(f"expected 192 unique retrieval runs, got {len(run_map)}")

    prepared_cases = []
    for query in queries:
        qid = query["query_id"]
        conditions = {}
        for profile_id in PROFILE_IDS:
            run = run_map[(qid, profile_id)]
            frozen_evidence = list(run.get("ordered_evidence") or [])
            if len(frozen_evidence) != 10:
                raise RuntimeError(f"expected top-10 evidence for {qid}/{profile_id}")
            records = []
            ordered_ids = []
            for rank, e in enumerate(frozen_evidence, 1):
                logical_id = str(e["logical_chunk_identity_sha256"])
                row = row_by_id.get(logical_id)
                if row is None:
                    raise RuntimeError(f"frozen evidence missing from logical corpus: {logical_id}")
                if row["dataset_id"] != e["dataset_id"] or row["distribution_id"] != e["distribution_id"]:
                    raise RuntimeError(f"frozen evidence identity mismatch: {qid}/{profile_id}/rank{rank}")
                if int(row["chunk_index"]) != int(e["chunk_index"]) or row["chunk_text_sha256"] != e["chunk_text_sha256"]:
                    raise RuntimeError(f"frozen evidence chunk mismatch: {qid}/{profile_id}/rank{rank}")
                records.append({
                    "evidence_index": rank,
                    "dataset_identifier": row["dataset_id"],
                    "distribution_identifier": row["distribution_id"],
                    "chunk_index": int(row["chunk_index"]),
                    "file_path": row.get("file_path"),
                    "text": row["chunk_text"],
                    "text_sha256": row["chunk_text_sha256"],
                    "logical_chunk_identity_sha256": logical_id,
                })
                ordered_ids.append(logical_id)
            serialized = serialize_evidence(records)
            conditions[profile_id] = {
                "profile_hash": run["profile_hash"],
                "top_k": 10,
                "ordered_evidence_identity_sha256": canonical_sha(ordered_ids),
                "serialized_evidence_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                "serialized_evidence": serialized,
                "evidence": records,
            }
        prepared_cases.append({
            "query_id": qid,
            "theme": query["theme"],
            "query_type": query["query_type"],
            "cell_replicate": int(query["cell_replicate"]),
            "query_text": query["query_text"],
            "query_text_sha256": query["query_text_sha256"],
            "conditions": conditions,
        })

    artifact = {
        "artifact": "SECOND_CORPUS_C2_ANSWER_DRIFT_INPUT_V1",
        "status": "PREPARED_BEFORE_C2_ANSWER_GENERATION",
        "scientific_status": config["scientific_status"],
        "config_sha256": sha_file(args.config),
        "confirmation_freeze_sha256": EXPECTED_CONFIRMATION_FREEZE,
        "primary_retrieval_runs_sha256": EXPECTED_RETRIEVAL_RUNS,
        "queries_sha256": EXPECTED_QUERIES,
        "query_count": len(prepared_cases),
        "condition_count": len(prepared_cases) * 2,
        "profile_ids": list(PROFILE_IDS),
        "top_k": 10,
        "contains_chunk_text": True,
        "publication_safe": False,
        "cases": prepared_cases,
    }
    atomic_json(input_path, artifact)

    freeze = {
        "artifact": "SECOND_CORPUS_C2_ANSWER_DRIFT_INPUT_FREEZE_V1",
        "status": "FROZEN_BEFORE_C2_ANSWER_GENERATION",
        "scientific_status": config["scientific_status"],
        "config_sha256": sha_file(args.config),
        "extension_document_sha256": sha_file(args.extension),
        "c1_rq3_protocol_sha256": sha_file(args.c1_protocol),
        "answer_drift_input_sha256": sha_file(input_path),
        "queries_sha256": EXPECTED_QUERIES,
        "primary_retrieval_runs_sha256": EXPECTED_RETRIEVAL_RUNS,
        "confirmation_freeze_sha256": EXPECTED_CONFIRMATION_FREEZE,
        "retrieval_runner_sha256": sha_file(args.retrieval_runner),
        "generation_runner_sha256": sha_file(args.generation_runner),
        "qwen_gguf_sha256": model_sha,
        "llama_cpp_version_file_sha256": sha_file(args.llama_version_file),
        "llama_cpp_version": llama_version,
        "query_count": 96,
        "condition_count": 192,
        "logical_audit": logical_audit,
        "verified_manifest_entries": {
            "prequery": checked_prequery,
            "query_freeze": checked_queries,
            "retrieval": checked_retrieval,
            "confirmation": checked_confirmation
        },
        "answers_generated": False,
    }
    atomic_json(freeze_path, freeze)
    paths = [
        args.config,
        args.extension,
        args.c1_protocol,
        args.retrieval_runner,
        args.generation_runner,
        args.llama_version_file,
        input_path,
        freeze_path,
    ]
    atomic_text(sums_path, "".join(f"{sha_file(p)}  {p.relative_to(ROOT)}\n" for p in paths))

    print("C2_ANSWER_DRIFT_INPUT_FROZEN")
    print(json.dumps({
        "query_count": 96,
        "condition_count": 192,
        "answer_drift_input_sha256": sha_file(input_path),
        "input_freeze_sha256": sha_file(freeze_path),
        "qwen_gguf_sha256": model_sha,
        "llama_cpp_version": llama_version,
        "answers_generated": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
