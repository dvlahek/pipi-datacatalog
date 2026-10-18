#!/usr/bin/env python3
"""C2 V2.4 transport wrapper for deterministic second-corpus selection.

V2.4 preserves the frozen candidate order and all V2.3 eligibility rules. The only
behavioral change is transport handling after bounded retries: an exhausted transient
distribution failure is recorded as attrition and selection continues to the next
frozen distribution, matching the frozen protocol's failed-distribution rule.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import fontTools
import pypdf
import requests

import second_corpus_dataeuropa_select_v2_2 as core

ROOT = Path(__file__).resolve().parents[1]


def fetch_bounded_retry_nonfatal(
    session: requests.Session,
    url: str,
    max_bytes: int,
    attempts: int,
):
    last_err = None
    for attempt in range(1, attempts + 1):
        got, err = core.base.fetch_bounded(session, url, max_bytes)
        if got is not None:
            return got, None
        last_err = err
        transient = bool(
            err
            and (
                err.startswith("request_error:")
                or err in {"http_429", "http_500", "http_502", "http_503", "http_504"}
            )
        )
        if not transient:
            return None, err
        if attempt < attempts:
            wait = min(30, 2 * (2 ** (attempt - 1)))
            print(
                f"DOWNLOAD_RETRY attempt={attempt}/{attempts} sleep={wait}s url={url} detail={err}",
                flush=True,
            )
            time.sleep(wait)

    reason = f"transient_retry_exhausted:{last_err or 'unknown'}"
    print(
        f"DOWNLOAD_SKIP retries={attempts} url={url} reason={reason}",
        flush=True,
    )
    return None, reason


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "second_corpus_frozen_config_v2_4.json",
    )
    ap.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "docs" / "second_corpus_confirmation_protocol_v2.md",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "second_corpus_dataeuropa_v2",
    )
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    expected = config["dependencies"]
    actual = {
        "fonttools": fontTools.__version__,
        "pypdf": pypdf.__version__,
        "requests": requests.__version__,
    }
    if actual != expected:
        raise RuntimeError(f"PARSER_DEPENDENCY_MISMATCH expected={expected} actual={actual}")

    dist_cfg = config["distribution"]
    if dist_cfg.get("transient_exhaustion_policy") != "record_and_skip_distribution":
        raise RuntimeError("unexpected V2.4 transient exhaustion policy")

    manifest_path = args.out / config["parser_environment"]["manifest_relpath"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_text = json.dumps(actual, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    manifest_sha = core.base.sha_file(manifest_path)
    expected_manifest_sha = config["parser_environment"]["manifest_sha256"]
    if manifest_sha != expected_manifest_sha:
        raise RuntimeError(
            f"PARSER_ENVIRONMENT_MANIFEST_HASH_MISMATCH expected={expected_manifest_sha} actual={manifest_sha}"
        )

    # V2.4 changes transport failure handling only; deterministic selection remains in core.
    core.fetch_bounded_retry = fetch_bounded_retry_nonfatal

    print(
        "TRANSPORT_ENVIRONMENT_V2_4_PASS "
        f"fonttools={actual['fonttools']} pypdf={actual['pypdf']} requests={actual['requests']} "
        f"retry_attempts={dist_cfg['download_retry_attempts']} "
        f"policy={dist_cfg['transient_exhaustion_policy']} "
        f"manifest_sha256={manifest_sha}",
        flush=True,
    )

    core.select(config, args.out, args.protocol, args.config)

    final_freeze = args.out / "corpus_freeze.json"
    summary = json.loads(final_freeze.read_text(encoding="utf-8"))
    driver_path = Path(__file__).resolve()
    core_path = Path(core.__file__).resolve()
    driver_sha = core.base.sha_file(driver_path)
    core_sha = core.base.sha_file(core_path)
    summary["parser_environment_manifest_sha256"] = manifest_sha
    summary["selector_driver_sha256"] = driver_sha
    summary["selector_core_sha256"] = core_sha
    summary["transient_exhaustion_policy"] = dist_cfg["transient_exhaustion_policy"]
    final_freeze.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sha_paths = [
        args.protocol,
        args.config,
        driver_path,
        core_path,
        args.out / "candidate_universe.jsonl",
        args.out / "candidate_order.jsonl",
        args.out / "candidate_universe_freeze.json",
        manifest_path,
        args.out / "metadata_detail_manifest.jsonl",
        args.out / "selected_corpus_manifest.jsonl",
        args.out / "attrition_ledger.jsonl",
        args.out / "chunk_manifest.jsonl",
        args.out / "environment_manifest.json",
        final_freeze,
    ]
    sha_path = args.out / "SHA256SUMS.prequery.txt"
    sha_path.write_text(
        "\n".join(
            f"{core.base.sha_file(path)}  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}"
            for path in sha_paths
        ) + "\n",
        encoding="utf-8",
    )

    print("SECOND_CORPUS_V2_4_FROZEN", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
