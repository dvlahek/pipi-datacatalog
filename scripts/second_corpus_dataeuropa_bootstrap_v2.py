#!/usr/bin/env python3
"""Build the frozen data.europa.eu C2 corpus under protocol V2.

Stages:
  harvest: freeze the CKAN candidate universe/order before payload download.
  select:  deterministically download/select 200 datasets per theme.
  all:     harvest if needed, then select.

No retrieval evaluation, qrels, LLM generation, or result-dependent tuning occurs here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests
import pypdf
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SEED = "SECOND_CORPUS_DATAEUROPA_V2"
UA = "retrieval-provenance-second-corpus/2.0 frozen-confirmation"
RETRY_STATUS = {429, 500, 502, 503, 504}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_text(text: str) -> str:
    return sha_bytes(text.encode("utf-8"))


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_strings(value) -> list[str]:
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, str):
        if value.strip():
            out.append(value.strip())
        return out
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        for item in value:
            out.extend(as_strings(item))
        return out
    if isinstance(value, dict):
        for key in ("resource", "uri", "url", "id", "label", "name", "title", "en"):
            if key in value:
                out.extend(as_strings(value.get(key)))
        if not out:
            for item in value.values():
                out.extend(as_strings(item))
    return out


def english_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("en", "EN", "eng"):
            if value.get(key):
                vals = as_strings(value[key])
                return vals[0] if vals else ""
        vals = as_strings(value)
        return vals[0] if vals else ""
    vals = as_strings(value)
    return vals[0] if vals else ""


def stable_id(record: dict) -> str:
    for key in ("uri", "resource", "id", "name"):
        vals = as_strings(record.get(key))
        if vals:
            return vals[0]
    return ""


def normalized_key(value) -> str:
    vals = as_strings(value)
    raw = vals[0] if vals else ""
    raw = raw.strip().lower()
    raw = re.sub(r"\s+", " ", raw)
    return raw


def publisher_key(ds: dict) -> str:
    for key in ("publisher", "organization", "creator"):
        k = normalized_key(ds.get(key))
        if k:
            return k
    for key in ("catalog", "catalogue"):
        k = normalized_key(ds.get(key))
        if k:
            return f"catalog:{k}"
    return f"dataset:{stable_id(ds)}"


def select_key(theme: str, dataset_id: str) -> str:
    return sha_text(f"{SEED}|{theme}|{dataset_id}")


def distribution_key(theme: str, dataset_id: str, distribution_id: str) -> str:
    return sha_text(f"{SEED}|{theme}|{dataset_id}|{distribution_id}")


def minimal_resource(r: dict) -> dict:
    keys = (
        "id", "uri", "resource", "name", "download_url", "downloadURL",
        "format", "mimetype", "media_type", "size", "byte_size",
        "license", "licence", "license_id", "license_url", "rights"
    )
    return {k: r.get(k) for k in keys if k in r}


def minimal_dataset(theme: str, ds: dict) -> dict:
    keys = (
        "id", "uri", "resource", "name", "title", "notes", "description",
        "publisher", "organization", "creator", "catalog", "catalogue",
        "country", "groups", "license", "licence", "license_id", "license_url"
    )
    out = {"theme": theme}
    out.update({k: ds.get(k) for k in keys if k in ds})
    resources = ds.get("resources") or ds.get("distributions") or []
    out["resources"] = [minimal_resource(r) for r in resources if isinstance(r, dict)]
    return out


def request_json(session: requests.Session, url: str, *, params: dict, attempts: int = 6) -> dict:
    last = None
    for attempt in range(1, attempts + 1):
        try:
            r = session.get(url, params=params, timeout=(20, 120))
            last = f"HTTP {r.status_code}"
            if r.status_code == 200:
                return r.json()
            if r.status_code not in RETRY_STATUS:
                r.raise_for_status()
        except (requests.RequestException, ValueError) as exc:
            last = repr(exc)
        if attempt < attempts:
            wait = min(60, 5 * (2 ** (attempt - 1)))
            print(f"API_RETRY attempt={attempt}/{attempts} sleep={wait}s detail={last}", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"API_FAILED after {attempts} attempts: {last}")


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
    started = utc_now()
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json"})

    rows_by_theme: dict[str, list[dict]] = {}
    api_counts: dict[str, int | None] = {}
    with universe_path.open("w", encoding="utf-8") as uf:
        for theme, theme_query in api["themes"].items():
            collected: list[dict] = []
            start = 0
            reported_count = None
            print(f"HARVEST {theme}", flush=True)
            while start < cap:
                rows = min(page_rows, cap - start)
                params = {
                    "fq": api["fq_template"].format(theme_query=theme_query),
                    "sort": api["sort"],
                    "rows": rows,
                    "start": start,
                    "facet": "false",
                }
                payload = request_json(session, endpoint, params=params)
                if not payload.get("success", True):
                    raise RuntimeError(f"CKAN package_search returned success=false for {theme}")
                result = payload.get("result") or {}
                batch = result.get("results") or []
                if reported_count is None:
                    try:
                        reported_count = int(result.get("count"))
                    except (TypeError, ValueError):
                        reported_count = None
                print(f"CKAN_PAGE theme={theme} start={start} rows={len(batch)}", flush=True)
                if not batch:
                    break
                for ds in batch:
                    if not isinstance(ds, dict):
                        continue
                    rec = minimal_dataset(theme, ds)
                    dsid = stable_id(rec)
                    if not dsid:
                        continue
                    rec["dataset_id"] = dsid
                    rec["selection_key_sha256"] = select_key(theme, dsid)
                    collected.append(rec)
                    uf.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                start += len(batch)
                if len(batch) < rows:
                    break
            if not collected:
                raise RuntimeError(f"EMPTY_CANDIDATE_UNIVERSE theme={theme}")
            rows_by_theme[theme] = collected
            api_counts[theme] = reported_count
            print(f"HARVESTED theme={theme} candidates={len(collected)} reported={reported_count}", flush=True)

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
        "harvest_started_utc": started,
        "harvest_completed_utc": utc_now(),
        "endpoint": endpoint,
        "query_contract": {
            "fq_template": api["fq_template"],
            "sort": api["sort"],
            "page_rows": page_rows,
            "candidate_cap_per_theme": cap,
        },
        "candidate_counts": {k: len(v) for k, v in rows_by_theme.items()},
        "api_reported_counts": api_counts,
        "candidate_universe_sha256": sha_file(universe_path),
        "candidate_order_sha256": sha_file(order_path),
    }
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CANDIDATE_UNIVERSE_FROZEN", flush=True)
    print(json.dumps(freeze, indent=2, sort_keys=True), flush=True)
    return freeze


def flatten_license(value) -> list[str]:
    vals = []
    for s in as_strings(value):
        s = s.strip()
        if s and s not in vals:
            vals.append(s)
    return vals


def license_values(record: dict) -> list[str]:
    vals: list[str] = []
    for key in ("license", "licence", "license_id", "license_url"):
        for s in flatten_license(record.get(key)):
            if s not in vals:
                vals.append(s)
    return vals


def normalize_label(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9.+-]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def open_license(resource: dict, dataset: dict, config: dict) -> tuple[bool, list[str], str | None]:
    vals = license_values(resource)
    scope = "distribution" if vals else None
    if not vals and config["licenses"].get("inherit_dataset_license_if_distribution_license_missing"):
        vals = license_values(dataset)
        scope = "dataset" if vals else None
    if not vals:
        return False, [], None
    prefixes = [x.lower().rstrip("/") for x in config["licenses"]["accepted_exact_or_prefixes"]]
    labels = {normalize_label(x) for x in config["licenses"]["accepted_normalized_labels"]}
    for value in vals:
        lv = value.lower().rstrip("/")
        if any(lv == p or lv.startswith(p + "/") for p in prefixes):
            return True, vals, scope
        if normalize_label(value) in labels:
            return True, vals, scope
    return False, vals, scope


def download_urls(resource: dict) -> list[str]:
    vals = []
    for key in ("download_url", "downloadURL"):
        vals.extend(as_strings(resource.get(key)))
    clean = sorted({u.strip() for u in vals if u.strip().startswith(("http://", "https://"))})
    return clean


def distribution_id(resource: dict, dataset_id: str) -> str:
    rid = stable_id(resource)
    if rid:
        return rid
    urls = download_urls(resource)
    if urls:
        return f"sha256:{sha_text(dataset_id + '|' + urls[0])}"
    return ""


def fetch_bounded(session: requests.Session, url: str, max_bytes: int):
    try:
        with session.get(url, stream=True, timeout=(20, 120), allow_redirects=True) as r:
            if r.status_code != 200:
                return None, f"http_{r.status_code}"
            clen = r.headers.get("Content-Length")
            if clen:
                try:
                    if int(clen) > max_bytes:
                        return None, "declared_oversize"
                except ValueError:
                    pass
            buf = bytearray()
            for block in r.iter_content(256 * 1024):
                if not block:
                    continue
                buf.extend(block)
                if len(buf) > max_bytes:
                    return None, "stream_oversize"
            return (bytes(buf), {
                "requested_url": url,
                "final_url": str(r.url),
                "content_type": (r.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower(),
                "etag": r.headers.get("ETag"),
                "last_modified": r.headers.get("Last-Modified"),
            }), None
    except requests.RequestException as exc:
        return None, f"request_error:{type(exc).__name__}"


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.ignored += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self.ignored:
            self.ignored -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored == 0:
            self.parts.append(data)


def decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass
class Chunk:
    index: int
    text: str
    char_start: int
    char_end: int


def generic_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[Chunk]:
    chunks: list[Chunk] = []
    start = 0
    index = 0
    length = len(text)
    while start < length:
        hard_end = min(start + chunk_size, length)
        end = hard_end
        if hard_end < length:
            window = text[start:hard_end]
            boundary = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "))
            if boundary >= chunk_size // 2:
                end = start + boundary + (2 if window[boundary:boundary + 2] in {"\n\n", ". "} else 1)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(Chunk(index, chunk, start, end))
            index += 1
        if end >= length:
            break
        nxt = end - overlap
        start = end if nxt <= start else nxt
    return chunks


def detect_format(url: str, content_type: str, data: bytes) -> str | None:
    suffix = Path(urlparse(url).path).suffix.lower()
    ct = content_type.lower()
    if ct == "text/csv" or suffix == ".csv":
        return "csv"
    if ct == "application/json" or ct.endswith("+json") or suffix == ".json":
        return "json"
    if ct == "application/pdf" or suffix == ".pdf" or data.startswith(b"%PDF"):
        return "pdf"
    if ct in {"text/html", "application/xhtml+xml"} or suffix in {".html", ".htm"}:
        return "html"
    if ct.startswith("text/") or suffix in {".txt", ".text"}:
        return "txt"
    return None


def extract_and_chunk(fmt: str, data: bytes) -> tuple[str, list[Chunk]]:
    if fmt == "csv":
        reader = csv.reader(io.StringIO(decode_text(data)))
        rows = list(reader)
        if not rows:
            raise ValueError("empty_csv")
        header = rows[0]
        row_texts = []
        for row_number, row in enumerate(rows[1:], start=1):
            if not any(str(v).strip() for v in row):
                continue
            pairs = []
            for i, value in enumerate(row):
                key = header[i] if i < len(header) and header[i] else f"column_{i+1}"
                pairs.append(f"{key}: {value}")
            row_texts.append(normalize_text(f"Row {row_number}. " + " | ".join(pairs)))
        row_texts = [x for x in row_texts if x]
        if not row_texts:
            raise ValueError("no_csv_rows")
        text = "\n".join(row_texts)
        chunks = []
        cursor = 0
        for i, row in enumerate(row_texts):
            chunks.append(Chunk(i, row, cursor, cursor + len(row)))
            cursor += len(row) + 1
        return text, chunks

    if fmt == "json":
        payload = json.loads(decode_text(data))
        if isinstance(payload, list):
            text = "\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in payload)
        else:
            text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    elif fmt == "pdf":
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages, start=1):
            value = page.extract_text() or ""
            if value.strip():
                pages.append(f"[Page {i}]\n{value}")
        text = "\n\n".join(pages)
    elif fmt == "html":
        parser = HTMLTextExtractor()
        parser.feed(decode_text(data))
        text = "".join(parser.parts)
    elif fmt == "txt":
        text = decode_text(data)
    else:
        raise ValueError("unsupported_format")

    text = normalize_text(text)
    if not text:
        raise ValueError("empty_extracted_text")
    return text, generic_chunks(text)


def load_candidates(out: Path) -> dict[str, list[dict]]:
    rows = defaultdict(list)
    with (out / "candidate_universe.jsonl").open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            rows[rec["theme"]].append(rec)
    return rows


def quantile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def stats(values: list[int]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "median": quantile(values, 0.5),
        "q1": quantile(values, 0.25),
        "q3": quantile(values, 0.75),
        "p95": quantile(values, 0.95),
        "max": max(values),
    }


def select(config: dict, out: Path, protocol_path: Path, config_path: Path) -> None:
    freeze_path = out / "candidate_universe_freeze.json"
    if not freeze_path.exists():
        raise RuntimeError("candidate universe must be frozen before selection")
    cfreeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if sha_file(out / "candidate_universe.jsonl") != cfreeze["candidate_universe_sha256"]:
        raise RuntimeError("candidate universe hash mismatch")
    if sha_file(out / "candidate_order.jsonl") != cfreeze["candidate_order_sha256"]:
        raise RuntimeError("candidate order hash mismatch")

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
    for p in (selected_path, attrition_path, chunk_path):
        if p.exists():
            p.unlink()

    candidates = load_candidates(out)
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "*/*"})
    sel_cfg = config["selection"]
    dist_cfg = config["distribution"]
    target = int(sel_cfg["target_per_theme"])
    pub_cap = int(sel_cfg["publisher_cap_per_theme"])
    max_bytes = int(dist_cfg["max_bytes"])
    max_chunks = int(dist_cfg["max_chunks"])

    selected_counts = Counter()
    publisher_counts: dict[str, Counter] = defaultdict(Counter)
    format_chunks: dict[str, list[int]] = defaultdict(list)
    theme_chunks: dict[str, list[int]] = defaultdict(list)
    dataset_chunks: list[int] = []
    started = utc_now()

    with selected_path.open("w", encoding="utf-8") as sf, attrition_path.open("w", encoding="utf-8") as af, chunk_path.open("w", encoding="utf-8") as cf:
        for theme in config["metadata_api"]["themes"]:
            ordered = sorted(candidates[theme], key=lambda r: (r["selection_key_sha256"], r["dataset_id"]))
            for ds in ordered:
                if selected_counts[theme] >= target:
                    break
                dsid = ds["dataset_id"]
                pub = publisher_key(ds)
                if publisher_counts[theme][pub] >= pub_cap:
                    af.write(json.dumps({"level":"dataset","theme":theme,"dataset_id":dsid,"reason":"publisher_cap","publisher_key":pub}, sort_keys=True) + "\n")
                    continue
                title = english_text(ds.get("title"))
                desc = english_text(ds.get("notes") or ds.get("description"))
                if not title or not desc:
                    af.write(json.dumps({"level":"dataset","theme":theme,"dataset_id":dsid,"reason":"missing_title_or_description"}, sort_keys=True) + "\n")
                    continue
                resources = [r for r in (ds.get("resources") or []) if isinstance(r, dict)]
                trials = []
                for r in resources:
                    rid = distribution_id(r, dsid)
                    if rid:
                        trials.append((distribution_key(theme, dsid, rid), rid, r))
                trials.sort(key=lambda x: (x[0], x[1]))
                kept = []
                for dkey, rid, resource in trials:
                    if len(kept) >= int(sel_cfg["retained_distributions"]):
                        break
                    urls = download_urls(resource)
                    if not urls:
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":"missing_download_url"}, sort_keys=True) + "\n")
                        continue
                    ok_lic, lic_vals, lic_scope = open_license(resource, ds, config)
                    if not ok_lic:
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":"license_not_whitelisted","license_values":lic_vals,"license_scope":lic_scope}, sort_keys=True) + "\n")
                        continue
                    url = urls[0]
                    got, err = fetch_bounded(session, url, max_bytes)
                    if got is None:
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":err,"download_url":url}, sort_keys=True) + "\n")
                        continue
                    data, http = got
                    fmt = detect_format(http["final_url"], http["content_type"], data)
                    if fmt not in set(dist_cfg["allowed_formats"]):
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":"unsupported_format","content_type":http["content_type"],"download_url":url}, sort_keys=True) + "\n")
                        continue
                    try:
                        text, chunks = extract_and_chunk(fmt, data)
                    except Exception as exc:
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":"extraction_failed","error":f"{type(exc).__name__}:{exc}"}, sort_keys=True) + "\n")
                        continue
                    if not chunks:
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":"zero_chunks"}, sort_keys=True) + "\n")
                        continue
                    if len(chunks) > max_chunks:
                        af.write(json.dumps({"level":"distribution","theme":theme,"dataset_id":dsid,"distribution_id":rid,"reason":"chunk_cap_exceeded","chunk_count":len(chunks)}, sort_keys=True) + "\n")
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
                        "payload_sha256": sha_bytes(data),
                        "byte_size": len(data),
                        "etag": http["etag"],
                        "last_modified": http["last_modified"],
                        "text": text,
                        "text_sha256": sha_text(text),
                        "chunks": chunks,
                    })

                if len(kept) < int(sel_cfg["min_eligible_distributions"]):
                    af.write(json.dumps({"level":"dataset","theme":theme,"dataset_id":dsid,"reason":"fewer_than_two_eligible_distributions","eligible_distributions":len(kept)}, sort_keys=True) + "\n")
                    continue

                dsdir_raw = raw_root / theme / ds["selection_key_sha256"][:16]
                dsdir_text = text_root / theme / ds["selection_key_sha256"][:16]
                dsdir_raw.mkdir(parents=True, exist_ok=True)
                dsdir_text.mkdir(parents=True, exist_ok=True)
                frozen_dists = []
                total_ds_chunks = 0
                for idx, item in enumerate(kept[:2]):
                    ext = {"pdf":".pdf","csv":".csv","json":".json","html":".html","txt":".txt"}[item["format"]]
                    raw_path = dsdir_raw / f"{idx:02d}_{item['payload_sha256'][:16]}{ext}"
                    text_path = dsdir_text / f"{idx:02d}_{item['text_sha256'][:16]}.txt"
                    raw_path.write_bytes(item["payload"])
                    text_path.write_text(item["text"], encoding="utf-8")
                    chunk_hashes = []
                    for ch in item["chunks"]:
                        chash = sha_text(ch.text)
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
                        k: v for k, v in item.items()
                        if k not in {"payload", "text", "chunks"}
                    } | {
                        "chunk_count": len(item["chunks"]),
                        "ordered_chunk_sha256": chunk_hashes,
                        "raw_relpath": str(raw_path.relative_to(out)),
                        "canonical_text_relpath": str(text_path.relative_to(out)),
                    })
                rec = {
                    "theme": theme,
                    "selection_rank_within_theme": selected_counts[theme],
                    "selection_key_sha256": ds["selection_key_sha256"],
                    "dataset_id": dsid,
                    "title": title,
                    "description": desc,
                    "publisher_key": pub,
                    "dataset_chunk_count": total_ds_chunks,
                    "distributions": frozen_dists,
                }
                sf.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                dataset_chunks.append(total_ds_chunks)
                publisher_counts[theme][pub] += 1
                selected_counts[theme] += 1
                print(f"SELECT {theme} {selected_counts[theme]}/{target} dataset={dsid} chunks={total_ds_chunks}", flush=True)

            if selected_counts[theme] != target:
                raise RuntimeError(f"INSUFFICIENT_ELIGIBLE_DATASETS theme={theme} selected={selected_counts[theme]} target={target}")

    environment = {
        "python": sys.version,
        "requests": requests.__version__,
        "pypdf": pypdf.__version__,
        "script_sha256": sha_file(Path(__file__)),
        "config_sha256": sha_file(config_path),
        "protocol_sha256": sha_file(protocol_path),
    }
    env_path = out / "environment_manifest.json"
    env_path.write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "protocol": config["protocol_id"],
        "selection_started_utc": started,
        "selection_completed_utc": utc_now(),
        "selected_per_theme": dict(selected_counts),
        "datasets_total": sum(selected_counts.values()),
        "distributions_total": sum(selected_counts.values()) * 2,
        "chunks_per_dataset": stats(dataset_chunks),
        "chunks_per_distribution_by_theme": {k: stats(v) for k, v in theme_chunks.items()},
        "chunks_per_distribution_by_format": {k: stats(v) for k, v in format_chunks.items()},
        "candidate_universe_sha256": sha_file(out / "candidate_universe.jsonl"),
        "candidate_order_sha256": sha_file(out / "candidate_order.jsonl"),
        "selected_corpus_manifest_sha256": sha_file(selected_path),
        "attrition_ledger_sha256": sha_file(attrition_path),
        "chunk_manifest_sha256": sha_file(chunk_path),
        "environment_manifest_sha256": sha_file(env_path),
        "script_sha256": environment["script_sha256"],
        "config_sha256": environment["config_sha256"],
        "protocol_sha256": environment["protocol_sha256"],
    }
    final_freeze.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sha_paths = [
        protocol_path, config_path, Path(__file__),
        out / "candidate_universe.jsonl", out / "candidate_order.jsonl", out / "candidate_universe_freeze.json",
        selected_path, attrition_path, chunk_path, env_path, final_freeze,
    ]
    sha_path = out / "SHA256SUMS.prequery.txt"
    sha_path.write_text("\n".join(f"{sha_file(p)}  {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}" for p in sha_paths) + "\n", encoding="utf-8")
    print("SECOND_CORPUS_V2_FROZEN", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "second_corpus_frozen_config_v2.json")
    ap.add_argument("--protocol", type=Path, default=ROOT / "docs" / "second_corpus_confirmation_protocol_v2.md")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "second_corpus_dataeuropa_v2")
    ap.add_argument("--stage", choices=("harvest", "select", "all"), default="all")
    args = ap.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    if args.stage in {"harvest", "all"}:
        harvest(config, args.out)
    if args.stage in {"select", "all"}:
        select(config, args.out, args.protocol, args.config)


if __name__ == "__main__":
    main()
