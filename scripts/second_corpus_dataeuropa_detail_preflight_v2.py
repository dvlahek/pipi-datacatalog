#!/usr/bin/env python3
"""Read-only metadata-detail preflight for frozen C2 V2 candidate IDs.

Reads the already frozen candidate order and probes one candidate per theme against:
1) modern GET /datasets/{id}
2) CKAN compatibility package_show?id={id}

No distribution payloads are downloaded. No frozen candidate artifact is modified.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "second_corpus_dataeuropa_v2"
ORDER = OUT / "candidate_order.jsonl"
ARTIFACT = ROOT / "results" / "second_corpus_detail_preflight_v2.json"
UA = "retrieval-provenance-second-corpus/2.0 detail-preflight"


def first_ids() -> dict[str, str]:
    wanted = {"ECON", "ENVI", "HEAL", "TRAN"}
    out: dict[str, str] = {}
    with ORDER.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            theme = rec.get("theme")
            if theme in wanted and theme not in out:
                out[theme] = str(rec["dataset_id"])
            if len(out) == len(wanted):
                break
    if set(out) != wanted:
        raise RuntimeError(f"missing themes in frozen candidate order: {wanted - set(out)}")
    return out


def summarize(payload):
    if not isinstance(payload, dict):
        return {"top_type": type(payload).__name__}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    keys = sorted(result.keys()) if isinstance(result, dict) else []
    dists = []
    for key in ("distributions", "resources"):
        value = result.get(key) if isinstance(result, dict) else None
        if isinstance(value, list):
            dists = [x for x in value if isinstance(x, dict)]
            if dists:
                break
    dist_keys = sorted({k for d in dists[:10] for k in d.keys()})
    downloadish = 0
    licenseish = 0
    for d in dists:
        if any(d.get(k) for k in ("download_url", "downloadURL", "download_url_mimetype", "access_url")):
            downloadish += 1
        if any(d.get(k) for k in ("license", "licence", "license_id", "license_url", "rights")):
            licenseish += 1
    return {
        "success": payload.get("success") if isinstance(payload, dict) else None,
        "result_keys": keys,
        "distribution_count": len(dists),
        "distribution_keys_sample": dist_keys,
        "distributions_with_downloadish_field": downloadish,
        "distributions_with_licenseish_field": licenseish,
        "dataset_license_fields": {
            k: result.get(k)
            for k in ("license", "licence", "license_id", "license_url", "rights")
            if isinstance(result, dict) and result.get(k) is not None
        },
    }


def probe(session, name: str, url: str, *, params=None):
    rec = {"name": name, "url": url, "params": params or {}}
    try:
        r = session.get(url, params=params, timeout=(20, 120))
        rec.update({
            "status_code": r.status_code,
            "final_url": str(r.url),
            "content_type": r.headers.get("content-type"),
            "response_bytes": len(r.content),
        })
        try:
            rec["json_summary"] = summarize(r.json())
        except Exception as exc:
            rec["json_error"] = f"{type(exc).__name__}:{exc}"
            rec["text_prefix"] = r.text[:300]
    except Exception as exc:
        rec["request_error"] = f"{type(exc).__name__}:{exc}"
    print(json.dumps(rec, ensure_ascii=False, sort_keys=True), flush=True)
    return rec


def main() -> None:
    ids = first_ids()
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json"})
    rows = []
    for theme in ("ECON", "ENVI", "HEAL", "TRAN"):
        dsid = ids[theme]
        rows.append({"theme": theme, "dataset_id": dsid, "probes": [
            probe(
                session,
                f"{theme}_modern_dataset_detail",
                f"https://data.europa.eu/api/hub/search/datasets/{quote(dsid, safe='')}",
            ),
            probe(
                session,
                f"{theme}_ckan_package_show",
                "https://data.europa.eu/api/hub/search/ckan/package_show",
                params={"id": dsid},
            ),
        ]})
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({"frozen_candidate_order": str(ORDER), "themes": rows}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"DETAIL_PREFLIGHT_ARTIFACT={ARTIFACT}", flush=True)


if __name__ == "__main__":
    main()
