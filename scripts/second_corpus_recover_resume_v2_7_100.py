#!/usr/bin/env python3
"""C2 target-100 recovery/resume selector.

This wrapper preserves the original V2.4/V2.5 output directory as read-only.
It validates the complete preserved V2.4 selection trace, freezes the first
100 selected datasets per available theme as the balanced checkpoint, and
continues only missing themes into a new recovery directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import second_corpus_recover_resume_v2_6 as v26

ROOT = Path(__file__).resolve().parents[1]
TARGET = 100
FULL_V24_EXPECTED = {
    "ECON": (200, 8256),
    "ENVI": (125, 1937),
    "HEAL": (0, -1),
    "TRAN": (0, -1),
}

_ORIGINAL_PARSE_LOG = v26.parse_log
_ORIGINAL_EVALUATE = v26.evaluate


def parse_log_target100(path: Path):
    """Validate the full V2.4 trace, then retain only first 100/theme."""
    old_expected = v26.EXPECTED
    try:
        v26.EXPECTED = FULL_V24_EXPECTED
        full_rows = _ORIGINAL_PARSE_LOG(path)
    finally:
        v26.EXPECTED = old_expected

    rows = [r for r in full_rows if int(r["selection_number"]) <= TARGET]
    counts = {
        theme: sum(r["theme"] == theme for r in rows)
        for theme in ("ECON", "ENVI", "HEAL", "TRAN")
    }
    expected_counts = {"ECON": 100, "ENVI": 100, "HEAL": 0, "TRAN": 0}
    if counts != expected_counts:
        raise RuntimeError(
            f"target-100 checkpoint mismatch expected={expected_counts} actual={counts}"
        )
    return rows


def evaluate_new_output_only(
    session,
    config,
    source_out,
    recovery_out,
    theme,
    rank,
    candidate,
    pubcounts,
    selnum,
):
    """Evaluate new candidates while writing every new cache/artifact to recovery_out.

    The V2.6 evaluator uses its source_out argument only for metadata-detail cache
    storage/provenance. Passing recovery_out in both output positions guarantees
    that the historical source_out remains read-only during HEAL/TRAN continuation.
    """
    return _ORIGINAL_EVALUATE(
        session,
        config,
        recovery_out,
        recovery_out,
        theme,
        rank,
        candidate,
        pubcounts,
        selnum,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-config",
        type=Path,
        default=ROOT / "config" / "second_corpus_frozen_config_v2_5.json",
    )
    ap.add_argument(
        "--amendment",
        type=Path,
        default=ROOT / "config" / "second_corpus_target100_amendment_v2_7.json",
    )
    ap.add_argument(
        "--source-out",
        type=Path,
        default=ROOT / "results" / "second_corpus_dataeuropa_v2",
    )
    ap.add_argument(
        "--source-log",
        type=Path,
        default=ROOT / "results" / "second_corpus_select_v2_4.log",
    )
    ap.add_argument(
        "--recovery-out",
        type=Path,
        default=ROOT / "results" / "second_corpus_dataeuropa_v2_recovery_v2_7_100",
    )
    ap.add_argument(
        "--mode",
        choices=["checkpoint", "status", "resume"],
        default="resume",
    )
    args = ap.parse_args()

    config = json.loads(args.base_config.read_text(encoding="utf-8"))
    amendment = json.loads(args.amendment.read_text(encoding="utf-8"))
    if int(config["selection"]["target_per_theme"]) != 200:
        raise RuntimeError("BASE_CONFIG_TARGET_CHANGED")
    if int(amendment["target_per_theme"]) != TARGET:
        raise RuntimeError("AMENDMENT_TARGET_MISMATCH")
    config["selection"]["target_per_theme"] = TARGET
    config["target_amendment"] = amendment

    v26.core.verify_frozen_candidate_universe(config, args.source_out)

    # Patch only the two recovery-specific behaviors. Historical source data remain read-only.
    v26.parse_log = parse_log_target100
    v26.evaluate = evaluate_new_output_only

    rows, ordered = v26.ensure_checkpoint(
        args.source_log,
        args.source_out,
        args.recovery_out,
        config,
    )

    themes = config["metadata_api"]["themes"]
    print(
        "RECOVERY_V2_7_100_SOURCE_READ_ONLY "
        f"source_out={args.source_out} recovery_out={args.recovery_out} target={TARGET}",
        flush=True,
    )

    if args.mode == "checkpoint":
        print("RECOVERY_V2_7_100_CHECKPOINT_PASS", flush=True)
        print(json.dumps(v26.stat(args.recovery_out, rows, themes), indent=2, sort_keys=True))
        return

    if args.mode == "status":
        print(json.dumps(v26.stat(args.recovery_out, rows, themes), indent=2, sort_keys=True))
        return

    v26.resume(config, args.source_out, args.recovery_out, rows, ordered)


if __name__ == "__main__":
    main()
