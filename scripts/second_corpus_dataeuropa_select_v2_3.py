#!/usr/bin/env python3
"""C2 V2.3 parser-environment guard and deterministic selector driver.

Scientific protocol and the frozen candidate universe are unchanged. This driver
requires the exact frozen parser dependencies before delegating selection to the
V2.2 deterministic core.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fontTools
import pypdf
import requests

import second_corpus_dataeuropa_select_v2_2 as core

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "second_corpus_frozen_config_v2_3.json",
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

    driver_sha = core.base.sha_file(Path(__file__))
    expected_driver_sha = config["parser_environment"]["selector_driver_sha256"]
    if driver_sha != expected_driver_sha:
        raise RuntimeError(
            f"SELECTOR_DRIVER_HASH_MISMATCH expected={expected_driver_sha} actual={driver_sha}"
        )

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

    print(
        "PARSER_ENVIRONMENT_V2_3_PASS "
        f"fonttools={actual['fonttools']} pypdf={actual['pypdf']} requests={actual['requests']} "
        f"manifest_sha256={manifest_sha}",
        flush=True,
    )
    core.select(config, args.out, args.protocol, args.config)
    print("SECOND_CORPUS_V2_3_FROZEN", flush=True)


if __name__ == "__main__":
    main()
