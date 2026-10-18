#!/usr/bin/env python3
"""C2 V2.1 transport implementation.

Scientific protocol remains SECOND_CORPUS_DATAEUROPA_V2.
V2.1 changes only the pre-result metadata harvest transport after read-only
preflight showed that the CKAN compatibility endpoint ignored/failed category
filtering while the current /search endpoint returned category-filtered counts.

Stages:
  harvest: freeze category-filtered candidate universe/order from /search.
  select:  call the frozen V2 selection logic on that universe.
  all:     harvest, then select.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import requests

import second_corpus_dataeuropa_bootstrap_v2 as base

ROOT = Path(__file__).resolve().parents[1]


def compact_candidate(theme: str, ds: dict) -> dict:
    rec = base.minimal_dataset(theme, ds)
    dsid = base.stable_id(rec)
    if not dsid:
        return {}
    rec["dataset_id"] = dsid
    rec["selection_key_sha256"] = base.select_key(theme, dsid)
    return rec


def harvest(config: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    universe_path = out / "candidate_universe.jsonl"
    order_path = out / "candidate_order.jsonl"
    freeze_path = out / "candidate_universe_freeze.json"
    if freeze_path.exists():
        print("CANDIDATE_UNIVERSE_ALREADY_FROZEN", flush=True)
        return json.loads(freeze_path.read_text(encoding="utf-8"))

    api = config["metadata_api"]
    endpoint = api["endpoint"]
    page_rows = int(api["page_rows"])
    cap = int(api["candidate_cap_per_theme"])
    started = base.utc_now()

    session = requests.Session()
    session.headers.update({"User-Agent": base.UA, "Accept": "application/json"})

    rows_by_theme: dict[str, list[dict]] = {}
    api_counts: dict[str, int | None] = {}
    metadata_presence: dict[str, dict[str, int]] = {}

    with universe_path.open("w", encoding="utf-8") as uf:
        for theme, category_code in api["themes"].items():
            collected: list[dict] = []
            seen: set[str] = set()
            page = 0
            reported_count = None
            presence = Counter()
            print(f"HARVEST {theme}", flush=True)

            while len(collected) < cap:
                limit = min(page_rows, cap - len(collected))
                params = {
                    "filters": api.get("filters", "dataset"),
                    "facets": json.dumps({api.get("facet_field", "categories"): [category_code]}, separators=(",", ":")),
                    "page": page,
                    "limit": limit,
                    "aggregation": str(bool(api.get("aggregation", False))).lower(),
                    "filterDistributions": str(bool(api.get("filter_distributions", False))).lower(),
                    "sort": [api.get("sort", "id+asc")],
                    "includes": api.get("includes", []),
                }
                payload = base.request_json(session, endpoint, params=params)
                result = payload.get("result") or {}
                batch = result.get("results") or []
                if reported_count is None:
                    try:
                        reported_count = int(result.get("count"))
                    except (TypeError, ValueError):
                        reported_count = None

                print(
                    f"SEARCH_PAGE theme={theme} page={page} rows={len(batch)} reported={reported_count}",
                    flush=True,
                )
                if not batch:
                    break

                added_this_page = 0
                for ds in batch:
                    if not isinstance(ds, dict):
                        continue
                    rec = compact_candidate(theme, ds)
                    if not rec:
                        continue
                    dsid = rec["dataset_id"]
                    if dsid in seen:
                        continue
                    seen.add(dsid)
                    collected.append(rec)
                    added_this_page += 1
                    resources = [r for r in (rec.get("resources") or []) if isinstance(r, dict)]
                    if base.english_text(rec.get("title")):
                        presence["title"] += 1
                    if base.english_text(rec.get("notes") or rec.get("description")):
                        presence["description"] += 1
                    if resources:
                        presence["distribution_metadata"] += 1
                    if any(base.download_urls(r) for r in resources):
                        presence["download_url"] += 1
                    uf.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    if len(collected) >= cap:
                        break

                if len(batch) < limit:
                    break
                if added_this_page == 0:
                    raise RuntimeError(f"SEARCH_PAGE_NO_NEW_IDS theme={theme} page={page}")
                page += 1

            if not collected:
                raise RuntimeError(f"EMPTY_CANDIDATE_UNIVERSE theme={theme}")
            rows_by_theme[theme] = collected
            api_counts[theme] = reported_count
            metadata_presence[theme] = dict(presence)
            print(
                f"HARVESTED theme={theme} candidates={len(collected)} reported={reported_count} "
                f"with_dists={presence['distribution_metadata']} with_download_url={presence['download_url']}",
                flush=True,
            )

    with order_path.open("w", encoding="utf-8") as of:
        for theme in api["themes"]:
            ordered = sorted(
                rows_by_theme[theme],
                key=lambda r: (r["selection_key_sha256"], r["dataset_id"]),
            )
            for rank, rec in enumerate(ordered):
                of.write(json.dumps({
                    "theme": theme,
                    "rank": rank,
                    "dataset_id": rec["dataset_id"],
                    "selection_key_sha256": rec["selection_key_sha256"],
                }, sort_keys=True) + "\n")

    freeze = {
        "protocol": config["protocol_id"],
        "transport_revision": config.get("transport_revision", "V2.1"),
        "harvest_started_utc": started,
        "harvest_completed_utc": base.utc_now(),
        "endpoint": endpoint,
        "query_contract": {
            "filters": api.get("filters", "dataset"),
            "facet_field": api.get("facet_field", "categories"),
            "themes": api["themes"],
            "sort": api.get("sort", "id+asc"),
            "page_rows": page_rows,
            "candidate_cap_per_theme": cap,
            "aggregation": bool(api.get("aggregation", False)),
            "filter_distributions": bool(api.get("filter_distributions", False)),
            "includes": api.get("includes", []),
        },
        "candidate_counts": {k: len(v) for k, v in rows_by_theme.items()},
        "api_reported_counts": api_counts,
        "metadata_presence": metadata_presence,
        "candidate_universe_sha256": base.sha_file(universe_path),
        "candidate_order_sha256": base.sha_file(order_path),
        "harvest_script_sha256": base.sha_file(Path(__file__)),
    }
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CANDIDATE_UNIVERSE_FROZEN", flush=True)
    print(json.dumps(freeze, indent=2, sort_keys=True), flush=True)
    return freeze


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "second_corpus_frozen_config_v2_1.json")
    ap.add_argument("--protocol", type=Path, default=ROOT / "docs" / "second_corpus_confirmation_protocol_v2.md")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2")
    ap.add_argument("--stage", choices=("harvest", "select", "all"), default="all")
    args = ap.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    if args.stage in {"harvest", "all"}:
        harvest(config, args.out)
    if args.stage in {"select", "all"}:
        base.select(config, args.out, args.protocol, args.config)


if __name__ == "__main__":
    main()
