#!/usr/bin/env python3
"""Deterministic C2 V2.2 selector over the already-frozen candidate universe.

This script does not re-harvest or reorder candidates. For each candidate reached in
frozen order it snapshots the modern data.europa.eu dataset-detail JSON, hashes that
snapshot, then applies the frozen V2 distribution/content eligibility rules.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import pypdf
import requests

import second_corpus_dataeuropa_bootstrap_v2 as base

ROOT = Path(__file__).resolve().parents[1]


def verify_frozen_candidate_universe(config: dict, out: Path) -> dict:
    freeze_path = out / "candidate_universe_freeze.json"
    universe_path = out / "candidate_universe.jsonl"
    order_path = out / "candidate_order.jsonl"
    for p in (freeze_path, universe_path, order_path):
        if not p.exists():
            raise RuntimeError(f"missing required frozen candidate artifact: {p}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    actual_universe = base.sha_file(universe_path)
    actual_order = base.sha_file(order_path)
    if actual_universe != freeze.get("candidate_universe_sha256"):
        raise RuntimeError("candidate universe hash mismatch against freeze")
    if actual_order != freeze.get("candidate_order_sha256"):
        raise RuntimeError("candidate order hash mismatch against freeze")
    expected_u = config["metadata_api"]["frozen_candidate_universe_sha256"]
    expected_o = config["metadata_api"]["frozen_candidate_order_sha256"]
    if actual_universe != expected_u or actual_order != expected_o:
        raise RuntimeError("candidate hashes do not match V2.2 config")
    return freeze


def load_frozen_order(config: dict, out: Path) -> dict[str, list[tuple[int, dict]]]:
    candidates: dict[tuple[str, str], dict] = {}
    with (out / "candidate_universe.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            candidates[(rec["theme"], rec["dataset_id"])] = rec

    ordered: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    with (out / "candidate_order.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            key = (row["theme"], row["dataset_id"])
            rec = candidates.get(key)
            if rec is None:
                raise RuntimeError(f"candidate order references missing candidate {key}")
            if rec["selection_key_sha256"] != row["selection_key_sha256"]:
                raise RuntimeError(f"selection-key mismatch for {key}")
            ordered[row["theme"]].append((int(row["rank"]), rec))

    expected_count = int(config["metadata_api"]["frozen_candidate_count_per_theme"])
    for theme in config["metadata_api"]["themes"]:
        rows = sorted(ordered[theme], key=lambda x: x[0])
        if len(rows) != expected_count:
            raise RuntimeError(f"unexpected frozen candidate count {theme}: {len(rows)} != {expected_count}")
        if [r for r, _ in rows] != list(range(len(rows))):
            raise RuntimeError(f"non-contiguous candidate ranks for {theme}")
        ordered[theme] = rows
    return ordered


def detail_cache_path(out: Path, theme: str, rank: int, dataset_id: str) -> Path:
    token = base.sha_text(dataset_id)[:16]
    return out / "metadata_detail" / theme / f"{rank:05d}_{token}.json"


def fetch_detail_cached(
    session: requests.Session,
    config: dict,
    out: Path,
    theme: str,
    rank: int,
    dataset_id: str,
) -> tuple[dict, Path]:
    path = detail_cache_path(out, theme, rank, dataset_id)
    if path.exists():
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if wrapper.get("dataset_id") != dataset_id or wrapper.get("theme") != theme:
            raise RuntimeError(f"detail-cache identity mismatch: {path}")
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
            last = f"HTTP {r.status_code}"
            if r.status_code == 200:
                body = r.content
                payload = r.json()
                wrapper = {
                    "theme": theme,
                    "rank": rank,
                    "dataset_id": dataset_id,
                    "retrieved_utc": base.utc_now(),
                    "request_url": url,
                    "final_url": str(r.url),
                    "status_code": r.status_code,
                    "content_type": r.headers.get("Content-Type"),
                    "response_bytes": len(body),
                    "response_sha256": base.sha_bytes(body),
                    "payload": payload,
                }
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(wrapper, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                return wrapper, path
            if r.status_code not in base.RETRY_STATUS:
                raise RuntimeError(f"detail endpoint returned non-retryable HTTP {r.status_code} for {dataset_id}")
        except (requests.RequestException, ValueError) as exc:
            last = repr(exc)
        if attempt < attempts:
            wait = min(60, 5 * (2 ** (attempt - 1)))
            print(
                f"DETAIL_RETRY theme={theme} rank={rank} attempt={attempt}/{attempts} sleep={wait}s detail={last}",
                flush=True,
            )
            time.sleep(wait)
    raise RuntimeError(f"DETAIL_FAILED theme={theme} rank={rank} dataset={dataset_id}: {last}")


def detail_record(wrapper: dict, config: dict) -> dict:
    payload = wrapper.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("detail payload is not an object")
    key = config["metadata_detail"].get("response_object")
    if key:
        payload = payload.get(key)
    if not isinstance(payload, dict):
        raise RuntimeError("detail result is not an object")
    return payload


def fetch_bounded_retry(
    session: requests.Session,
    url: str,
    max_bytes: int,
    attempts: int,
):
    last_err = None
    for attempt in range(1, attempts + 1):
        got, err = base.fetch_bounded(session, url, max_bytes)
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
            print(f"DOWNLOAD_RETRY attempt={attempt}/{attempts} sleep={wait}s url={url} detail={err}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"transient distribution download failure exhausted retries: {url} ({last_err})")


def append_events(handle, events: list[dict]) -> None:
    for event in events:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def select(config: dict, out: Path, protocol_path: Path, config_path: Path) -> None:
    candidate_freeze = verify_frozen_candidate_universe(config, out)
    ordered = load_frozen_order(config, out)

    final_freeze = out / "corpus_freeze.json"
    if final_freeze.exists():
        raise RuntimeError("corpus already frozen; refusing to overwrite")

    raw_root = out / "raw"
    text_root = out / "canonical_text"
    for p in (raw_root, text_root):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

    selected_path = out / "selected_corpus_manifest.jsonl"
    attrition_path = out / "attrition_ledger.jsonl"
    chunk_path = out / "chunk_manifest.jsonl"
    detail_manifest_path = out / "metadata_detail_manifest.jsonl"
    for p in (selected_path, attrition_path, chunk_path, detail_manifest_path):
        if p.exists():
            p.unlink()

    session = requests.Session()
    session.headers.update({"User-Agent": base.UA})
    sel_cfg = config["selection"]
    dist_cfg = config["distribution"]
    target = int(sel_cfg["target_per_theme"])
    pub_cap = int(sel_cfg["publisher_cap_per_theme"])
    max_bytes = int(dist_cfg["max_bytes"])
    max_chunks = int(dist_cfg["max_chunks"])
    download_attempts = int(dist_cfg.get("download_retry_attempts", 3))

    selected_counts = Counter()
    attempted_counts = Counter()
    publisher_counts: dict[str, Counter] = defaultdict(Counter)
    format_chunks: dict[str, list[int]] = defaultdict(list)
    theme_chunks: dict[str, list[int]] = defaultdict(list)
    dataset_chunks: list[int] = []
    used_detail_paths: dict[tuple[str, int, str], Path] = {}
    started = base.utc_now()

    with selected_path.open("w", encoding="utf-8") as sf, attrition_path.open("w", encoding="utf-8") as af, chunk_path.open("w", encoding="utf-8") as cf:
        for theme in config["metadata_api"]["themes"]:
            for rank, candidate in ordered[theme]:
                if selected_counts[theme] >= target:
                    break
                dsid = candidate["dataset_id"]
                attempted_counts[theme] += 1
                wrapper, detail_path = fetch_detail_cached(session, config, out, theme, rank, dsid)
                used_detail_paths[(theme, rank, dsid)] = detail_path
                detail = detail_record(wrapper, config)
                detail_id = base.stable_id(detail)
                if detail_id and detail_id != dsid:
                    append_events(af, [{
                        "level": "dataset", "theme": theme, "candidate_rank": rank,
                        "dataset_id": dsid, "reason": "detail_identity_mismatch", "detail_id": detail_id,
                    }])
                    continue

                ds = base.minimal_dataset(theme, detail)
                ds["dataset_id"] = dsid
                ds["selection_key_sha256"] = candidate["selection_key_sha256"]
                pub = base.publisher_key(ds)
                if publisher_counts[theme][pub] >= pub_cap:
                    append_events(af, [{
                        "level": "dataset", "theme": theme, "candidate_rank": rank,
                        "dataset_id": dsid, "reason": "publisher_cap", "publisher_key": pub,
                    }])
                    continue

                title = base.english_text(ds.get("title"))
                desc = base.english_text(ds.get("notes") or ds.get("description"))
                if not title or not desc:
                    append_events(af, [{
                        "level": "dataset", "theme": theme, "candidate_rank": rank,
                        "dataset_id": dsid, "reason": "missing_title_or_description",
                    }])
                    continue

                resources = [r for r in (ds.get("resources") or []) if isinstance(r, dict)]
                trials = []
                for resource in resources:
                    rid = base.distribution_id(resource, dsid)
                    if rid:
                        trials.append((base.distribution_key(theme, dsid, rid), rid, resource))
                trials.sort(key=lambda x: (x[0], x[1]))

                kept = []
                events: list[dict] = []
                for dkey, rid, resource in trials:
                    if len(kept) >= int(sel_cfg["retained_distributions"]):
                        break
                    urls = base.download_urls(resource)
                    if not urls:
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": "missing_download_url",
                        })
                        continue
                    ok_lic, lic_vals, lic_scope = base.open_license(resource, ds, config)
                    if not ok_lic:
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": "license_not_whitelisted",
                            "license_values": lic_vals, "license_scope": lic_scope,
                        })
                        continue

                    url = urls[0]
                    got, err = fetch_bounded_retry(session, url, max_bytes, download_attempts)
                    if got is None:
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": err, "download_url": url,
                        })
                        continue
                    data, http = got
                    fmt = base.detect_format(http["final_url"], http["content_type"], data)
                    if fmt not in set(dist_cfg["allowed_formats"]):
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": "unsupported_format",
                            "content_type": http["content_type"], "download_url": url,
                        })
                        continue
                    try:
                        text, chunks = base.extract_and_chunk(fmt, data)
                    except Exception as exc:
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": "extraction_failed",
                            "error": f"{type(exc).__name__}:{exc}",
                        })
                        continue
                    if not chunks:
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": "zero_chunks",
                        })
                        continue
                    if len(chunks) > max_chunks:
                        events.append({
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": rid, "reason": "chunk_cap_exceeded",
                            "chunk_count": len(chunks),
                        })
                        continue

                    kept.append({
                        "distribution_id": rid,
                        "distribution_key_sha256": dkey,
                        "download_url": url,
                        "final_url": http["final_url"],
                        "content_type": http["content_type"],
                        "format": fmt,
                        "license_values": lic_vals,
                        "license_scope": lic_scope,
                        "payload": data,
                        "payload_sha256": base.sha_bytes(data),
                        "byte_size": len(data),
                        "etag": http["etag"],
                        "last_modified": http["last_modified"],
                        "text": text,
                        "text_sha256": base.sha_text(text),
                        "chunks": chunks,
                    })

                append_events(af, events)
                if len(kept) < int(sel_cfg["min_eligible_distributions"]):
                    for item in kept:
                        append_events(af, [{
                            "level": "distribution", "theme": theme, "candidate_rank": rank,
                            "dataset_id": dsid, "distribution_id": item["distribution_id"],
                            "reason": "eligible_distribution_but_dataset_rejected",
                            "download_url": item["download_url"], "payload_sha256": item["payload_sha256"],
                            "byte_size": item["byte_size"], "format": item["format"],
                            "chunk_count": len(item["chunks"]),
                        }])
                    append_events(af, [{
                        "level": "dataset", "theme": theme, "candidate_rank": rank,
                        "dataset_id": dsid, "reason": "fewer_than_two_eligible_distributions",
                        "eligible_distributions": len(kept),
                    }])
                    continue

                dsdir_raw = raw_root / theme / candidate["selection_key_sha256"][:16]
                dsdir_text = text_root / theme / candidate["selection_key_sha256"][:16]
                dsdir_raw.mkdir(parents=True, exist_ok=True)
                dsdir_text.mkdir(parents=True, exist_ok=True)
                frozen_dists = []
                total_ds_chunks = 0
                for idx, item in enumerate(kept[:2]):
                    ext = {"pdf": ".pdf", "csv": ".csv", "json": ".json", "html": ".html", "txt": ".txt"}[item["format"]]
                    raw_path = dsdir_raw / f"{idx:02d}_{item['payload_sha256'][:16]}{ext}"
                    text_path = dsdir_text / f"{idx:02d}_{item['text_sha256'][:16]}.txt"
                    raw_path.write_bytes(item["payload"])
                    text_path.write_text(item["text"], encoding="utf-8")
                    chunk_hashes = []
                    for ch in item["chunks"]:
                        chash = base.sha_text(ch.text)
                        chunk_hashes.append(chash)
                        cf.write(json.dumps({
                            "theme": theme,
                            "dataset_id": dsid,
                            "distribution_id": item["distribution_id"],
                            "chunk_index": ch.index,
                            "chunk_text_sha256": chash,
                            "character_count": len(ch.text),
                            "char_start": ch.char_start,
                            "char_end": ch.char_end,
                        }, sort_keys=True) + "\n")
                    total_ds_chunks += len(item["chunks"])
                    format_chunks[item["format"]].append(len(item["chunks"]))
                    theme_chunks[theme].append(len(item["chunks"]))
                    frozen_dists.append({
                        k: v for k, v in item.items() if k not in {"payload", "text", "chunks"}
                    } | {
                        "chunk_count": len(item["chunks"]),
                        "ordered_chunk_sha256": chunk_hashes,
                        "raw_relpath": str(raw_path.relative_to(out)),
                        "canonical_text_relpath": str(text_path.relative_to(out)),
                    })

                detail_rel = str(detail_path.relative_to(out))
                rec = {
                    "theme": theme,
                    "candidate_rank": rank,
                    "selection_rank_within_theme": selected_counts[theme],
                    "selection_key_sha256": candidate["selection_key_sha256"],
                    "dataset_id": dsid,
                    "title": title,
                    "description": desc,
                    "publisher_key": pub,
                    "dataset_chunk_count": total_ds_chunks,
                    "metadata_detail_relpath": detail_rel,
                    "metadata_detail_file_sha256": base.sha_file(detail_path),
                    "metadata_detail_response_sha256": wrapper["response_sha256"],
                    "metadata_detail_retrieved_utc": wrapper["retrieved_utc"],
                    "distributions": frozen_dists,
                }
                sf.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                dataset_chunks.append(total_ds_chunks)
                publisher_counts[theme][pub] += 1
                selected_counts[theme] += 1
                print(
                    f"SELECT {theme} {selected_counts[theme]}/{target} rank={rank} dataset={dsid} chunks={total_ds_chunks}",
                    flush=True,
                )

            if selected_counts[theme] != target:
                raise RuntimeError(
                    f"INSUFFICIENT_ELIGIBLE_DATASETS theme={theme} selected={selected_counts[theme]} target={target} attempted={attempted_counts[theme]}"
                )

    with detail_manifest_path.open("w", encoding="utf-8") as mf:
        for (theme, rank, dsid), path in sorted(used_detail_paths.items(), key=lambda x: (config["metadata_api"]["themes"].index(x[0][0]), x[0][1])):
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            mf.write(json.dumps({
                "theme": theme,
                "candidate_rank": rank,
                "dataset_id": dsid,
                "detail_relpath": str(path.relative_to(out)),
                "detail_file_sha256": base.sha_file(path),
                "response_sha256": wrapper["response_sha256"],
                "retrieved_utc": wrapper["retrieved_utc"],
                "request_url": wrapper["request_url"],
                "final_url": wrapper["final_url"],
                "response_bytes": wrapper["response_bytes"],
            }, ensure_ascii=False, sort_keys=True) + "\n")

    environment = {
        "python": sys.version,
        "requests": requests.__version__,
        "pypdf": pypdf.__version__,
        "script_sha256": base.sha_file(Path(__file__)),
        "config_sha256": base.sha_file(config_path),
        "protocol_sha256": base.sha_file(protocol_path),
    }
    env_path = out / "environment_manifest.json"
    env_path.write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "protocol": config["protocol_id"],
        "transport_revision": config["transport_revision"],
        "selection_started_utc": started,
        "selection_completed_utc": base.utc_now(),
        "selected_per_theme": dict(selected_counts),
        "attempted_per_theme": dict(attempted_counts),
        "datasets_total": sum(selected_counts.values()),
        "distributions_total": sum(selected_counts.values()) * 2,
        "chunks_per_dataset": base.stats(dataset_chunks),
        "chunks_per_distribution_by_theme": {k: base.stats(v) for k, v in theme_chunks.items()},
        "chunks_per_distribution_by_format": {k: base.stats(v) for k, v in format_chunks.items()},
        "candidate_universe_sha256": base.sha_file(out / "candidate_universe.jsonl"),
        "candidate_order_sha256": base.sha_file(out / "candidate_order.jsonl"),
        "candidate_universe_freeze_sha256": base.sha_file(out / "candidate_universe_freeze.json"),
        "metadata_detail_manifest_sha256": base.sha_file(detail_manifest_path),
        "metadata_detail_records_used": len(used_detail_paths),
        "selected_corpus_manifest_sha256": base.sha_file(selected_path),
        "attrition_ledger_sha256": base.sha_file(attrition_path),
        "chunk_manifest_sha256": base.sha_file(chunk_path),
        "environment_manifest_sha256": base.sha_file(env_path),
        "script_sha256": environment["script_sha256"],
        "config_sha256": environment["config_sha256"],
        "protocol_sha256": environment["protocol_sha256"],
        "candidate_harvest_completed_utc": candidate_freeze.get("harvest_completed_utc"),
    }
    final_freeze.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sha_paths = [
        protocol_path,
        config_path,
        Path(__file__),
        out / "candidate_universe.jsonl",
        out / "candidate_order.jsonl",
        out / "candidate_universe_freeze.json",
        detail_manifest_path,
        selected_path,
        attrition_path,
        chunk_path,
        env_path,
        final_freeze,
    ]
    sha_path = out / "SHA256SUMS.prequery.txt"
    sha_path.write_text(
        "\n".join(
            f"{base.sha_file(p)}  {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}"
            for p in sha_paths
        ) + "\n",
        encoding="utf-8",
    )
    print("SECOND_CORPUS_V2_2_FROZEN", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "second_corpus_frozen_config_v2_2.json",
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
    select(config, args.out, args.protocol, args.config)


if __name__ == "__main__":
    main()
