#!/usr/bin/env python3
"""Bootstrap the frozen data.europa.eu second-corpus snapshot.

Discovery/selection only: no retrieval evaluation, qrels, generation, or tuning.
Dependencies: requests
"""
from __future__ import annotations
import argparse, hashlib, json, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests

SPARQL_ENDPOINT = "https://data.europa.eu/sparql"
FREEZE_SEED = "SECOND_CORPUS_DATAEUROPA_V1"
THEMES = {
    "ENVI": "http://publications.europa.eu/resource/authority/data-theme/ENVI",
    "TRAN": "http://publications.europa.eu/resource/authority/data-theme/TRAN",
    "HEAL": "http://publications.europa.eu/resource/authority/data-theme/HEAL",
    "ECON": "http://publications.europa.eu/resource/authority/data-theme/ECON",
}
ALLOWED_EXT = {".pdf", ".txt", ".csv", ".json", ".xml", ".html", ".htm"}
ALLOWED_MIME = ("text/", "application/pdf", "application/json", "application/xml", "application/xhtml+xml", "application/csv")
UA = "retrieval-provenance-second-corpus/1.0 research snapshot"

def sha_bytes(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def sha_text(s: str) -> str: return sha_bytes(s.encode("utf-8"))
def val(b: dict, k: str):
    x = b.get(k)
    return x.get("value") if isinstance(x, dict) else None

def sparql(theme_uri: str, limit: int, offset: int) -> list[dict]:
    q = f'''PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?dataset ?title ?description ?publisher ?distribution ?accessURL ?downloadURL ?mediaType ?format WHERE {{
  ?dataset a dcat:Dataset ; dcat:theme <{theme_uri}> ; dct:title ?title ; dct:description ?description ; dcat:distribution ?distribution .
  OPTIONAL {{ ?dataset dct:publisher ?pub . OPTIONAL {{ ?pub foaf:name ?publisher }} OPTIONAL {{ ?pub rdfs:label ?publisher }} }}
  OPTIONAL {{ ?distribution dcat:accessURL ?accessURL }}
  OPTIONAL {{ ?distribution dcat:downloadURL ?downloadURL }}
  OPTIONAL {{ ?distribution dcat:mediaType ?mediaType }}
  OPTIONAL {{ ?distribution dct:format ?format }}
  FILTER(LANG(?title) = "" || LANGMATCHES(LANG(?title), "en"))
  FILTER(LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
}} ORDER BY ?dataset ?distribution LIMIT {int(limit)} OFFSET {int(offset)}'''
    r = requests.post(SPARQL_ENDPOINT, data={"query": q}, headers={"Accept":"application/sparql-results+json","User-Agent":UA}, timeout=120)
    r.raise_for_status()
    return r.json()["results"]["bindings"]

def collect(theme: str, page_rows: int, max_rows: int) -> dict:
    out = {}
    for off in range(0, max_rows, page_rows):
        rows = sparql(THEMES[theme], page_rows, off)
        if not rows: break
        for b in rows:
            ds, dist = val(b,"dataset"), val(b,"distribution")
            if not ds or not dist: continue
            rec = out.setdefault(ds,{"dataset_uri":ds,"title":val(b,"title") or "","description":val(b,"description") or "","publisher":val(b,"publisher") or "","theme":theme,"distributions":{}})
            d = rec["distributions"].setdefault(dist,{"distribution_uri":dist,"access_url":val(b,"accessURL"),"download_url":val(b,"downloadURL"),"media_type":val(b,"mediaType"),"format":val(b,"format")})
            if not d.get("download_url") and val(b,"downloadURL"): d["download_url"] = val(b,"downloadURL")
            if not d.get("access_url") and val(b,"accessURL"): d["access_url"] = val(b,"accessURL")
        if len(rows) < page_rows: break
        time.sleep(0.2)
    return out

def order_key(theme: str, uri: str) -> str: return sha_text(f"{FREEZE_SEED}|{theme}|{uri}")
def choose_url(d: dict): return d.get("download_url") or d.get("access_url")

def acceptable(url: str, ct: str) -> bool:
    if Path(urlparse(url).path).suffix.lower() in ALLOWED_EXT: return True
    ct = (ct or "").split(";",1)[0].lower().strip()
    return any(ct.startswith(x) for x in ALLOWED_MIME)

def ext_for(url: str, ct: str) -> str:
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in ALLOWED_EXT: return ext
    ct = (ct or "").split(";",1)[0].lower().strip()
    return {"application/pdf":".pdf","application/json":".json","application/xml":".xml","application/xhtml+xml":".html","text/html":".html","text/csv":".csv","text/plain":".txt","text/xml":".xml"}.get(ct,".bin")

def fetch(session, url: str, max_bytes: int):
    try:
        with session.get(url,stream=True,timeout=(20,90),allow_redirects=True) as r:
            if r.status_code != 200: return None
            ct = r.headers.get("Content-Type","")
            if not acceptable(str(r.url),ct): return None
            clen = r.headers.get("Content-Length")
            if clen:
                try:
                    if int(clen) > max_bytes: return None
                except ValueError: pass
            buf=bytearray()
            for chunk in r.iter_content(256*1024):
                if chunk:
                    buf.extend(chunk)
                    if len(buf) > max_bytes: return None
            return bytes(buf),{"requested_url":url,"final_url":str(r.url),"status_code":r.status_code,"content_type":ct,"content_length":len(buf),"etag":r.headers.get("ETag"),"last_modified":r.headers.get("Last-Modified")}
    except requests.RequestException:
        return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="second_corpus_dataeuropa_v1")
    ap.add_argument("--per-theme",type=int,default=200)
    ap.add_argument("--max-file-mib",type=float,default=5.0)
    ap.add_argument("--raw-budget-gib",type=float,default=8.0)
    ap.add_argument("--page-rows",type=int,default=2000)
    ap.add_argument("--max-sparql-rows-per-theme",type=int,default=40000)
    ap.add_argument("--sleep",type=float,default=0.1)
    a=ap.parse_args()
    root=Path(a.out).resolve(); raw=root/"raw"; raw.mkdir(parents=True,exist_ok=True)
    max_bytes=int(a.max_file_mib*1024**2); budget=int(a.raw_budget_gib*1024**3); total=0
    sess=requests.Session(); sess.headers.update({"User-Agent":UA})
    manifest=[]
    for theme in THEMES:
        print("DISCOVER",theme,flush=True)
        candidates=collect(theme,a.page_rows,a.max_sparql_rows_per_theme)
        ordered=sorted(candidates.values(),key=lambda r:order_key(theme,r["dataset_uri"]))
        selected=0
        for rec in ordered:
            if selected>=a.per_theme: break
            if not rec["title"].strip() or not rec["description"].strip(): continue
            dists=list(rec["distributions"].values())
            if len(dists)<2: continue
            dists.sort(key=lambda d:sha_text(f'{FREEZE_SEED}|{theme}|{rec["dataset_uri"]}|{d["distribution_uri"]}'))
            dskey=order_key(theme,rec["dataset_uri"]); dsdir=raw/theme/dskey[:16]; dsdir.mkdir(parents=True,exist_ok=True)
            kept=[]
            for d in dists:
                if len(kept)>=2: break
                url=choose_url(d)
                if not url or not url.startswith(("http://","https://")): continue
                got=fetch(sess,url,max_bytes); time.sleep(a.sleep)
                if got is None: continue
                data,http=got
                if total+len(data)>budget: raise RuntimeError("RAW_BUDGET_EXCEEDED")
                h=sha_bytes(data); p=dsdir/f'{len(kept):02d}_{h[:16]}{ext_for(http["final_url"],http["content_type"])}'; p.write_bytes(data); total+=len(data)
                kept.append({**d,**http,"local_relpath":str(p.relative_to(root)),"content_sha256":h})
            if len(kept)<2:
                for p in dsdir.glob("*"):
                    total-=p.stat().st_size; p.unlink()
                try: dsdir.rmdir()
                except OSError: pass
                continue
            manifest.append({"selection_rank_within_theme":selected,"selection_key_sha256":dskey,"theme":theme,"dataset_uri":rec["dataset_uri"],"title":rec["title"],"description":rec["description"],"publisher":rec["publisher"],"distributions":kept})
            selected+=1
            print(f'SELECT {theme} {selected}/{a.per_theme} raw_total={total/1024**3:.3f} GiB',flush=True)
        if selected!=a.per_theme: raise RuntimeError(f'INSUFFICIENT_ELIGIBLE_DATASETS {theme} {selected}/{a.per_theme}')
    mp=root/"dataeuropa_snapshot_manifest.jsonl"
    with mp.open("w",encoding="utf-8") as f:
        for r in manifest: f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n")
    freeze={"protocol":"SECOND_CORPUS_DATAEUROPA_V1","themes":THEMES,"per_theme":a.per_theme,"datasets_total":len(manifest),"distributions_per_dataset":2,"max_file_bytes":max_bytes,"raw_budget_bytes":budget,"raw_downloaded_bytes":total,"manifest_sha256":sha_bytes(mp.read_bytes()),"selection_seed":FREEZE_SEED}
    fp=root/"dataeuropa_snapshot_freeze.json"; fp.write_text(json.dumps(freeze,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    (root/"SHA256SUMS.snapshot.txt").write_text(f'{sha_bytes(mp.read_bytes())}  {mp.name}\n{sha_bytes(fp.read_bytes())}  {fp.name}\n',encoding="utf-8")
    print("SECOND_CORPUS_SNAPSHOT_FROZEN",flush=True); print(json.dumps(freeze,indent=2),flush=True)
if __name__=="__main__": main()
