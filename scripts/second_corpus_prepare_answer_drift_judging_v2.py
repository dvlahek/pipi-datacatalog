#!/usr/bin/env python3
"""Prepare and freeze the blinded C2 V2 Qwen answer-pair judging packet.

This script runs only after the V2 generation freeze. It verifies the frozen
81-query / 162-answer chain, deterministically assigns A/B orientation from the
pre-existing blinding seed, writes the blinded judging packet and a separate
local mapping, and stops before any grade is supplied.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V1_CONFIG = ROOT / "config" / "second_corpus_answer_drift_qwen_v1.json"
V2_INPUT = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2.json"
V2_INPUT_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "answer_drift_input_v2_freeze.json"
ANSWERS = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "qwen_answers_v2.jsonl"
ANSWERS_FREEZE = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "qwen_answers_v2_freeze.json"
OUT = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible"

EXPECTED_ANSWERS_SHA256 = "c59a19c51cb05395cb4fbee23edb601f8f3b68e23940c14a54fbac5d434627b3"
EXPECTED_ANSWERS_FREEZE_SHA256 = "e03a321671b7e5f243d033ff506862c12c5b089ad2066a5b99711ed131df64ed"
EXPECTED_QUERY_COUNT = 81
EXPECTED_ANSWER_COUNT = 162
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


def pair_orientation(seed: str, query_id: str) -> bool:
    """Return True when profile order should be swapped for blinded A/B."""
    digest = hashlib.sha256(f"{seed}|{query_id}".encode("utf-8")).digest()
    return bool(digest[0] & 1)


def pair_id(seed: str, query_id: str) -> str:
    return hashlib.sha256(f"{seed}|PAIR|{query_id}".encode("utf-8")).hexdigest()[:20]


def main() -> None:
    required = [V1_CONFIG, V2_INPUT, V2_INPUT_FREEZE, ANSWERS, ANSWERS_FREEZE]
    for p in required:
        if not p.is_file():
            raise RuntimeError(f"missing required frozen input: {p}")

    packet_path = OUT / "qwen_answer_pairs_v2_blinded.json"
    mapping_path = OUT / "qwen_answer_pairs_v2_mapping_PRIVATE.json"
    template_path = OUT / "qwen_answer_pairs_v2_judgments_template.jsonl"
    freeze_path = OUT / "qwen_answer_pairs_v2_blinding_freeze.json"
    sums_path = OUT / "SHA256SUMS.qwen_answer_pairs_v2_blinding.txt"
    for p in (packet_path, mapping_path, template_path, freeze_path, sums_path):
        if p.exists():
            raise RuntimeError(f"JUDGING_PACKET_ALREADY_EXISTS; refusing to overwrite: {p}")

    if sha_file(ANSWERS) != EXPECTED_ANSWERS_SHA256:
        raise RuntimeError("V2 answers SHA mismatch")
    if sha_file(ANSWERS_FREEZE) != EXPECTED_ANSWERS_FREEZE_SHA256:
        raise RuntimeError("V2 answers freeze SHA mismatch")

    cfg = read_json(V1_CONFIG)
    v2_input = read_json(V2_INPUT)
    input_freeze = read_json(V2_INPUT_FREEZE)
    answers_freeze = read_json(ANSWERS_FREEZE)

    if answers_freeze.get("status") != "FROZEN_BEFORE_V2_ANSWER_PAIR_JUDGING":
        raise RuntimeError("V2 answer freeze status mismatch")
    if int(answers_freeze.get("query_count") or 0) != EXPECTED_QUERY_COUNT:
        raise RuntimeError("unexpected frozen V2 query count")
    if int(answers_freeze.get("answer_count") or 0) != EXPECTED_ANSWER_COUNT:
        raise RuntimeError("unexpected frozen V2 answer count")
    if answers_freeze.get("answers_sha256") != EXPECTED_ANSWERS_SHA256:
        raise RuntimeError("answers freeze does not bind expected answers SHA")
    if answers_freeze.get("answer_drift_input_v2_sha256") != sha_file(V2_INPUT):
        raise RuntimeError("answer freeze does not bind current V2 input")
    if answers_freeze.get("input_freeze_v2_sha256") != sha_file(V2_INPUT_FREEZE):
        raise RuntimeError("answer freeze does not bind current V2 input freeze")

    seed = str(cfg["judging"]["blinding_seed"])
    if seed != "SECOND_CORPUS_C2_ANSWER_DRIFT_BLIND_V1":
        raise RuntimeError("unexpected frozen blinding seed")
    rubric = cfg["judging"]["ordinal_scale"]
    material_threshold = list(cfg["judging"]["material_threshold"])

    cases = list(v2_input.get("cases") or [])
    if len(cases) != EXPECTED_QUERY_COUNT:
        raise RuntimeError(f"expected {EXPECTED_QUERY_COUNT} V2 cases, got {len(cases)}")
    case_by_qid = {str(c["query_id"]): c for c in cases}
    if len(case_by_qid) != EXPECTED_QUERY_COUNT:
        raise RuntimeError("duplicate query IDs in V2 input")

    answer_rows = read_jsonl(ANSWERS)
    if len(answer_rows) != EXPECTED_ANSWER_COUNT:
        raise RuntimeError(f"expected {EXPECTED_ANSWER_COUNT} answer rows, got {len(answer_rows)}")
    answer_map: dict[tuple[str, str], dict] = {}
    for row in answer_rows:
        qid = str(row.get("query_id") or "")
        condition = str(row.get("condition") or "")
        if qid not in case_by_qid or condition not in PROFILE_IDS:
            raise RuntimeError(f"unexpected answer identity: {(qid, condition)}")
        key = (qid, condition)
        if key in answer_map:
            raise RuntimeError(f"duplicate answer identity: {key}")
        answer_map[key] = row

    blinded_pairs: list[dict] = []
    mapping_rows: list[dict] = []
    judgment_lines: list[str] = []

    for case in cases:
        qid = str(case["query_id"])
        content = answer_map[(qid, PROFILE_IDS[0])]
        metadata = answer_map[(qid, PROFILE_IDS[1])]
        swapped = pair_orientation(seed, qid)
        if swapped:
            a, b = metadata, content
            a_condition, b_condition = PROFILE_IDS[1], PROFILE_IDS[0]
        else:
            a, b = content, metadata
            a_condition, b_condition = PROFILE_IDS[0], PROFILE_IDS[1]

        pid = pair_id(seed, qid)
        blinded_pairs.append({
            "pair_id": pid,
            "query_id": qid,
            "theme": case["theme"],
            "query_type": case["query_type"],
            "query_text": case["query_text"],
            "answer_a": a["answer"],
            "answer_b": b["answer"],
            "answer_a_sha256": a["answer_sha256"],
            "answer_b_sha256": b["answer_sha256"],
        })
        mapping_rows.append({
            "pair_id": pid,
            "query_id": qid,
            "answer_a_condition": a_condition,
            "answer_b_condition": b_condition,
            "swapped": swapped,
        })
        judgment_lines.append(json.dumps({
            "pair_id": pid,
            "query_id": qid,
            "grade": None,
            "note": "",
        }, ensure_ascii=False, sort_keys=True))

    packet = {
        "artifact": "SECOND_CORPUS_C2_QWEN_V2_BLINDED_JUDGING_PACKET",
        "status": "FROZEN_BEFORE_V2_ANSWER_PAIR_JUDGING",
        "scientific_status": "post-confirmatory descriptive context-feasible subset",
        "pair_count": EXPECTED_QUERY_COUNT,
        "coverage_rate": v2_input.get("coverage_rate"),
        "excluded_query_count": v2_input.get("excluded_query_count"),
        "answers_sha256": EXPECTED_ANSWERS_SHA256,
        "answers_freeze_sha256": EXPECTED_ANSWERS_FREEZE_SHA256,
        "profile_identity_hidden": True,
        "rubric": rubric,
        "material_threshold": material_threshold,
        "pairs": blinded_pairs,
    }
    atomic_json(packet_path, packet)

    mapping = {
        "artifact": "SECOND_CORPUS_C2_QWEN_V2_PRIVATE_AB_MAPPING",
        "status": "PRIVATE_UNTIL_ALL_JUDGMENTS_FROZEN",
        "seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "pair_count": EXPECTED_QUERY_COUNT,
        "rows": mapping_rows,
    }
    atomic_json(mapping_path, mapping)
    atomic_text(template_path, "\n".join(judgment_lines) + "\n")

    freeze = {
        "artifact": "SECOND_CORPUS_C2_QWEN_V2_BLINDING_FREEZE",
        "status": "FROZEN_BEFORE_V2_ANSWER_PAIR_JUDGING",
        "answers_sha256": EXPECTED_ANSWERS_SHA256,
        "answers_freeze_sha256": EXPECTED_ANSWERS_FREEZE_SHA256,
        "answer_drift_input_v2_sha256": sha_file(V2_INPUT),
        "input_freeze_v2_sha256": sha_file(V2_INPUT_FREEZE),
        "preparation_script_sha256": sha_file(Path(__file__)),
        "blinded_packet_sha256": sha_file(packet_path),
        "private_mapping_sha256": sha_file(mapping_path),
        "judgments_template_sha256": sha_file(template_path),
        "pair_count": EXPECTED_QUERY_COUNT,
        "profile_identity_hidden": True,
        "judgments_present": False,
    }
    atomic_json(freeze_path, freeze)

    paths = [V1_CONFIG, V2_INPUT, V2_INPUT_FREEZE, ANSWERS, ANSWERS_FREEZE, Path(__file__), packet_path, mapping_path, template_path, freeze_path]
    atomic_text(sums_path, "".join(f"{sha_file(p)}  {p.relative_to(ROOT)}\n" for p in paths))

    print("C2_QWEN_V2_BLINDED_JUDGING_PACKET_FROZEN")
    print(json.dumps({
        "pair_count": EXPECTED_QUERY_COUNT,
        "coverage_rate": v2_input.get("coverage_rate"),
        "blinded_packet_sha256": sha_file(packet_path),
        "private_mapping_sha256": sha_file(mapping_path),
        "judgments_template_sha256": sha_file(template_path),
        "blinding_freeze_sha256": sha_file(freeze_path),
        "judgments_present": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
