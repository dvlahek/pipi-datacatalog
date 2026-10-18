#!/usr/bin/env python3
"""Prepare the frozen three-rater C2 human answer-drift audit packet.

The script samples all 19 strict hidden-drift pairs plus 25 deterministic
controls from the already-frozen 81-pair blinded Qwen C2 packet. It never opens
the private retrieval-profile A/B key or prior LLM grades.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLINDED = ROOT / "results" / "second_corpus_answer_drift_v2_context_feasible" / "qwen_answer_pairs_v2_blinded.json"
PER_QUERY = ROOT / "results" / "second_corpus_confirmation_v1" / "per_query_metrics.jsonl"
OUT = ROOT / "results" / "second_corpus_human_audit_v1"
PROTOCOL = ROOT / "docs" / "second_corpus_human_audit_protocol_v1.md"

EXPECTED_BLINDED_SHA = "0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa"
EXPECTED_PER_QUERY_SHA = "794be7b504060580910fbc7f8e13274c604cfbdcffaa33781c333b7ad7e94b0b"
SEED = "SECOND_CORPUS_C2_HUMAN_AUDIT_V1"
RATERS = ("colleague_1", "colleague_2", "author")


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def require_sha(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")
    actual = sha_file(path)
    if actual != expected:
        raise RuntimeError(f"{label} SHA mismatch expected={expected} actual={actual}")


def hsort(tag: str, pair_id: str) -> str:
    return sha_text(f"{SEED}|{tag}|{pair_id}")


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["audit_id", "query", "answer_A", "answer_B", "human_grade_0_3", "notes"])
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def main() -> None:
    require_sha(BLINDED, EXPECTED_BLINDED_SHA, "C2 blinded packet")
    require_sha(PER_QUERY, EXPECTED_PER_QUERY_SHA, "C2 per-query metrics")
    if not PROTOCOL.is_file():
        raise RuntimeError(f"missing frozen human-audit protocol: {PROTOCOL}")

    OUT.mkdir(parents=True, exist_ok=True)
    freeze_path = OUT / "human_audit_packet_freeze.json"
    if freeze_path.exists():
        raise RuntimeError("C2_HUMAN_AUDIT_PACKET_ALREADY_FROZEN; refusing overwrite")

    packet = read_json(BLINDED)
    metrics = read_jsonl(PER_QUERY)
    pairs = list(packet.get("pairs") or [])
    if len(pairs) != 81:
        raise RuntimeError(f"expected 81 blinded C2 pairs, got {len(pairs)}")
    pair_by_qid = {str(p["query_id"]): p for p in pairs}
    if len(pair_by_qid) != 81:
        raise RuntimeError("duplicate query IDs in blinded packet")
    metric_by_qid = {str(r["query_id"]): r for r in metrics}
    if len(metric_by_qid) != 96:
        raise RuntimeError("unexpected per-query metric count")

    strict: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for pair in pairs:
        qid = str(pair["query_id"])
        m = metric_by_qid.get(qid)
        if m is None:
            raise RuntimeError(f"missing retrieval metrics for {qid}")
        is_strict = abs(float(m["dataset_jaccard_at_10"]) - 1.0) <= 1e-12 and float(m["chunk_churn_at_10"]) > 0.0
        (strict if is_strict else remaining).append(pair)
    if len(strict) != 19 or len(remaining) != 62:
        raise RuntimeError(f"unexpected strict/control frame counts strict={len(strict)} remaining={len(remaining)}")

    controls = sorted(remaining, key=lambda p: hsort("CONTROL", str(p["pair_id"])))[:25]
    selected_ids = {str(p["pair_id"]) for p in strict + controls}
    if len(selected_ids) != 44:
        raise RuntimeError("human audit sample contains duplicate pair IDs")
    selected = sorted(strict + controls, key=lambda p: hsort("ORDER", str(p["pair_id"])))
    strict_ids = {str(p["pair_id"]) for p in strict}

    private_rows = []
    rater_rows = []
    for i, pair in enumerate(selected, 1):
        audit_id = f"C2H{i:03d}"
        qid = str(pair["query_id"])
        pid = str(pair["pair_id"])
        query = str(pair["query_text"])
        answer_a = str(pair["answer_a"])
        answer_b = str(pair["answer_b"])
        content_fingerprint = sha_text("\0".join([query, answer_a, answer_b]))
        private_rows.append({
            "audit_id": audit_id,
            "pair_id": pid,
            "query_id": qid,
            "stratum": "strict_hidden" if pid in strict_ids else "control",
            "query_type": pair.get("query_type"),
            "theme": pair.get("theme"),
            "content_fingerprint_sha256": content_fingerprint,
        })
        rater_rows.append({
            "audit_id": audit_id,
            "query": query,
            "answer_A": answer_a,
            "answer_B": answer_b,
            "human_grade_0_3": "",
            "notes": "",
        })

    private_manifest = {
        "artifact": "SECOND_CORPUS_C2_HUMAN_AUDIT_PRIVATE_SAMPLE_V1",
        "status": "PRIVATE_UNTIL_ALL_HUMAN_RATINGS_FROZEN",
        "seed_sha256": sha_text(SEED),
        "sampling_rule": "all 19 strict hidden-drift pairs plus first 25 remaining pairs by SHA256(seed|CONTROL|pair_id); final order by SHA256(seed|ORDER|pair_id)",
        "sample_count": 44,
        "strict_hidden_count": 19,
        "control_count": 25,
        "rows": private_rows,
    }
    private_path = OUT / "human_audit_sampling_PRIVATE.json"
    atomic_json(private_path, private_manifest)

    rater_paths = {}
    for rater in RATERS:
        path = OUT / f"c2_human_audit_{rater}.csv"
        write_csv(path, rater_rows)
        rater_paths[rater] = path

    instructions = OUT / "HUMAN_AUDIT_INSTRUCTIONS.txt"
    instructions.write_text(
        "C2 HUMAN ANSWER-DRIFT AUDIT\n\n"
        "Rate each pair independently. Do not discuss cases with the other raters until all three files are complete.\n"
        "Do not look up prior LLM grades, retrieval profiles, or aggregate C2 results.\n\n"
        "Rubric:\n"
        "0 = semantically the same; wording-only differences\n"
        "1 = minor difference; same substantive conclusion\n"
        "2 = materially different content, support, qualification, or conclusion\n"
        "3 = substantially different or contradictory\n\n"
        "Fill only human_grade_0_3 with 0, 1, 2, or 3. Notes are optional.\n"
        "Judge semantic change between Answer A and Answer B, not which system is better.\n",
        encoding="utf-8",
    )

    freeze = {
        "artifact": "SECOND_CORPUS_C2_HUMAN_AUDIT_PACKET_FREEZE_V1",
        "status": "FROZEN_BEFORE_ANY_C2_HUMAN_RATINGS",
        "scientific_status": "post-hoc human validation; frozen C2 H1/H2/H3 and LLM judgments unchanged",
        "protocol_sha256": sha_file(PROTOCOL),
        "blinded_packet_sha256": sha_file(BLINDED),
        "per_query_metrics_sha256": sha_file(PER_QUERY),
        "private_sampling_manifest_sha256": sha_file(private_path),
        "sample_count": 44,
        "strict_hidden_count": 19,
        "control_count": 25,
        "rater_roles": list(RATERS),
        "rater_packet_sha256": {r: sha_file(p) for r, p in rater_paths.items()},
        "instructions_sha256": sha_file(instructions),
        "ratings_present": False,
    }
    atomic_json(freeze_path, freeze)

    print("C2_HUMAN_AUDIT_PACKET_FROZEN")
    print(json.dumps({
        "sample_count": 44,
        "strict_hidden_count": 19,
        "control_count": 25,
        "rater_files": {r: str(p.relative_to(ROOT)) for r, p in rater_paths.items()},
        "private_sampling_manifest_sha256": sha_file(private_path),
        "packet_freeze_sha256": sha_file(freeze_path),
        "ratings_present": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
