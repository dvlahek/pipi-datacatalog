#!/usr/bin/env python3
"""Finalize C2 target-100 using only preserved historical V2.4 selections.

V2.8 successfully rebuilt all 100 ECON rows and 91/100 of the first ENVI rows.
This V2.9 finalizer preserves those 191 successful rows, marks the nine missing
first-100 ENVI rows as unmaterializable-at-finalization, and fills their slots
from the already-preserved V2.4 ENVI selections 101--125 in original selection
order. No new candidate search is performed.

A replacement row is accepted only when:
  * its historical metadata-detail snapshot exists,
  * frozen candidate identity/rank match,
  * unchanged distribution/content eligibility succeeds, and
  * rebuilt total chunk count exactly matches the V2.4 SELECT log.

All source and V2.8 outputs are read-only. V2.9 writes a new final directory.
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
import second_corpus_finalize_v2_8_100 as v28

ROOT = Path(__file__).resolve().parents[1]
TARGET = 100
THEMES = ["ECON", "ENVI", "HEAL", "TRAN"]


def copy_file_verified(src: Path, dst: Path) -> None:
    if not src.exists():
        raise RuntimeError(f"missing source artifact: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
    if v28.sha(src) != v28.sha(dst):
        raise RuntimeError(f"copy hash mismatch: {src} -> {dst}")


def copy_v28_success_rows(v28_out: Path, final_out: Path) -> list[dict]:
    rows = v28.read_jsonl(v28_out / "checkpoint_rebuild_manifest.jsonl")
    counts = {t: sum(r["theme"] == t for r in rows) for t in ("ECON", "ENVI")}
    if counts != {"ECON": 100, "ENVI": 91}:
        raise RuntimeError(f"unexpected V2.8 successful checkpoint counts: {counts}")

    out = []
    for srcrow in rows:
        row = copy.deepcopy(srcrow)
        for dist in row["distributions"]:
            copy_file_verified(v28_out / dist["raw_relpath"], final_out / dist["raw_relpath"])
            copy_file_verified(v28_out / dist["canonical_text_relpath"], final_out / dist["canonical_text_relpath"])
        detail = row.get("metadata_detail_relpath")
        if detail:
            copy_file_verified(v28_out / detail, final_out / detail)
        out.append(row)
    return out


def parse_full_v24(source_log: Path) -> list[dict]:
    # V2.6 defaults are the full preserved V2.4 trace: ECON=200, ENVI=125.
    rows = v26.parse_log(source_log)
    if sum(r["theme"] == "ECON" for r in rows) != 200:
        raise RuntimeError("full V2.4 ECON trace not recovered")
    if sum(r["theme"] == "ENVI" for r in rows) != 125:
        raise RuntimeError("full V2.4 ENVI trace not recovered")
    return rows


def latest_attempts(v28_out: Path) -> dict[tuple[str, str], dict]:
    latest = {}
    for row in v28.read_jsonl(v28_out / "checkpoint_rebuild_attempts.jsonl"):
        latest[(row["theme"], row["dataset_id"])] = row
    return latest


def validate_missing_transport_only(
    first100_checkpoint: list[dict],
    successful: list[dict],
    v28_out: Path,
) -> list[dict]:
    successful_ids = {(r["theme"], r["dataset_id"]) for r in successful}
    missing = [
        r for r in first100_checkpoint
        if r["theme"] == "ENVI" and ("ENVI", r["dataset_id"]) not in successful_ids
    ]
    missing.sort(key=lambda r: int(r["selection_number"]))
    if len(missing) != 9:
        raise RuntimeError(f"expected 9 unavailable first-100 ENVI rows, got {len(missing)}")

    latest = latest_attempts(v28_out)
    for row in missing:
        a = latest.get(("ENVI", row["dataset_id"]))
        if not a:
            raise RuntimeError(f"missing V2.8 failure evidence for {row['dataset_id']}")
        if a.get("reason") != "fewer_than_two_eligible_distributions":
            raise RuntimeError(f"non-transport failure for missing ENVI row: {a}")
        d = a.get("detail") or {}
        events = d.get("distribution_events") or []
        if not events:
            raise RuntimeError(f"missing distribution failure evidence for {row['dataset_id']}")
        bad = [
            ev for ev in events
            if not str(ev.get("reason", "")).startswith("transient_retry_exhausted:request_error:ConnectionError")
        ]
        if bad:
            raise RuntimeError(
                f"missing ENVI row has non-connection failure evidence: {row['dataset_id']} {bad}"
            )
    return missing


def load_existing_replacements(final_out: Path) -> list[dict]:
    rows = v28.read_jsonl(final_out / "historical_overflow_replacements.jsonl")
    slots = [int(r["selection_number"]) for r in rows]
    if len(slots) != len(set(slots)):
        raise RuntimeError("duplicate final ENVI slots in replacement manifest")
    sources = [int(r["historical_v2_4_selection_number"]) for r in rows]
    if len(sources) != len(set(sources)):
        raise RuntimeError("duplicate historical replacement source rows")
    for row in rows:
        v28.validate_existing_checkpoint_record(row, final_out)
    return rows


def build_replacements(
    missing: list[dict],
    overflow: list[dict],
    config: dict,
    candidates: dict[tuple[str, str], dict],
    by_rank: dict[tuple[str, int], str],
    source_out: Path,
    final_out: Path,
) -> tuple[list[dict], list[dict]]:
    manifest_path = final_out / "historical_overflow_replacements.jsonl"
    attempts_path = final_out / "historical_overflow_attempts.jsonl"
    existing = load_existing_replacements(final_out)
    filled_slots = {int(r["selection_number"]) for r in existing}
    attempted_sources = {
        int(r["historical_v2_4_selection_number"])
        for r in v28.read_jsonl(attempts_path)
        if r.get("historical_v2_4_selection_number") is not None
    }

    rebuild_cfg = copy.deepcopy(config)
    rebuild_cfg["selection"]["publisher_cap_per_theme"] = 10**9
    staging = final_out / "_historical_overflow_staging"
    staging.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": v26.base.UA})

    failures = []
    pool_index = 0
    for missing_row in missing:
        slot = int(missing_row["selection_number"])
        if slot in filled_slots:
            continue

        accepted = False
        while pool_index < len(overflow):
            source_row = overflow[pool_index]
            pool_index += 1
            source_sel = int(source_row["selection_number"])
            if source_sel in attempted_sources:
                continue

            rank = int(source_row["candidate_rank"])
            dsid = source_row["dataset_id"]
            key = ("ENVI", dsid)
            if by_rank.get(("ENVI", rank)) != dsid:
                raise RuntimeError(f"frozen rank mismatch in historical overflow: {source_row}")
            candidate = candidates.get(key)
            if candidate is None:
                raise RuntimeError(f"historical overflow dataset missing from frozen universe: {source_row}")
            detail_path = v26.core.detail_cache_path(source_out, "ENVI", rank, dsid)
            if not detail_path.exists():
                raise RuntimeError(
                    f"refusing network metadata fetch; missing historical overflow detail cache: {detail_path}"
                )

            ok, result = v26.evaluate(
                session,
                rebuild_cfg,
                source_out,
                staging,
                "ENVI",
                rank,
                candidate,
                defaultdict(Counter),
                slot,
            )
            attempt = {
                "target_missing_selection_number": slot,
                "replaced_dataset_id": missing_row["dataset_id"],
                "replaced_candidate_rank": int(missing_row["candidate_rank"]),
                "historical_v2_4_selection_number": source_sel,
                "candidate_rank": rank,
                "dataset_id": dsid,
                "historical_dataset_chunk_count_logged": int(source_row["dataset_chunk_count_logged"]),
                "rebuild_ok": bool(ok),
            }
            attempted_sources.add(source_sel)

            if not ok:
                attempt["reason"] = result.get("reason")
                attempt["detail"] = result
                v28.append_jsonl(attempts_path, attempt)
                failures.append(attempt)
                print(
                    f"OVERFLOW_SKIP source={source_sel}/125 rank={rank} dataset={dsid} "
                    f"reason={result.get('reason')}",
                    flush=True,
                )
                continue

            rebuilt_count = int(result["dataset_chunk_count"])
            if rebuilt_count != int(source_row["dataset_chunk_count_logged"]):
                attempt["reason"] = "historical_chunk_count_mismatch"
                attempt["rebuilt_dataset_chunk_count"] = rebuilt_count
                v28.append_jsonl(attempts_path, attempt)
                failures.append(attempt)
                print(
                    f"OVERFLOW_MISMATCH source={source_sel}/125 rank={rank} dataset={dsid} "
                    f"logged={source_row['dataset_chunk_count_logged']} rebuilt={rebuilt_count}",
                    flush=True,
                )
                continue

            normalized = v28.normalize_rebuilt_record(result, source_row, staging, final_out, source_out)
            normalized["selection_number"] = slot
            normalized["selection_source"] = "v2_4_historical_overflow_replacement_v2_9"
            normalized["historical_v2_4_selection_number"] = source_sel
            normalized["replacement_for_unmaterializable_dataset_id"] = missing_row["dataset_id"]
            normalized["replacement_for_unmaterializable_candidate_rank"] = int(missing_row["candidate_rank"])
            normalized["replacement_for_unmaterializable_selection_number"] = slot
            normalized["replacement_reason"] = "transport_unavailable_at_final_materialization"
            v28.append_jsonl(manifest_path, normalized)
            attempt["reason"] = "pass"
            attempt["rebuilt_dataset_chunk_count"] = rebuilt_count
            v28.append_jsonl(attempts_path, attempt)
            existing.append(normalized)
            filled_slots.add(slot)
            accepted = True
            print(
                f"OVERFLOW_REPLACEMENT_PASS slot={slot}/100 source={source_sel}/125 "
                f"rank={rank} dataset={dsid} chunks={rebuilt_count}",
                flush=True,
            )
            break

        if not accepted:
            break

    return load_existing_replacements(final_out), failures


def copy_candidate_artifacts(source_out: Path, final_out: Path) -> None:
    v28.copy_frozen_candidate_artifacts(source_out, final_out)


def freeze_v29(
    checkpoint_rows: list[dict],
    extension: list[dict],
    missing: list[dict],
    config: dict,
    base_config: Path,
    target_amendment: Path,
    availability_amendment: Path,
    protocol: Path,
    source_out: Path,
    source_log: Path,
    recovery_out: Path,
    final_out: Path,
) -> None:
    extension_rows = v28.copy_extension(extension, recovery_out, final_out)
    rows = v28.canonicalize_selected(checkpoint_rows + extension_rows)
    audit = v28.audit_final(rows, config)

    selected_path = final_out / "selected_corpus_manifest.jsonl"
    tmp = selected_path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, selected_path)

    chunk_stats = v28.write_chunk_manifest(rows, final_out)
    copy_candidate_artifacts(source_out, final_out)

    replacements = v28.read_jsonl(final_out / "historical_overflow_replacements.jsonl")
    attempts = v28.read_jsonl(final_out / "historical_overflow_attempts.jsonl")
    audit.update(chunk_stats)
    audit["checkpoint_rebuild_exact_chunk_count_matches"] = sum(
        1 for r in checkpoint_rows if r.get("rebuild_chunk_count_match")
    )
    audit["checkpoint_rebuild_total"] = len(checkpoint_rows)
    audit["unmaterializable_first100_envi_count"] = len(missing)
    audit["unmaterializable_first100_envi"] = [
        {
            "selection_number": int(r["selection_number"]),
            "candidate_rank": int(r["candidate_rank"]),
            "dataset_id": r["dataset_id"],
        }
        for r in missing
    ]
    audit["historical_overflow_replacements_count"] = len(replacements)
    audit["historical_overflow_replacements"] = [
        {
            "final_selection_number": int(r["selection_number"]),
            "historical_v2_4_selection_number": int(r["historical_v2_4_selection_number"]),
            "dataset_id": r["dataset_id"],
            "candidate_rank": int(r["candidate_rank"]),
            "replaced_dataset_id": r["replacement_for_unmaterializable_dataset_id"],
        }
        for r in replacements
    ]
    audit["historical_overflow_attempt_count"] = len(attempts)
    audit_path = final_out / "corpus_audit.json"
    v28.write_json(audit_path, audit)

    provenance = {
        "base_config_sha256": v28.sha(base_config),
        "target100_amendment_sha256": v28.sha(target_amendment),
        "materialization_availability_amendment_sha256": v28.sha(availability_amendment),
        "protocol_sha256": v28.sha(protocol),
        "source_v2_4_log_sha256": v28.sha(source_log),
        "source_candidate_universe_sha256": v28.sha(source_out / "candidate_universe.jsonl"),
        "source_candidate_order_sha256": v28.sha(source_out / "candidate_order.jsonl"),
        "checkpoint_selection_sha256": v28.sha(recovery_out / "checkpoint_selected_from_v2_4_log.jsonl"),
        "extension_selection_sha256": v28.sha(recovery_out / "selected_extension_manifest.jsonl"),
        "selection_complete_sha256": v28.sha(recovery_out / "selection_resume_complete.json"),
        "historical_overflow_replacements_sha256": v28.sha(final_out / "historical_overflow_replacements.jsonl"),
        "historical_overflow_attempts_sha256": v28.sha(final_out / "historical_overflow_attempts.jsonl"),
        "finalizer_script_sha256": v28.sha(Path(__file__)),
    }
    provenance_path = final_out / "provenance_manifest.json"
    v28.write_json(provenance_path, provenance)

    freeze_obj = {
        "protocol_id": config["protocol_id"],
        "corpus_revision": "V2.9-target100-final-materialization-recovery",
        "selection_target_per_theme": TARGET,
        "themes": THEMES,
        "theme_stratum_records_total": 400,
        "unique_dataset_ids": audit["unique_dataset_ids"],
        "distributions_total": 800,
        "chunks_total": chunk_stats["chunks_total"],
        "unique_chunk_text_sha256": chunk_stats["unique_chunk_text_sha256"],
        "candidate_universe_sha256": v28.sha(final_out / "candidate_universe.jsonl"),
        "candidate_order_sha256": v28.sha(final_out / "candidate_order.jsonl"),
        "selected_corpus_manifest_sha256": v28.sha(selected_path),
        "chunk_manifest_sha256": v28.sha(final_out / "chunk_manifest.jsonl"),
        "corpus_audit_sha256": v28.sha(audit_path),
        "provenance_manifest_sha256": v28.sha(provenance_path),
        "checkpoint_rebuild_policy": "reuse_historical_metadata_detail_and_require_exact_v2_4_logged_dataset_chunk_count",
        "unmaterializable_first100_envi_count": len(missing),
        "historical_overflow_replacement_count": len(replacements),
        "historical_overflow_policy": "fill unavailable ENVI slots from already-selected V2.4 ENVI rows 101-125 in original selection order",
        "cross_theme_overlap_policy": "retained_and_reported_as_observed_multi_theme_catalog_membership",
        "identical_distribution_payload_policy": "retained_and_reported; no post-selection content deduplication",
        "prequery": True,
    }
    freeze_path = final_out / "corpus_freeze.json"
    v28.write_json(freeze_path, freeze_obj)

    hash_paths = [
        base_config,
        target_amendment,
        availability_amendment,
        protocol,
        Path(__file__),
        source_log,
        recovery_out / "checkpoint_selected_from_v2_4_log.jsonl",
        recovery_out / "selected_extension_manifest.jsonl",
        recovery_out / "selection_resume_complete.json",
        final_out / "historical_overflow_replacements.jsonl",
        final_out / "historical_overflow_attempts.jsonl",
        final_out / "candidate_universe.jsonl",
        final_out / "candidate_order.jsonl",
        final_out / "candidate_universe_freeze.json",
        selected_path,
        final_out / "chunk_manifest.jsonl",
        audit_path,
        provenance_path,
        freeze_path,
    ]
    sums = final_out / "SHA256SUMS.prequery.txt"
    lines = []
    for p in hash_paths:
        display = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        lines.append(f"{v28.sha(p)}  {display}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("FINAL_CORPUS_V2_9_100_FROZEN", flush=True)
    print(json.dumps(freeze_obj, indent=2, sort_keys=True), flush=True)
    print("FINAL_CORPUS_AUDIT", json.dumps(audit, sort_keys=True), flush=True)


def status(final_out: Path) -> dict:
    replacements = v28.read_jsonl(final_out / "historical_overflow_replacements.jsonl")
    return {
        "historical_overflow_replacements": len(replacements),
        "replacement_final_slots": sorted(int(r["selection_number"]) for r in replacements),
        "final_freeze_exists": (final_out / "corpus_freeze.json").exists(),
        "selected_manifest_exists": (final_out / "selected_corpus_manifest.jsonl").exists(),
        "chunk_manifest_exists": (final_out / "chunk_manifest.jsonl").exists(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-config", type=Path, default=ROOT / "config" / "second_corpus_frozen_config_v2_5.json")
    ap.add_argument("--target-amendment", type=Path, default=ROOT / "config" / "second_corpus_target100_amendment_v2_7.json")
    ap.add_argument("--availability-amendment", type=Path, default=ROOT / "docs" / "second_corpus_v2_prequery_amendment_9_materialization_availability.md")
    ap.add_argument("--protocol", type=Path, default=ROOT / "docs" / "second_corpus_confirmation_protocol_v2.md")
    ap.add_argument("--source-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2")
    ap.add_argument("--source-log", type=Path, default=ROOT / "results" / "second_corpus_select_v2_4.log")
    ap.add_argument("--recovery-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2_recovery_v2_7_100")
    ap.add_argument("--v28-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_8_100")
    ap.add_argument("--final-out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2_final_v2_9_100")
    ap.add_argument("--mode", choices=["build", "status"], default="build")
    args = ap.parse_args()

    if args.mode == "status":
        print(json.dumps(status(args.final_out), indent=2, sort_keys=True))
        return

    if (args.final_out / "corpus_freeze.json").exists():
        raise RuntimeError("FINAL_FREEZE_ALREADY_EXISTS; refusing to mutate frozen V2.9 corpus")

    config = v28.load_config(args.base_config, args.target_amendment)
    v26.core.verify_frozen_candidate_universe(config, args.source_out)
    first100_checkpoint, extension = v28.validate_selection_inputs(args.recovery_out)
    successful = copy_v28_success_rows(args.v28_out, args.final_out)
    missing = validate_missing_transport_only(first100_checkpoint, successful, args.v28_out)

    full_v24 = parse_full_v24(args.source_log)
    overflow = [
        r for r in full_v24
        if r["theme"] == "ENVI" and 101 <= int(r["selection_number"]) <= 125
    ]
    if [int(r["selection_number"]) for r in overflow] != list(range(101, 126)):
        raise RuntimeError("historical ENVI overflow trace 101-125 is incomplete")

    candidates, by_rank = v28.load_candidates(args.source_out)
    args.final_out.mkdir(parents=True, exist_ok=True)

    print(
        "FINALIZER_V2_9_100_START "
        f"missing_first100_envi={len(missing)} overflow_pool={len(overflow)} final_out={args.final_out}",
        flush=True,
    )
    print("SOURCE_V2_4_V2_7_V2_8_READ_ONLY", flush=True)

    replacements, failures = build_replacements(
        missing,
        overflow,
        config,
        candidates,
        by_rank,
        args.source_out,
        args.final_out,
    )
    print(
        "HISTORICAL_OVERFLOW_STATUS",
        json.dumps({"replacements": len(replacements), "failures_this_run": len(failures)}, sort_keys=True),
        flush=True,
    )

    if len(replacements) != len(missing):
        print("HISTORICAL_OVERFLOW_INCOMPLETE; final freeze not written", flush=True)
        print(json.dumps(status(args.final_out), indent=2, sort_keys=True), flush=True)
        sys.exit(2)

    checkpoint_final = successful + replacements
    counts = {t: sum(r["theme"] == t for r in checkpoint_final) for t in ("ECON", "ENVI")}
    if counts != {"ECON": 100, "ENVI": 100}:
        raise RuntimeError(f"final checkpoint counts invalid: {counts}")

    # Final publisher-cap validation occurs over the actual 100/theme corpus in audit_final.
    freeze_v29(
        checkpoint_final,
        extension,
        missing,
        config,
        args.base_config,
        args.target_amendment,
        args.availability_amendment,
        args.protocol,
        args.source_out,
        args.source_log,
        args.recovery_out,
        args.final_out,
    )


if __name__ == "__main__":
    main()
