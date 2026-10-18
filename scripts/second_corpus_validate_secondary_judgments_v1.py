#!/usr/bin/env python3
"""Validate and hash one blinded C2 secondary-judge judgment file.

This is intentionally validation-only: it does not compute grade counts, material
rates, agreement metrics, or any scientific summary. Run separately for Gemini
and Claude before the cross-judge analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_PACKET_SHA256 = "0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa"
EXPECTED_PAIR_COUNT = 81


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise RuntimeError(f"invalid JSONL line {line_no}: {exc}") from exc
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--judgments", type=Path, required=True)
    ap.add_argument("--judge-id", required=True, choices=[
        "GEMINI_C2_SECONDARY_JUDGE_V1",
        "CLAUDE_C2_SECONDARY_JUDGE_V1",
    ])
    args = ap.parse_args()

    if not args.packet.is_file():
        raise RuntimeError(f"missing blinded packet: {args.packet}")
    if not args.judgments.is_file():
        raise RuntimeError(f"missing judgment file: {args.judgments}")
    if sha256_file(args.packet) != EXPECTED_PACKET_SHA256:
        raise RuntimeError("blinded packet SHA mismatch")

    packet = load_json(args.packet)
    pairs = list(packet.get("pairs") or [])
    if int(packet.get("pair_count") or 0) != EXPECTED_PAIR_COUNT or len(pairs) != EXPECTED_PAIR_COUNT:
        raise RuntimeError("unexpected blinded packet pair count")

    rows = load_jsonl(args.judgments)
    if len(rows) != EXPECTED_PAIR_COUNT:
        raise RuntimeError(f"expected {EXPECTED_PAIR_COUNT} judgment rows, got {len(rows)}")

    expected = [(str(p["pair_id"]), str(p["query_id"])) for p in pairs]
    seen = set()
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"row {idx+1} is not an object")
        pair_id = str(row.get("pair_id") or "")
        query_id = str(row.get("query_id") or "")
        if (pair_id, query_id) != expected[idx]:
            raise RuntimeError(
                f"row {idx+1} identity/order mismatch: expected {expected[idx]}, got {(pair_id, query_id)}"
            )
        if pair_id in seen:
            raise RuntimeError(f"duplicate pair_id: {pair_id}")
        seen.add(pair_id)
        grade = row.get("grade")
        if isinstance(grade, bool) or not isinstance(grade, int) or grade not in (0, 1, 2, 3):
            raise RuntimeError(f"invalid grade at row {idx+1}: {grade!r}")
        note = row.get("note", "")
        if note is not None and not isinstance(note, str):
            raise RuntimeError(f"note must be string/null at row {idx+1}")

    print("C2_SECONDARY_JUDGMENTS_VALIDATION_PASS")
    print(json.dumps({
        "judge_id": args.judge_id,
        "pair_count": len(rows),
        "blinded_packet_sha256": EXPECTED_PACKET_SHA256,
        "judgments_sha256": sha256_file(args.judgments),
        "aggregate_results_computed": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
