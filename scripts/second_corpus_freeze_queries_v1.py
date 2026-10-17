#!/usr/bin/env python3
"""Freeze the 96 authored C2 confirmation queries before any retrieval run."""
from __future__ import annotations
import argparse, base64, gzip, hashlib, json, re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_PACKET="6701e6c1b15f92331be08c25d911f0e452a0dcb1f6026f28781370f71ac6ded0"
EXPECTED_ASSIGNMENT="4a92278d37aa2330aeb332922de2c654fe697d9dff2858ad90c4cfe8840964ae"
THEMES=["ECON","ENVI","HEAL","TRAN"]
QUERY_TYPES=["exact_lookup","entity_dataset_lookup","relation_comparison","topic_discovery","semantic_paraphrase","constraint_filtered_lookup"]
AUTHORED_B64="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"

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def jwrite(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def loadj(path):
    out=[]
    with path.open(encoding="utf-8") as f:
        for n,line in enumerate(f,1):
            if line.strip(): out.append(json.loads(line))
    return out

def authored():
    txt=gzip.decompress(base64.b64decode(AUTHORED_B64)).decode("utf-8")
    out={}
    for line in txt.split("\n"):
        if not line: continue
        qid,q=line.split("\t",1); out[qid]=q
    return out

def verify_manifest(path:Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        expected,rel=line.split(None,1); rel=rel.strip()
        p=ROOT/rel
        if not p.exists() or sha(p)!=expected: raise RuntimeError(f"AUTHORING_SHA_FAIL {rel}")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--authoring-dir",type=Path,default=ROOT/"results"/"second_corpus_query_authoring_v1"); ap.add_argument("--corpus-dir",type=Path,default=ROOT/"results"/"second_corpus_dataeuropa_v2_final_v2_9_100"); ap.add_argument("--out",type=Path,default=ROOT/"results"/"second_corpus_queries_v1"); a=ap.parse_args()
    packet=a.authoring_dir/"authoring_packet.jsonl"; assignment=a.authoring_dir/"source_assignment.jsonl"; pfreeze=a.authoring_dir/"authoring_packet_freeze.json"; aman=a.authoring_dir/"SHA256SUMS.authoring.txt"; cfreeze=a.corpus_dir/"corpus_freeze.json"
    for p in (packet,assignment,pfreeze,aman,cfreeze):
        if not p.exists(): raise RuntimeError(f"MISSING_INPUT {p}")
    verify_manifest(aman)
    if sha(packet)!=EXPECTED_PACKET: raise RuntimeError("AUTHORING_PACKET_HASH_MISMATCH")
    if sha(assignment)!=EXPECTED_ASSIGNMENT: raise RuntimeError("SOURCE_ASSIGNMENT_HASH_MISMATCH")
    pf=json.loads(pfreeze.read_text(encoding="utf-8"))
    if pf.get("authoring_packet_sha256")!=EXPECTED_PACKET or pf.get("source_assignment_sha256")!=EXPECTED_ASSIGNMENT: raise RuntimeError("AUTHORING_FREEZE_HASH_MISMATCH")
    if pf.get("corpus_freeze_sha256")!=sha(cfreeze): raise RuntimeError("CORPUS_FREEZE_HASH_MISMATCH")
    if pf.get("retrieval_executed") is not False or pf.get("query_texts_frozen") is not False: raise RuntimeError("AUTHORING_NOT_PRE_RETRIEVAL")
    rows=loadj(packet); qs=authored()
    ids=[r["query_id"] for r in rows]
    if len(rows)!=96 or len(set(ids))!=96 or set(ids)!=set(qs): raise RuntimeError("QUERY_ID_AUDIT_FAIL")
    cells=Counter((r["theme"],r["query_type"]) for r in rows)
    if len(cells)!=24 or any(v!=4 for v in cells.values()): raise RuntimeError("QUERY_CELL_AUDIT_FAIL")
    if len(set(qs.values()))!=96: raise RuntimeError("DUPLICATE_QUERY_TEXT")
    src_refs=0; words=[]
    for r in rows:
        q=qs[r["query_id"]].strip(); exp=2 if r["query_type"]=="relation_comparison" else 1
        if len(r["source_dataset_ids"])!=exp: raise RuntimeError(f"SOURCE_COUNT_FAIL {r['query_id']}")
        src_refs+=len(r["source_dataset_ids"]); wc=len(q.split()); words.append(wc)
        if wc<5 or wc>45: raise RuntimeError(f"QUERY_LENGTH_FAIL {r['query_id']}")
        if r["query_id"] in q or re.search(r"\bC2-[A-Z]",q): raise RuntimeError(f"INTERNAL_ID_LEAK {r['query_id']}")
        if any(d in q for d in r["source_dataset_ids"]): raise RuntimeError(f"RAW_DATASET_ID_LEAK {r['query_id']}")
    if a.out.exists() and any(a.out.iterdir()): raise RuntimeError("QUERY_FREEZE_OUTPUT_EXISTS")
    a.out.mkdir(parents=True,exist_ok=True)
    qp=a.out/"queries.jsonl"
    with qp.open("w",encoding="utf-8") as f:
        for r in rows:
            q=qs[r["query_id"]].strip(); rec={"query_id":r["query_id"],"theme":r["theme"],"query_type":r["query_type"],"cell_replicate":r["cell_replicate"],"query_text":q,"query_text_sha256":hashlib.sha256(q.encode()).hexdigest(),"source_dataset_ids":r["source_dataset_ids"],"source_selection_numbers":r["source_selection_numbers"],"source_multiplicity_Mq_from_frozen_sources":r["source_multiplicity_Mq_from_frozen_sources"]}; f.write(json.dumps(rec,ensure_ascii=False,sort_keys=True)+"\n")
    audit={"query_count":96,"query_cells":24,"queries_per_cell":4,"source_dataset_references_total":src_refs,"relation_comparison_source_count":2,"other_query_type_source_count":1,"unique_query_texts":96,"min_query_words":min(words),"max_query_words":max(words),"themes":THEMES,"query_types":QUERY_TYPES,"manual_source_grounding_review":"completed_from_frozen_authoring_packet_before_retrieval","retrieval_executed_during_authoring":False,"queries_sha256":sha(qp),"authoring_packet_sha256":sha(packet),"source_assignment_sha256":sha(assignment),"corpus_freeze_sha256":sha(cfreeze)}
    apath=a.out/"query_audit.json"; jwrite(apath,audit)
    freeze={"artifact":"SECOND_CORPUS_C2_QUERY_FREEZE_V1","status":"FROZEN_BEFORE_RETRIEVAL","query_count":96,"queries_sha256":sha(qp),"query_audit_sha256":sha(apath),"authoring_packet_sha256":sha(packet),"authoring_packet_freeze_sha256":sha(pfreeze),"source_assignment_sha256":sha(assignment),"corpus_freeze_sha256":sha(cfreeze),"query_freezer_script_sha256":sha(Path(__file__)),"retrieval_executed":False,"source_dataset_ids_frozen":True,"query_texts_frozen":True}
    fp=a.out/"query_freeze.json"; jwrite(fp,freeze)
    sp=a.out/"SHA256SUMS.query_freeze.txt"
    with sp.open("w",encoding="utf-8") as f:
        for p in (aman,packet,assignment,pfreeze,cfreeze,Path(__file__),qp,apath,fp): f.write(f"{sha(p)}  {p.relative_to(ROOT)}\n")
    print("C2_QUERY_FREEZE_PASS"); print(json.dumps(freeze,indent=2,sort_keys=True)); print("QUERY_AUDIT",json.dumps(audit,sort_keys=True))
if __name__=="__main__": main()
