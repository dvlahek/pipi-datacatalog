#!/usr/bin/env python3
"""Read-only preflight for data.europa.eu search APIs used by C2 V2.

This script does not harvest, download, select, freeze, index, retrieve, or generate.
It only probes public search endpoints so transport/schema problems are separated from
scientific corpus selection.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "second_corpus_api_preflight_v2.json"
UA = "retrieval-provenance-second-corpus/2.0 api-preflight"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def summarize_payload(payload):
    out = {"top_type": type(payload).__name__}
    if isinstance(payload, dict):
        out["top_keys"] = sorted(payload.keys())
        if "success" in payload:
            out["success"] = payload.get("success")
        result = payload.get("result")
        if isinstance(result, dict):
            out["result_keys"] = sorted(result.keys())
            for key in ("count", "total", "total_count"):
                if key in result:
                    out[f"result_{key}"] = result.get(key)
            for key in ("results", "items", "datasets"):
                if isinstance(result.get(key), list):
                    out[f"result_{key}_len"] = len(result[key])
                    if result[key] and isinstance(result[key][0], dict):
                        out[f"result_{key}_first_keys"] = sorted(result[key][0].keys())
        for key in ("count", "total", "total_count"):
            if key in payload:
                out[key] = payload.get(key)
        for key in ("results", "items", "datasets"):
            if isinstance(payload.get(key), list):
                out[f"{key}_len"] = len(payload[key])
                if payload[key] and isinstance(payload[key][0], dict):
                    out[f"{key}_first_keys"] = sorted(payload[key][0].keys())
    return out


def probe(session, name, url, params):
    row = {"name": name, "url": url, "params": params, "started_utc": now()}
    try:
        r = session.get(url, params=params, timeout=(20, 90))
        row["status_code"] = r.status_code
        row["final_url"] = str(r.url)
        row["content_type"] = r.headers.get("content-type")
        row["response_bytes"] = len(r.content)
        try:
            payload = r.json()
            row["json_summary"] = summarize_payload(payload)
        except ValueError:
            row["text_prefix"] = r.text[:500]
    except Exception as exc:
        row["error"] = repr(exc)
    row["completed_utc"] = now()
    print(json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)
    return row


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})

    ckan = "https://data.europa.eu/api/hub/search/ckan/package_search"
    modern = "https://data.europa.eu/api/hub/search/search"

    tests = [
        ("ckan_unfiltered", ckan, {"rows": 1, "start": 0, "facet": "false"}),
        ("ckan_econ_groups_slug", ckan, {"fq": "groups:economy-and-finance", "rows": 1, "start": 0, "facet": "false"}),
        ("ckan_econ_groups_quoted", ckan, {"fq": 'groups:"economy-and-finance"', "rows": 1, "start": 0, "facet": "false"}),
        ("ckan_econ_category_code", ckan, {"fq": "categories:ECON", "rows": 1, "start": 0, "facet": "false"}),
        ("search_unfiltered_dataset", modern, {"filters": "dataset", "page": 0, "limit": 1, "aggregation": "false"}),
        ("search_econ_categories", modern, {"filters": "dataset", "facets": json.dumps({"categories": ["ECON"]}, separators=(",", ":")), "page": 0, "limit": 1, "aggregation": "false"}),
    ]

    rows = [probe(s, *t) for t in tests]
    artifact = {
        "artifact": "SECOND_CORPUS_DATAEUROPA_API_PREFLIGHT_V2",
        "created_utc": now(),
        "read_only": True,
        "tests": rows,
    }
    OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PREFLIGHT_ARTIFACT={OUT}", flush=True)


if __name__ == "__main__":
    main()
