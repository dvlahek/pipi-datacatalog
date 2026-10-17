#!/usr/bin/env python3
"""Prepare the frozen C2 query-authoring packet before any retrieval run.

The script is deliberately retrieval-free. It verifies the complete pre-query
SHA-256 chain, reads only the frozen V2.9 corpus, deterministically assigns source
datasets to the 96 preregistered query slots, and exports metadata plus a small
set of representative frozen chunks for human query authoring.

It never mutates the frozen corpus and refuses to overwrite an existing packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEMES = ["ECON", "ENVI", "HEAL", "TRAN"]
QUERY_TYPES = [
    "exact_lookup",
    "entity_dataset_lookup",
    "relation_comparison",
    "topic_discovery",
    "semantic_paraphrase",
    "constraint_filtered_lookup",
]
TYPE_CODES = {
    "exact_lookup": "EXACT",
    "entity_dataset_lookup": "ENTITY",
    "relation_comparison": "REL",
    "topic_discovery": "TOPIC",
    "semantic_paraphrase": "PARA",
    "constraint_filtered_lookup": "CONST",
}
SOURCE_COUNTS = {
    "exact_lookup": 1,
    "entity_dataset_lookup": 1,
    "relation_comparison": 2,
    "topic_discovery": 1,
    "semantic_paraphrase": 1,
    "constraint_filtered_lookup": 1,
}
AUTHORING_GUIDANCE = {
    "exact_lookup": (
        "Write a natural query asking for a concrete fact or value explicitly supported by the frozen source content. "
        "Do not copy a full source sentence verbatim."
    ),
    "entity_dataset_lookup": (
        "Write a query that identifies or locates the source dataset through a named entity, dataset subject, place, organisation, or other explicit identifying context."
    ),
    "relation_comparison": (
        "Write one comparison or relationship query that meaningfully requires both frozen source datasets. Do not write two unrelated subquestions."
    ),
    "topic_discovery": (
        "Write a discovery-style query for information or data about the topic represented by the frozen source. Avoid exposing benchmark IDs."
    ),
    "semantic_paraphrase": (
        "Express the source concept with a genuine semantic paraphrase or synonyms instead of copying distinctive title wording. The intended answer must remain grounded in the source."
    ),
    "constraint_filtered_lookup": (
        "Write a lookup containing at least two explicit constraints grounded in the frozen metadata/content, such as topic, geography, publisher, time, format, or measured entity."
    ),
}
SEED = "SECOND_CORPUS_C2_QUERY_AUTHORING_V1"
QUERIES_PER_CELL = 4
REPRESENTATIVE_CHUNKS_PER_SOURCE = 6
EXPECTED_CORPUS_REVISION = "V2.9-target100-final-materialization-recovery"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_text(text: str) -> str:
    return sha_bytes(text.encode("utf-8"))


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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


def atomic_json(path: Path, obj: dict) -> None:
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    atomic_text(path, text)


def verify_sha_manifest(manifest_path: Path) -> int:
    checked = 0
    with manifest_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise RuntimeError(f"invalid SHA manifest line {line_no}: {line}")
            expected, rel = parts
            rel = rel.strip()
            if rel.startswith("*"):
                rel = rel[1:]
            path = Path(rel)
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists():
                raise RuntimeError(f"pre-query SHA target missing: {path}")
            actual = sha_file(path)
            if actual != expected:
                raise RuntimeError(
                    f"pre-query SHA mismatch: {path} expected={expected} actual={actual}"
                )
            checked += 1
    return checked


def representative_chunk_indices(n: int, k: int) -> list[int]:
    if n <= 0:
        return []
    if n <= k:
        return list(range(n))
    raw = [round(i * (n - 1) / (k - 1)) for i in range(k)]
    out = []
    seen = set()
    for idx in raw:
        if idx not in seen:
            out.append(idx)
            seen.add(idx)
    return out


def compact_distribution(dist: dict) -> dict:
    return {
        "distribution_id": dist["distribution_id"],
        "format": dist["format"],
        "chunk_count": int(dist["chunk_count"]),
        "payload_sha256": dist["payload_sha256"],
        "text_sha256": dist["text_sha256"],
        "byte_size": int(dist["byte_size"]),
        "license_values": dist.get("license_values"),
        "license_scope": dist.get("license_scope"),
    }


def source_context(row: dict, dataset_chunks: list[dict]) -> dict:
    chunks = sorted(
        dataset_chunks,
        key=lambda c: (str(c["distribution_id"]), int(c["chunk_index"])),
    )
    if not chunks:
        raise RuntimeError(f"selected dataset has no chunks: {row['theme']} {row['dataset_id']}")
    indices = representative_chunk_indices(len(chunks), REPRESENTATIVE_CHUNKS_PER_SOURCE)
    reps = []
    for pos in indices:
        c = chunks[pos]
        reps.append(
            {
                "distribution_id": c["distribution_id"],
                "chunk_index": int(c["chunk_index"]),
                "chunk_text_sha256": c["chunk_text_sha256"],
                "chunk_identity_sha256": c["chunk_identity_sha256"],
                "chunk_text": c["chunk_text"],
            }
        )
    return {
        "theme": row["theme"],
        "selection_number": int(row["selection_number"]),
        "dataset_id": row["dataset_id"],
        "title": row.get("title"),
        "description": row.get("description"),
        "publisher_key": row.get("publisher_key"),
        "dataset_chunk_count": len(chunks),
        "log1p_dataset_chunk_count": math.log1p(len(chunks)),
        "distributions": [compact_distribution(d) for d in row["distributions"]],
        "representative_chunks": reps,
    }


def deterministic_theme_sources(theme_rows: list[dict]) -> list[dict]:
    required = sum(SOURCE_COUNTS[t] * QUERIES_PER_CELL for t in QUERY_TYPES)
    if required != 28:
        raise RuntimeError(f"unexpected required source count per theme: {required}")
    scored = []
    for row in theme_rows:
        token = (
            f"{SEED}|{row['theme']}|{int(row['selection_number'])}|{row['dataset_id']}"
        )
        scored.append((sha_text(token), int(row["selection_number"]), row["dataset_id"], row))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return [x[3] for x in scored[:required]]


def build_assignments(selected: list[dict]) -> list[dict]:
    by_theme = {t: [r for r in selected if r["theme"] == t] for t in THEMES}
    assignments = []
    for theme in THEMES:
        if len(by_theme[theme]) != 100:
            raise RuntimeError(f"expected 100 selected datasets for {theme}, got {len(by_theme[theme])}")
        pool = deterministic_theme_sources(by_theme[theme])
        cursor = 0
        used_keys = set()
        for qtype in QUERY_TYPES:
            nsrc = SOURCE_COUNTS[qtype]
            for replicate in range(1, QUERIES_PER_CELL + 1):
                src_rows = pool[cursor : cursor + nsrc]
                cursor += nsrc
                if len(src_rows) != nsrc:
                    raise RuntimeError(f"source assignment exhausted for {theme} {qtype}")
                src_ids = [r["dataset_id"] for r in src_rows]
                src_keys = [(r["theme"], int(r["selection_number"])) for r in src_rows]
                if any(k in used_keys for k in src_keys):
                    raise RuntimeError(f"source reuse within theme assignment: {theme} {src_keys}")
                used_keys.update(src_keys)
                qid = f"C2-{theme}-{TYPE_CODES[qtype]}-{replicate:02d}"
                assignments.append(
                    {
                        "query_id": qid,
                        "theme": theme,
                        "query_type": qtype,
                        "cell_replicate": replicate,
                        "source_dataset_ids": src_ids,
                        "source_selection_numbers": [int(r["selection_number"]) for r in src_rows],
                        "authoring_guidance": AUTHORING_GUIDANCE[qtype],
                    }
                )
        if cursor != 28 or len(used_keys) != 28:
            raise RuntimeError(f"unexpected source allocation for {theme}: cursor={cursor} used={len(used_keys)}")
    if len(assignments) != 96:
        raise RuntimeError(f"expected 96 assignments, got {len(assignments)}")
    return assignments


def audit_assignments(assignments: list[dict]) -> dict:
    cells = Counter((r["theme"], r["query_type"]) for r in assignments)
    expected_cells = {(t, q): 4 for t in THEMES for q in QUERY_TYPES}
    if dict(cells) != expected_cells:
        raise RuntimeError(f"query-cell imbalance: {dict(cells)}")
    ids = [r["query_id"] for r in assignments]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate query_id")
    source_refs = sum(len(r["source_dataset_ids"]) for r in assignments)
    if source_refs != 112:
        raise RuntimeError(f"unexpected total source references: {source_refs}")
    return {
        "query_slots": len(assignments),
        "query_cells": len(cells),
        "queries_per_cell": 4,
        "source_dataset_references_total": source_refs,
        "source_records_per_theme": 28,
        "relation_comparison_source_count": 2,
        "other_query_type_source_count": 1,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        type=Path,
        default=ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_9_100",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "second_corpus_query_authoring_v1",
    )
    args = ap.parse_args()

    corpus = args.corpus.resolve()
    out = args.out.resolve()
    required_inputs = [
        corpus / "corpus_freeze.json",
        corpus / "selected_corpus_manifest.jsonl",
        corpus / "chunk_manifest.jsonl",
        corpus / "SHA256SUMS.prequery.txt",
    ]
    for p in required_inputs:
        if not p.exists():
            raise RuntimeError(f"missing frozen corpus input: {p}")

    output_paths = [
        out / "source_assignment.jsonl",
        out / "authoring_packet.jsonl",
        out / "authoring_packet_freeze.json",
        out / "SHA256SUMS.authoring.txt",
    ]
    if any(p.exists() for p in output_paths):
        raise RuntimeError("AUTHORING_OUTPUT_ALREADY_EXISTS; refusing to overwrite")

    freeze = json.loads((corpus / "corpus_freeze.json").read_text(encoding="utf-8"))
    if freeze.get("corpus_revision") != EXPECTED_CORPUS_REVISION:
        raise RuntimeError(
            f"unexpected corpus revision: {freeze.get('corpus_revision')} != {EXPECTED_CORPUS_REVISION}"
        )
    if freeze.get("prequery") is not True:
        raise RuntimeError("corpus freeze is not marked prequery")
    if int(freeze.get("theme_stratum_records_total", -1)) != 400:
        raise RuntimeError("frozen corpus does not contain 400 theme-stratum records")

    sha_checked = verify_sha_manifest(corpus / "SHA256SUMS.prequery.txt")

    selected_path = corpus / "selected_corpus_manifest.jsonl"
    chunk_path = corpus / "chunk_manifest.jsonl"
    if sha_file(selected_path) != freeze["selected_corpus_manifest_sha256"]:
        raise RuntimeError("selected corpus hash does not match corpus_freeze.json")
    if sha_file(chunk_path) != freeze["chunk_manifest_sha256"]:
        raise RuntimeError("chunk manifest hash does not match corpus_freeze.json")

    selected = read_jsonl(selected_path)
    chunks = read_jsonl(chunk_path)
    if len(selected) != 400:
        raise RuntimeError(f"selected manifest row count mismatch: {len(selected)}")
    if len(chunks) != int(freeze["chunks_total"]):
        raise RuntimeError(f"chunk manifest row count mismatch: {len(chunks)} != {freeze['chunks_total']}")

    selected_by_key = {}
    for row in selected:
        key = (row["theme"], row["dataset_id"])
        if key in selected_by_key:
            raise RuntimeError(f"duplicate selected theme/dataset identity: {key}")
        selected_by_key[key] = row

    chunks_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in chunks:
        key = (c["theme"], c["dataset_id"])
        if key not in selected_by_key:
            raise RuntimeError(f"chunk references non-selected dataset: {key}")
        chunks_by_key[key].append(c)

    assignments = build_assignments(selected)
    audit = audit_assignments(assignments)

    packet = []
    for a in assignments:
        contexts = []
        for dsid in a["source_dataset_ids"]:
            key = (a["theme"], dsid)
            row = selected_by_key[key]
            contexts.append(source_context(row, chunks_by_key[key]))
        multiplicity = sum(c["log1p_dataset_chunk_count"] for c in contexts) / len(contexts)
        packet.append(
            {
                **a,
                "query_text": None,
                "source_multiplicity_Mq_from_frozen_sources": multiplicity,
                "source_contexts": contexts,
                "authoring_rules": [
                    "Use only the frozen source metadata and representative chunks in this packet.",
                    "Do not inspect retrieval outputs while writing or revising the query text.",
                    "Keep source_dataset_ids unchanged for this slot unless the entire query-authoring packet is regenerated before any retrieval run.",
                    "Write one natural-language information need, not an answer and not a benchmark instruction.",
                    "Do not mention internal query IDs, selection numbers, chunk hashes, or benchmark mechanics in the query text.",
                    "For relation_comparison, both source datasets must be substantively required by the query.",
                ],
            }
        )

    out.mkdir(parents=True, exist_ok=True)
    assignment_path = out / "source_assignment.jsonl"
    packet_path = out / "authoring_packet.jsonl"
    write_jsonl(assignment_path, assignments)
    write_jsonl(packet_path, packet)

    freeze_obj = {
        "artifact": "SECOND_CORPUS_C2_QUERY_AUTHORING_PACKET_V1",
        "status": "FROZEN_SOURCE_ASSIGNMENT_BEFORE_RETRIEVAL",
        "seed": SEED,
        "corpus_revision": freeze["corpus_revision"],
        "corpus_freeze_sha256": sha_file(corpus / "corpus_freeze.json"),
        "prequery_sha_manifest_sha256": sha_file(corpus / "SHA256SUMS.prequery.txt"),
        "prequery_sha_entries_verified": sha_checked,
        "selected_corpus_manifest_sha256": sha_file(selected_path),
        "chunk_manifest_sha256": sha_file(chunk_path),
        "source_assignment_sha256": sha_file(assignment_path),
        "authoring_packet_sha256": sha_file(packet_path),
        "generator_script_sha256": sha_file(Path(__file__)),
        "themes": THEMES,
        "query_types": QUERY_TYPES,
        "queries_per_theme_query_type_cell": QUERIES_PER_CELL,
        "query_slots_total": 96,
        "representative_chunks_per_source_max": REPRESENTATIVE_CHUNKS_PER_SOURCE,
        "audit": audit,
        "retrieval_executed": False,
        "query_texts_frozen": False,
    }
    freeze_path = out / "authoring_packet_freeze.json"
    atomic_json(freeze_path, freeze_obj)

    checksum_targets = [
        Path(__file__),
        corpus / "corpus_freeze.json",
        corpus / "SHA256SUMS.prequery.txt",
        assignment_path,
        packet_path,
        freeze_path,
    ]
    checksum_lines = []
    for p in checksum_targets:
        try:
            display = p.resolve().relative_to(ROOT.resolve())
        except ValueError:
            display = p.resolve()
        checksum_lines.append(f"{sha_file(p)}  {display}")
    atomic_text(out / "SHA256SUMS.authoring.txt", "\n".join(checksum_lines) + "\n")

    print("C2_QUERY_AUTHORING_PACKET_FROZEN")
    print(json.dumps(freeze_obj, indent=2, sort_keys=True))
    print(f"AUTHORING_PACKET={packet_path}")


if __name__ == "__main__":
    main()
