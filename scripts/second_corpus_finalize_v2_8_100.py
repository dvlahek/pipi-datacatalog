#!/usr/bin/env python3
"""Finalize the balanced C2 target-100 corpus without mutating historical outputs.

Inputs are read-only:
  * results/second_corpus_dataeuropa_v2
  * results/second_corpus_dataeuropa_v2_recovery_v2_7_100

The first 100 ECON and ENVI dataset identities come from the preserved V2.4
checkpoint. Their historical metadata-detail snapshots are reused, while the
selected distribution payloads are rebuilt into a new staging/final directory.
A checkpoint row is accepted only when its rebuilt total chunk count matches the
count preserved in the V2.4 SELECT log.

HEAL and TRAN are copied from the completed V2.7 target-100 recovery output.
The script is resumable at dataset granularity and never deletes source outputs.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests

import second_corpus_recover_resume_v2_6 as v26

ROOT = Path(__file__).resolve().parents[1]
THEMES = ["ECON", "ENVI", "HEAL", "TRAN"]
TARGET = 100


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception as exc:
                    raise RuntimeError(f"invalid JSONL {path}:{line_no}: {exc}") from exc
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha(path: Path) -> str:
    return v26.base.sha_file(path)


def load_config(base_config: Path, amendment_path: Path) -> dict:
    cfg = json.loads(base_config.read_text(encoding="utf-8"))
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    if int(cfg["selection"]["target_per_theme"]) != 200:
        raise RuntimeError("BASE_CONFIG_TARGET_CHANGED")
    if int(amendment["target_per_theme"]) != TARGET:
        raise RuntimeError("TARGET100_AMENDMENT_MISMATCH")
    cfg = copy.deepcopy(cfg)
    cfg["selection"]["target_per_theme"] = TARGET
    cfg["target_amendment"] = amendment
    return cfg


def load_candidates(source_out: Path) -> tuple[dict[tuple[str, str], dict], dict[tuple[str, int], str]]:
    candidates = {}
    for row in read_jsonl(source_out / "candidate_universe.jsonl"):
        candidates[(row["theme"], row["dataset_id"])] = row
    by_rank = {}
    for row in read_jsonl(source_out / "candidate_order.jsonl"):
        by_rank[(row["theme"], int(row["rank"]))] = row["dataset_id"]
    return candidates, by_rank


def validate_selection_inputs(recovery_out: Path) -> tuple[list[dict], list[dict]]:
    complete_path = recovery_out / "selection_resume_complete.json"
    if not complete_path.exists():
        raise RuntimeError(f"missing completed V2.7 selection marker: {complete_path}")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    expected_cp = {"ECON": 100, "ENVI": 100, "HEAL": 0, "TRAN": 0}
    expected_ext = {"ECON": 0, "ENVI": 0, "HEAL": 100, "TRAN": 100}
    if complete.get("checkpoint_selected") != expected_cp:
        raise RuntimeError(f"unexpected checkpoint counts: {complete.get('checkpoint_selected')}")
    if complete.get("selected_after_checkpoint") != expected_ext:
        raise RuntimeError(f"unexpected extension counts: {complete.get('selected_after_checkpoint')}")

    checkpoint = read_jsonl(recovery_out / "checkpoint_selected_from_v2_4_log.jsonl")
    extension = read_jsonl(recovery_out / "selected_extension_manifest.jsonl")
    if len(checkpoint) != 200 or len(extension) != 200:
        raise RuntimeError(f"unexpected selection sizes checkpoint={len(checkpoint)} extension={len(extension)}")

    for theme in ("ECON", "ENVI"):
        rows = [r for r in checkpoint if r["theme"] == theme]
        if len(rows) != TARGET:
            raise RuntimeError(f"checkpoint count mismatch {theme}: {len(rows)}")
        if [int(r["selection_number"]) for r in rows] != list(range(1, TARGET + 1)):
            raise RuntimeError(f"checkpoint numbering mismatch {theme}")
        ranks = [int(r["candidate_rank"]) for r in rows]
        if any(a >= b for a, b in zip(ranks, ranks[1:])):
            raise RuntimeError(f"checkpoint ranks not strictly increasing {theme}")

    for theme in ("HEAL", "TRAN"):
        rows = [r for r in extension if r["theme"] == theme]
        if len(rows) != TARGET:
            raise RuntimeError(f"extension count mismatch {theme}: {len(rows)}")
        if [int(r["selection_number"]) for r in rows] != list(range(1, TARGET + 1)):
            raise RuntimeError(f"extension numbering mismatch {theme}")
        if any(len(r.get("distributions", [])) != 2 for r in rows):
            raise RuntimeError(f"extension distribution-count mismatch {theme}")

    return checkpoint, extension


def checkpoint_publisher_audit(checkpoint: list[dict], config: dict, source_out: Path) -> dict[str, Counter]:
    pubs: dict[str, Counter] = defaultdict(Counter)
    for row in checkpoint:
        path = v26.core.detail_cache_path(source_out, row["theme"], int(row["candidate_rank"]), row["dataset_id"])
        if not path.exists():
            raise RuntimeError(f"missing historical detail cache for checkpoint row: {path}")
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("transport_outcome"):
            raise RuntimeError(f"historical checkpoint detail marked unavailable: {row}")
        detail = v26.core.detail_record(wrapper, config)
        if v26.core.detail_dataset_id(detail) != row["dataset_id"]:
            raise RuntimeError(f"checkpoint detail identity mismatch: {row}")
        ds = v26.base.minimal_dataset(row["theme"], detail)
        ds["dataset_id"] = row["dataset_id"]
        pubs[row["theme"]][v26.base.publisher_key(ds)] += 1
    cap = int(config["selection"]["publisher_cap_per_theme"])
    for theme, counts in pubs.items():
        if max(counts.values(), default=0) > cap:
            raise RuntimeError(f"checkpoint publisher cap violation {theme}: {max(counts.values())} > {cap}")
    return pubs


def normalize_rebuilt_record(record: dict, logged: dict, staging_out: Path, final_out: Path, source_out: Path) -> dict:
    out = copy.deepcopy(record)
    out["selection_source"] = "recovered_v2_4_checkpoint_rebuilt_v2_8"
    out["historical_dataset_chunk_count_logged"] = int(logged["dataset_chunk_count_logged"])
    out["rebuild_chunk_count_match"] = int(out["dataset_chunk_count"]) == int(logged["dataset_chunk_count_logged"])

    for dist in out["distributions"]:
        src_raw = staging_out / dist["raw_relpath"]
        src_text = staging_out / dist["canonical_text_relpath"]
        keydir = out["selection_key_sha256"][:16]
        raw_dst = final_out / "raw" / out["theme"] / keydir / src_raw.name
        text_dst = final_out / "canonical_text" / out["theme"] / keydir / src_text.name
        raw_dst.parent.mkdir(parents=True, exist_ok=True)
        text_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_raw, raw_dst)
        shutil.copy2(src_text, text_dst)
        dist["raw_relpath"] = str(raw_dst.relative_to(final_out))
        dist["canonical_text_relpath"] = str(text_dst.relative_to(final_out))

    detail_src = source_out / out["metadata_detail_relpath"]
    detail_dst = final_out / out["metadata_detail_relpath"]
    detail_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(detail_src, detail_dst)
    out["metadata_detail_file_sha256"] = sha(detail_dst)
    return out


def validate_existing_checkpoint_record(row: dict, final_out: Path) -> None:
    if not row.get("rebuild_chunk_count_match"):
        raise RuntimeError(f"stored checkpoint record lacks exact chunk-count match: {row['theme']} {row['dataset_id']}")
    if len(row.get("distributions", [])) != 2:
        raise RuntimeError(f"stored checkpoint record has !=2 distributions: {row['theme']} {row['dataset_id']}")
    for dist in row["distributions"]:
        rp = final_out / dist["raw_relpath"]
        tp = final_out / dist["canonical_text_relpath"]
        if not rp.exists() or not tp.exists():
            raise RuntimeError(f"stored checkpoint artifact missing for {row['dataset_id']}")
        if sha(rp) != dist["payload_sha256"]:
            raise RuntimeError(f"stored raw hash mismatch: {rp}")
        if v26.base.sha_text(tp.read_text(encoding="utf-8")) != dist["text_sha256"]:
            raise RuntimeError(f"stored text hash mismatch: {tp}")


def rebuild_checkpoint(
    checkpoint: list[dict],
    config: dict,
    candidates: dict[tuple[str, str], dict],
    by_rank: dict[tuple[str, int], str],
    source_out: Path,
    final_out: Path,
) -> tuple[list[dict], list[dict]]:
    manifest_path = final_out / "checkpoint_rebuild_manifest.jsonl"
    attempts_path = final_out / "checkpoint_rebuild_attempts.jsonl"
    existing = read_jsonl(manifest_path)
    done = {(r["theme"], r["dataset_id"]): r for r in existing}
    if len(done) != len(existing):
        raise RuntimeError("duplicate rows in checkpoint_rebuild_manifest.jsonl")
    for row in existing:
        validate_existing_checkpoint_record(row, final_out)

    rebuild_cfg = copy.deepcopy(config)
    # Dataset identities are already frozen. Publisher cap is audited separately from
    # historical metadata and must not be re-applied as a new selection decision here.
    rebuild_cfg["selection"]["publisher_cap_per_theme"] = 10**9
    staging = final_out / "_checkpoint_rebuild_staging"
    staging.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": v26.base.UA})
    failures = []

    for row in checkpoint:
        key = (row["theme"], row["dataset_id"])
        if key in done:
            continue
        rank = int(row["candidate_rank"])
        if by_rank.get((row["theme"], rank)) != row["dataset_id"]:
            raise RuntimeError(f"frozen rank mismatch for checkpoint row: {row}")
        candidate = candidates.get(key)
        if candidate is None:
            raise RuntimeError(f"checkpoint dataset missing from frozen universe: {row}")
        detail_path = v26.core.detail_cache_path(source_out, row["theme"], rank, row["dataset_id"])
        if not detail_path.exists():
            raise RuntimeError(f"refusing network metadata fetch; missing historical detail cache: {detail_path}")

        ok, result = v26.evaluate(
            session,
            rebuild_cfg,
            source_out,
            staging,
            row["theme"],
            rank,
            candidate,
            defaultdict(Counter),
            int(row["selection_number"]),
        )
        attempt = {
            "theme": row["theme"],
            "selection_number": int(row["selection_number"]),
            "candidate_rank": rank,
            "dataset_id": row["dataset_id"],
            "historical_dataset_chunk_count_logged": int(row["dataset_chunk_count_logged"]),
            "rebuild_ok": bool(ok),
        }
        if not ok:
            attempt["reason"] = result.get("reason")
            attempt["detail"] = result
            append_jsonl(attempts_path, attempt)
            failures.append(attempt)
            print(f"REBUILD_FAIL {row['theme']} {row['selection_number']}/100 rank={rank} dataset={row['dataset_id']} reason={result.get('reason')}", flush=True)
            continue

        rebuilt_count = int(result["dataset_chunk_count"])
        attempt["rebuilt_dataset_chunk_count"] = rebuilt_count
        if rebuilt_count != int(row["dataset_chunk_count_logged"]):
            attempt["reason"] = "historical_chunk_count_mismatch"
            append_jsonl(attempts_path, attempt)
            failures.append(attempt)
            print(
                f"REBUILD_MISMATCH {row['theme']} {row['selection_number']}/100 rank={rank} "
                f"dataset={row['dataset_id']} logged={row['dataset_chunk_count_logged']} rebuilt={rebuilt_count}",
                flush=True,
            )
            continue

        normalized = normalize_rebuilt_record(result, row, staging, final_out, source_out)
        append_jsonl(manifest_path, normalized)
        done[key] = normalized
        attempt["reason"] = "pass"
        append_jsonl(attempts_path, attempt)
        print(
            f"REBUILD_PASS {row['theme']} {row['selection_number']}/100 rank={rank} "
            f"dataset={row['dataset_id']} chunks={rebuilt_count}",
            flush=True,
        )

    rows = read_jsonl(manifest_path)
    for row in rows:
        validate_existing_checkpoint_record(row, final_out)
    return rows, failures


def copy_extension(extension: list[dict], recovery_out: Path, final_out: Path) -> list[dict]:
    rows = []
    for src in extension:
        row = copy.deepcopy(src)
        row["selection_source"] = "v2_7_target100_extension"
        for dist in row["distributions"]:
            src_raw = recovery_out / dist["raw_relpath"]
            src_text = recovery_out / dist["canonical_text_relpath"]
            if not src_raw.exists() or not src_text.exists():
                raise RuntimeError(f"missing V2.7 selected artifact for {row['theme']} {row['dataset_id']}")
            if sha(src_raw) != dist["payload_sha256"]:
                raise RuntimeError(f"V2.7 raw hash mismatch: {src_raw}")
            if v26.base.sha_text(src_text.read_text(encoding="utf-8")) != dist["text_sha256"]:
                raise RuntimeError(f"V2.7 text hash mismatch: {src_text}")
            keydir = row["selection_key_sha256"][:16]
            raw_dst = final_out / "raw" / row["theme"] / keydir / src_raw.name
            text_dst = final_out / "canonical_text" / row["theme"] / keydir / src_text.name
            raw_dst.parent.mkdir(parents=True, exist_ok=True)
            text_dst.parent.mkdir(parents=True, exist_ok=True)
            if not raw_dst.exists():
                shutil.copy2(src_raw, raw_dst)
            if not text_dst.exists():
                shutil.copy2(src_text, text_dst)
            dist["raw_relpath"] = str(raw_dst.relative_to(final_out))
            dist["canonical_text_relpath"] = str(text_dst.relative_to(final_out))

        detail_src = recovery_out / row["metadata_detail_relpath"]
        if not detail_src.exists():
            raise RuntimeError(f"missing V2.7 metadata detail: {detail_src}")
        detail_dst = final_out / row["metadata_detail_relpath"]
        detail_dst.parent.mkdir(parents=True, exist_ok=True)
        if not detail_dst.exists():
            shutil.copy2(detail_src, detail_dst)
        row["metadata_detail_file_sha256"] = sha(detail_dst)
        rows.append(row)
    return rows


def canonicalize_selected(rows: list[dict]) -> list[dict]:
    order = {t: i for i, t in enumerate(THEMES)}
    rows = sorted(rows, key=lambda r: (order[r["theme"]], int(r["selection_number"])))
    for theme in THEMES:
        rr = [r for r in rows if r["theme"] == theme]
        if len(rr) != TARGET:
            raise RuntimeError(f"final selected count mismatch {theme}: {len(rr)}")
        if [int(r["selection_number"]) for r in rr] != list(range(1, TARGET + 1)):
            raise RuntimeError(f"final selection numbering mismatch {theme}")
        if any(len(r.get("distributions", [])) != 2 for r in rr):
            raise RuntimeError(f"final distribution count mismatch {theme}")
    return rows


def write_chunk_manifest(rows: list[dict], final_out: Path) -> dict:
    path = final_out / "chunk_manifest.jsonl"
    tmp = path.with_suffix(".jsonl.tmp")
    total = 0
    unique_chunk_hashes = set()
    payload_hashes = []
    text_hashes = []
    within_dataset_identical_payload_pairs = 0

    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            dists = row["distributions"]
            if len({d["payload_sha256"] for d in dists}) < len(dists):
                within_dataset_identical_payload_pairs += 1
            for dist in dists:
                rp = final_out / dist["raw_relpath"]
                tp = final_out / dist["canonical_text_relpath"]
                data = rp.read_bytes()
                if v26.base.sha_bytes(data) != dist["payload_sha256"]:
                    raise RuntimeError(f"final raw payload hash mismatch: {rp}")
                text, chunks = v26.base.extract_and_chunk(dist["format"], data)
                if v26.base.sha_text(text) != dist["text_sha256"]:
                    raise RuntimeError(f"re-extracted text hash mismatch: {rp}")
                canonical = tp.read_text(encoding="utf-8")
                if v26.base.sha_text(canonical) != dist["text_sha256"]:
                    raise RuntimeError(f"canonical text hash mismatch: {tp}")
                if len(chunks) != int(dist["chunk_count"]):
                    raise RuntimeError(f"re-extracted chunk count mismatch: {rp}")
                stored = dist.get("chunks", [])
                if len(stored) != len(chunks):
                    raise RuntimeError(f"stored chunk manifest length mismatch: {row['dataset_id']} {dist['distribution_id']}")
                payload_hashes.append(dist["payload_sha256"])
                text_hashes.append(dist["text_sha256"])
                for ch, old in zip(chunks, stored):
                    chash = v26.base.sha_text(ch.text)
                    if int(old["chunk_index"]) != int(ch.index) or old["chunk_text_sha256"] != chash:
                        raise RuntimeError(f"chunk replay mismatch: {row['dataset_id']} {dist['distribution_id']} {ch.index}")
                    unique_chunk_hashes.add(chash)
                    chunk_identity = v26.base.sha_text(
                        f"{row['theme']}\0{row['dataset_id']}\0{dist['distribution_id']}\0{ch.index}\0{chash}"
                    )
                    rec = {
                        "theme": row["theme"],
                        "selection_number": int(row["selection_number"]),
                        "dataset_id": row["dataset_id"],
                        "distribution_id": dist["distribution_id"],
                        "distribution_key_sha256": dist["distribution_key_sha256"],
                        "chunk_index": int(ch.index),
                        "chunk_identity_sha256": chunk_identity,
                        "chunk_text_sha256": chash,
                        "character_count": len(ch.text),
                        "char_start": ch.char_start,
                        "char_end": ch.char_end,
                        "chunk_text": ch.text,
                    }
                    f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    total += 1
    os.replace(tmp, path)
    return {
        "chunks_total": total,
        "unique_chunk_text_sha256": len(unique_chunk_hashes),
        "payload_records": len(payload_hashes),
        "unique_payload_sha256": len(set(payload_hashes)),
        "unique_text_sha256": len(set(text_hashes)),
        "datasets_with_identical_selected_distribution_payloads": within_dataset_identical_payload_pairs,
    }


def audit_final(rows: list[dict], config: dict) -> dict:
    theme_counts = Counter(r["theme"] for r in rows)
    publisher_max = {}
    publisher_top = {}
    dist_counts = Counter()
    max_chunks_per_distribution = 0
    all_ids = defaultdict(list)
    same_payload = []
    for row in rows:
        all_ids[row["dataset_id"]].append(row["theme"])
        publisher = row["publisher_key"]
        dist_counts[(row["theme"], publisher)] += 1
        dists = row["distributions"]
        if len({d["payload_sha256"] for d in dists}) < 2:
            same_payload.append({"theme": row["theme"], "dataset_id": row["dataset_id"], "candidate_rank": row["candidate_rank"]})
        for dist in dists:
            max_chunks_per_distribution = max(max_chunks_per_distribution, int(dist["chunk_count"]))
    for theme in THEMES:
        c = Counter(r["publisher_key"] for r in rows if r["theme"] == theme)
        publisher_max[theme] = max(c.values(), default=0)
        publisher_top[theme] = c.most_common(10)
    cap = int(config["selection"]["publisher_cap_per_theme"])
    if any(v > cap for v in publisher_max.values()):
        raise RuntimeError(f"final publisher cap violation: {publisher_max}")
    if max_chunks_per_distribution > int(config["distribution"]["max_chunks"]):
        raise RuntimeError(f"final max-chunks violation: {max_chunks_per_distribution}")
    cross_theme = {
        dataset_id: themes
        for dataset_id, themes in all_ids.items()
        if len(themes) > 1
    }
    return {
        "theme_stratum_counts": dict(theme_counts),
        "theme_stratum_records_total": len(rows),
        "unique_dataset_ids": len(all_ids),
        "cross_theme_duplicate_dataset_ids": cross_theme,
        "cross_theme_duplicate_dataset_id_count": len(cross_theme),
        "publisher_max_per_theme": publisher_max,
        "publisher_top10_per_theme": publisher_top,
        "max_chunks_per_distribution": max_chunks_per_distribution,
        "datasets_with_identical_selected_distribution_payloads_count": len(same_payload),
        "datasets_with_identical_selected_distribution_payloads": same_payload,
    }


def copy_frozen_candidate_artifacts(source_out: Path, final_out: Path) -> None:
    for name in ("candidate_universe.jsonl", "candidate_order.jsonl", "candidate_universe_freeze.json"):
        src = source_out / name
        dst = final_out / name
        if not src.exists():
            raise RuntimeError(f"missing frozen candidate artifact: {src}")
        if not dst.exists():
            shutil.copy2(src, dst)
        if sha(src) != sha(dst):
            raise RuntimeError(f"copied candidate artifact hash mismatch: {name}")


def freeze(
    checkpoint_rows: list[dict],
    extension: list[dict],
    config: dict,
    base_config: Path,
    amendment_path: Path,
    protocol_path: Path,
    source_out: Path,
    recovery_out: Path,
    final_out: Path,
) -> dict:
    extension_rows = copy_extension(extension, recovery_out, final_out)
    rows = canonicalize_selected(checkpoint_rows + extension_rows)
    audit = audit_final(rows, config)

    selected_path = final_out / "selected_corpus_manifest.jsonl"
    tmp = selected_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, selected_path)

    chunk_stats = write_chunk_manifest(rows, final_out)
    copy_frozen_candidate_artifacts(source_out, final_out)

    audit.update(chunk_stats)
    audit["checkpoint_rebuild_exact_chunk_count_matches"] = sum(
        1 for r in checkpoint_rows if r.get("rebuild_chunk_count_match")
    )
    audit["checkpoint_rebuild_total"] = len(checkpoint_rows)
    audit_path = final_out / "corpus_audit.json"
    write_json(audit_path, audit)

    provenance = {
        "base_config_sha256": sha(base_config),
        "target100_amendment_sha256": sha(amendment_path),
        "protocol_sha256": sha(protocol_path),
        "source_candidate_universe_sha256": sha(source_out / "candidate_universe.jsonl"),
        "source_candidate_order_sha256": sha(source_out / "candidate_order.jsonl"),
        "checkpoint_selection_sha256": sha(recovery_out / "checkpoint_selected_from_v2_4_log.jsonl"),
        "extension_selection_sha256": sha(recovery_out / "selected_extension_manifest.jsonl"),
        "selection_complete_sha256": sha(recovery_out / "selection_resume_complete.json"),
        "finalizer_script_sha256": sha(Path(__file__)),
    }
    provenance_path = final_out / "provenance_manifest.json"
    write_json(provenance_path, provenance)

    freeze_obj = {
        "protocol_id": config["protocol_id"],
        "corpus_revision": "V2.8-target100-final",
        "selection_target_per_theme": TARGET,
        "themes": THEMES,
        "theme_stratum_records_total": 400,
        "unique_dataset_ids": audit["unique_dataset_ids"],
        "distributions_total": 800,
        "chunks_total": chunk_stats["chunks_total"],
        "unique_chunk_text_sha256": chunk_stats["unique_chunk_text_sha256"],
        "candidate_universe_sha256": sha(final_out / "candidate_universe.jsonl"),
        "candidate_order_sha256": sha(final_out / "candidate_order.jsonl"),
        "selected_corpus_manifest_sha256": sha(selected_path),
        "chunk_manifest_sha256": sha(final_out / "chunk_manifest.jsonl"),
        "corpus_audit_sha256": sha(audit_path),
        "provenance_manifest_sha256": sha(provenance_path),
        "checkpoint_rebuild_policy": "reuse_historical_metadata_detail_and_require_exact_v2_4_logged_dataset_chunk_count",
        "cross_theme_overlap_policy": "retained_and_reported_as_observed_multi_theme_catalog_membership",
        "identical_distribution_payload_policy": "retained_and_reported; no post-selection content deduplication",
        "prequery": True,
    }
    freeze_path = final_out / "corpus_freeze.json"
    write_json(freeze_path, freeze_obj)

    hash_paths = [
        base_config,
        amendment_path,
        protocol_path,
        Path(__file__),
        recovery_out / "checkpoint_selected_from_v2_4_log.jsonl",
        recovery_out / "selected_extension_manifest.jsonl",
        recovery_out / "selection_resume_complete.json",
        final_out / "candidate_universe.jsonl",
        final_out / "candidate_order.jsonl",
        final_out / "candidate_universe_freeze.json",
        selected_path,
        final_out / "chunk_manifest.jsonl",
        audit_path,
        provenance_path,
        freeze_path,
    ]
    sums_path = final_out / "SHA256SUMS.prequery.txt"
    lines = []
    for path in hash_paths:
        display = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        lines.append(f"{sha(path)}  {display}")
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("FINAL_CORPUS_V2_8_100_FROZEN", flush=True)
    print(json.dumps(freeze_obj, indent=2, sort_keys=True), flush=True)
    print("FINAL_CORPUS_AUDIT", json.dumps(audit, sort_keys=True), flush=True)
    return freeze_obj


def status(final_out: Path) -> dict:
    rebuilt = read_jsonl(final_out / "checkpoint_rebuild_manifest.jsonl")
    return {
        "checkpoint_rebuilt_total": len(rebuilt),
        "checkpoint_rebuilt_by_theme": {
            t: sum(r["theme"] == t for r in rebuilt) for t in ("ECON", "ENVI")
        },
        "final_freeze_exists": (final_out / "corpus_freeze.json").exists(),
        "selected_manifest_exists": (final_out / "selected_corpus_manifest.jsonl").exists(),
        "chunk_manifest_exists": (final_out / "chunk_manifest.jsonl").exists(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-config", type=Path, default=ROOT / "config" / "second_corpus_frozen_config_v2_5.json")
    ap.add_argument("--amendment", type=Path, default=ROOT / "config" / "second_corpus_target100_amendment_v2_7.json")
    ap.add_argument("--protocol", type=Path, default=ROOT / "docs" / "second_corpus_confirmation_protocol_v2.md")
    ap.add_argument("--source-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2")
    ap.add_argument("--recovery-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2_recovery_v2_7_100")
    ap.add_argument("--final-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_8_100")
    ap.add_argument("--mode", choices=["build", "status"], default="build")
    args = ap.parse_args()

    if args.mode == "status":
        print(json.dumps(status(args.final_out), indent=2, sort_keys=True))
        return

    config = load_config(args.base_config, args.amendment)
    v26.core.verify_frozen_candidate_universe(config, args.source_out)
    checkpoint, extension = validate_selection_inputs(args.recovery_out)
    checkpoint_publisher_audit(checkpoint, config, args.source_out)
    candidates, by_rank = load_candidates(args.source_out)

    args.final_out.mkdir(parents=True, exist_ok=True)
    if (args.final_out / "corpus_freeze.json").exists():
        raise RuntimeError("FINAL_FREEZE_ALREADY_EXISTS; refusing to mutate frozen corpus")

    print(
        "FINALIZER_V2_8_100_START "
        f"source_out={args.source_out} recovery_out={args.recovery_out} final_out={args.final_out}",
        flush=True,
    )
    print("HISTORICAL_INPUTS_READ_ONLY", flush=True)

    rebuilt, failures = rebuild_checkpoint(
        checkpoint,
        config,
        candidates,
        by_rank,
        args.source_out,
        args.final_out,
    )
    counts = {t: sum(r["theme"] == t for r in rebuilt) for t in ("ECON", "ENVI")}
    print("CHECKPOINT_REBUILD_STATUS", json.dumps({"counts": counts, "failures_this_run": len(failures)}, sort_keys=True), flush=True)

    if counts != {"ECON": 100, "ENVI": 100}:
        print("CHECKPOINT_REBUILD_INCOMPLETE; final freeze not written", flush=True)
        print(json.dumps(status(args.final_out), indent=2, sort_keys=True), flush=True)
        sys.exit(2)

    freeze(
        rebuilt,
        extension,
        config,
        args.base_config,
        args.amendment,
        args.protocol,
        args.source_out,
        args.recovery_out,
        args.final_out,
    )


if __name__ == "__main__":
    main()
