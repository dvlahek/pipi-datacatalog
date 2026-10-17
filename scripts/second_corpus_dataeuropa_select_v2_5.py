#!/usr/bin/env python3
"""C2 V2.5 transport wrapper for deterministic second-corpus selection.

V2.5 preserves the frozen candidate universe/order and all scientific eligibility
rules. It adds explicit nonfatal handling for unavailable dataset-detail responses:
non-retryable 4xx responses (except 429), or exhausted transient detail retries, are
recorded as dataset-level attrition and selection continues in frozen candidate order.
Distribution retry exhaustion remains nonfatal as introduced in V2.4.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import quote

import fontTools
import pypdf
import requests

import second_corpus_dataeuropa_select_v2_2 as core

ROOT = Path(__file__).resolve().parents[1]
_DETAIL_OUTCOMES: dict[tuple[str, int, str], str] = {}
_ORIGINAL_DETAIL_RECORD = core.detail_record
_ORIGINAL_APPEND_EVENTS = core.append_events


def _write_detail_wrapper(path: Path, wrapper: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(wrapper, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fetch_detail_cached_nonfatal(
    session: requests.Session,
    config: dict,
    out: Path,
    theme: str,
    rank: int,
    dataset_id: str,
):
    path = core.detail_cache_path(out, theme, rank, dataset_id)
    key = (theme, rank, dataset_id)
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("dataset_id") != dataset_id or wrapper.get("theme") != theme:
            raise RuntimeError(f"detail-cache identity mismatch: {path}")
        outcome = wrapper.get("transport_outcome")
        if outcome:
            _DETAIL_OUTCOMES[key] = str(outcome)
        return wrapper, path

    detail_cfg = config["metadata_detail"]
    url = detail_cfg["endpoint_template"].format(dataset_id=quote(dataset_id, safe=""))
    attempts = int(detail_cfg["retry_attempts"])
    timeout = (
        float(detail_cfg["timeout_connect_seconds"]),
        float(detail_cfg["timeout_read_seconds"]),
    )
    last = None

    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, timeout=timeout, headers={"Accept": "application/json"})
            body = r.content
            last = f"HTTP {r.status_code}"
            if r.status_code == 200:
                payload = r.json()
                wrapper = {
                    "theme": theme,
                    "rank": rank,
                    "dataset_id": dataset_id,
                    "retrieved_utc": core.base.utc_now(),
                    "request_url": url,
                    "final_url": str(r.url),
                    "status_code": r.status_code,
                    "content_type": r.headers.get("Content-Type"),
                    "response_bytes": len(body),
                    "response_sha256": core.base.sha_bytes(body),
                    "payload": payload,
                }
                _write_detail_wrapper(path, wrapper)
                return wrapper, path

            retryable = r.status_code in core.base.RETRY_STATUS
            if not retryable:
                outcome = f"http_{r.status_code}"
                wrapper = {
                    "theme": theme,
                    "rank": rank,
                    "dataset_id": dataset_id,
                    "retrieved_utc": core.base.utc_now(),
                    "request_url": url,
                    "final_url": str(r.url),
                    "status_code": r.status_code,
                    "content_type": r.headers.get("Content-Type"),
                    "response_bytes": len(body),
                    "response_sha256": core.base.sha_bytes(body),
                    "payload": None,
                    "transport_outcome": outcome,
                }
                _write_detail_wrapper(path, wrapper)
                _DETAIL_OUTCOMES[key] = outcome
                print(
                    f"DETAIL_SKIP theme={theme} rank={rank} dataset={dataset_id} reason={outcome}",
                    flush=True,
                )
                return wrapper, path
        except (requests.RequestException, ValueError) as exc:
            last = f"{type(exc).__name__}:{exc}"

        if attempt < attempts:
            wait = min(60, 5 * (2 ** (attempt - 1)))
            print(
                f"DETAIL_RETRY theme={theme} rank={rank} attempt={attempt}/{attempts} "
                f"sleep={wait}s detail={last}",
                flush=True,
            )
            time.sleep(wait)

    outcome = f"transient_retry_exhausted:{last or 'unknown'}"
    wrapper = {
        "theme": theme,
        "rank": rank,
        "dataset_id": dataset_id,
        "retrieved_utc": core.base.utc_now(),
        "request_url": url,
        "final_url": url,
        "status_code": None,
        "content_type": None,
        "response_bytes": 0,
        "response_sha256": core.base.sha_bytes(b""),
        "payload": None,
        "transport_outcome": outcome,
    }
    _write_detail_wrapper(path, wrapper)
    _DETAIL_OUTCOMES[key] = outcome
    print(
        f"DETAIL_SKIP theme={theme} rank={rank} dataset={dataset_id} reason={outcome}",
        flush=True,
    )
    return wrapper, path


def detail_record_nonfatal(wrapper: dict, config: dict) -> dict:
    if wrapper.get("transport_outcome"):
        return {"id": "__DETAIL_UNAVAILABLE__"}
    return _ORIGINAL_DETAIL_RECORD(wrapper, config)


def append_events_with_detail_reason(handle, events: list[dict]) -> None:
    rewritten: list[dict] = []
    for event in events:
        e = dict(event)
        if (
            e.get("reason") == "detail_identity_mismatch"
            and e.get("detail_id") == "__DETAIL_UNAVAILABLE__"
        ):
            key = (str(e.get("theme")), int(e.get("candidate_rank")), str(e.get("dataset_id")))
            outcome = _DETAIL_OUTCOMES.get(key, "unknown")
            e.pop("detail_id", None)
            e["reason"] = "detail_unavailable"
            e["detail_transport_outcome"] = outcome
        rewritten.append(e)
    _ORIGINAL_APPEND_EVENTS(handle, rewritten)


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
        default=ROOT / "config" / "second_corpus_frozen_config_v2_5.json",
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
    detail_cfg = config["metadata_detail"]
    if dist_cfg.get("transient_exhaustion_policy") != "record_and_skip_distribution":
        raise RuntimeError("unexpected distribution transient exhaustion policy")
    if detail_cfg.get("unavailable_policy") != "record_and_skip_dataset":
        raise RuntimeError("unexpected metadata-detail unavailable policy")

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

    core.fetch_bounded_retry = fetch_bounded_retry_nonfatal
    core.fetch_detail_cached = fetch_detail_cached_nonfatal
    core.detail_record = detail_record_nonfatal
    core.append_events = append_events_with_detail_reason

    print(
        "TRANSPORT_ENVIRONMENT_V2_5_PASS "
        f"fonttools={actual['fonttools']} pypdf={actual['pypdf']} requests={actual['requests']} "
        f"distribution_policy={dist_cfg['transient_exhaustion_policy']} "
        f"detail_policy={detail_cfg['unavailable_policy']} "
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
    summary["metadata_detail_unavailable_policy"] = detail_cfg["unavailable_policy"]
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

    print("SECOND_CORPUS_V2_5_FROZEN", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
