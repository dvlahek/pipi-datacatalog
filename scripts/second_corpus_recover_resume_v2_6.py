#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re
from collections import Counter, defaultdict
from pathlib import Path
import requests
import second_corpus_dataeuropa_select_v2_5 as v25
core=v25.core; base=core.base
ROOT=Path(__file__).resolve().parents[1]
SELECT_RE=re.compile(r'^SELECT (ECON|ENVI|HEAL|TRAN) (\d+)/200 rank=(\d+) dataset=(.*?) chunks=(\d+)$')
EXPECTED={'ECON':(200,8256),'ENVI':(125,1937),'HEAL':(0,-1),'TRAN':(0,-1)}

def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); os.replace(tmp,path)

def appendj(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f:
        f.write(json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())

def loadj(path):
    if not path.exists(): return []
    out=[]
    with path.open(encoding='utf-8') as f:
        for n,line in enumerate(f,1):
            if line.strip(): out.append(json.loads(line))
    return out

def parse_log(path):
    rows=[]; counts=defaultdict(int)
    with path.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            m=SELECT_RE.match(line.strip())
            if not m: continue
            theme,n,rank,ds,ch=m.groups(); n=int(n); rank=int(rank); ch=int(ch)
            if n!=counts[theme]+1: raise RuntimeError(f'non-contiguous SELECT trace {theme}: got {n} expected {counts[theme]+1}')
            counts[theme]=n; rows.append({'theme':theme,'selection_number':n,'candidate_rank':rank,'dataset_id':ds,'dataset_chunk_count_logged':ch})
    for t,(cnt,last) in EXPECTED.items():
        rr=[r for r in rows if r['theme']==t]
        if len(rr)!=cnt: raise RuntimeError(f'checkpoint mismatch {t}: {len(rr)} != {cnt}')
        got=rr[-1]['candidate_rank'] if rr else -1
        if got!=last: raise RuntimeError(f'checkpoint last rank mismatch {t}: {got} != {last}')
    return rows

def load_order(source_out):
    cand={}
    for line in (source_out/'candidate_universe.jsonl').open(encoding='utf-8'):
        r=json.loads(line); cand[(r['theme'],r['dataset_id'])]=r
    ordered=defaultdict(list); byrank={}
    for line in (source_out/'candidate_order.jsonl').open(encoding='utf-8'):
        r=json.loads(line); rec=cand[(r['theme'],r['dataset_id'])]; rank=int(r['rank'])
        ordered[r['theme']].append((rank,rec)); byrank[(r['theme'],rank)]=r['dataset_id']
    for t in ordered: ordered[t].sort(key=lambda x:x[0])
    return cand,ordered,byrank

def checkpoint_pub(row,config,source_out):
    p=core.detail_cache_path(source_out,row['theme'],row['candidate_rank'],row['dataset_id'])
    if not p.exists(): raise RuntimeError(f'missing cached detail for checkpoint: {p}')
    w=json.loads(p.read_text(encoding='utf-8'))
    if w.get('transport_outcome'): raise RuntimeError(f'checkpoint detail unavailable {row}')
    d=core.detail_record(w,config); did=core.detail_dataset_id(d)
    if did!=row['dataset_id']: raise RuntimeError(f'checkpoint detail id mismatch {row}')
    ds=base.minimal_dataset(row['theme'],d); ds['dataset_id']=row['dataset_id']
    return base.publisher_key(ds)

def ext(fmt): return {'pdf':'.pdf','csv':'.csv','json':'.json','html':'.html','xhtml':'.html','txt':'.txt'}.get(fmt,'.bin')

def evaluate(session,config,source_out,recovery_out,theme,rank,candidate,pubcounts,selnum):
    dsid=candidate['dataset_id']
    w,dp=v25.fetch_detail_cached_nonfatal(session,config,source_out,theme,rank,dsid)
    if w.get('transport_outcome'):
        return False,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'outcome':'rejected','reason':'detail_unavailable','detail_transport_outcome':w.get('transport_outcome')}
    d=core.detail_record(w,config); did=core.detail_dataset_id(d)
    if not did: return False,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'outcome':'rejected','reason':'detail_missing_canonical_id'}
    if did!=dsid: return False,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'outcome':'rejected','reason':'detail_identity_mismatch','detail_id':did}
    ds=base.minimal_dataset(theme,d); ds['dataset_id']=dsid; ds['selection_key_sha256']=candidate['selection_key_sha256']
    pub=base.publisher_key(ds); cap=int(config['selection']['publisher_cap_per_theme'])
    if pubcounts[theme][pub]>=cap: return False,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'outcome':'rejected','reason':'publisher_cap','publisher_key':pub}
    title=base.english_text(ds.get('title')); desc=base.english_text(ds.get('notes') or ds.get('description'))
    if not title or not desc: return False,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'outcome':'rejected','reason':'missing_title_or_description'}
    trials=[]
    for r in [x for x in (ds.get('resources') or []) if isinstance(x,dict)]:
        rid=base.distribution_id(r,dsid)
        if rid: trials.append((base.distribution_key(theme,dsid,rid),rid,r))
    trials.sort(key=lambda x:(x[0],x[1]))
    dc=config['distribution']; kept=[]; events=[]
    for dkey,rid,r in trials:
        if len(kept)>=int(config['selection']['retained_distributions']): break
        urls=base.download_urls(r)
        if not urls: events.append({'distribution_id':rid,'reason':'missing_download_url'}); continue
        ok,lic,scope=base.open_license(r,ds,config)
        if not ok: events.append({'distribution_id':rid,'reason':'license_not_whitelisted'}); continue
        url=urls[0]; got,err=v25.fetch_bounded_retry_nonfatal(session,url,int(dc['max_bytes']),int(dc.get('download_retry_attempts',3)))
        if got is None: events.append({'distribution_id':rid,'reason':err,'download_url':url}); continue
        data,http=got; fmt=base.detect_format(http['final_url'],http['content_type'],data)
        if fmt not in set(dc['allowed_formats']): events.append({'distribution_id':rid,'reason':'unsupported_format'}); continue
        try: text,chunks=base.extract_and_chunk(fmt,data)
        except Exception as exc: events.append({'distribution_id':rid,'reason':'extraction_failed','error':f'{type(exc).__name__}:{exc}'}); continue
        if not chunks: events.append({'distribution_id':rid,'reason':'zero_chunks'}); continue
        if len(chunks)>int(dc['max_chunks']): events.append({'distribution_id':rid,'reason':'chunk_cap_exceeded','chunk_count':len(chunks)}); continue
        kept.append({'distribution_id':rid,'distribution_key_sha256':dkey,'download_url':url,'final_url':http['final_url'],'content_type':http['content_type'],'format':fmt,'license_values':lic,'license_scope':scope,'payload':data,'payload_sha256':base.sha_bytes(data),'byte_size':len(data),'etag':http['etag'],'last_modified':http['last_modified'],'text':text,'text_sha256':base.sha_text(text),'chunks':chunks})
    if len(kept)<int(config['selection']['min_eligible_distributions']):
        return False,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'outcome':'rejected','reason':'fewer_than_two_eligible_distributions','eligible_distributions':len(kept),'distribution_events':events}
    rr=recovery_out/'new_selected_raw'/theme/candidate['selection_key_sha256'][:16]; tt=recovery_out/'new_selected_canonical_text'/theme/candidate['selection_key_sha256'][:16]
    rr.mkdir(parents=True,exist_ok=True); tt.mkdir(parents=True,exist_ok=True)
    fd=[]; total=0
    for i,item in enumerate(kept[:2]):
        rp=rr/f"{i:02d}_{item['payload_sha256'][:16]}{ext(item['format'])}"; tp=tt/f"{i:02d}_{item['text_sha256'][:16]}.txt"
        rp.write_bytes(item['payload']); tp.write_text(item['text'],encoding='utf-8'); cr=[]
        for ch in item['chunks']:
            cr.append({'chunk_index':ch.index,'chunk_text_sha256':base.sha_text(ch.text),'character_count':len(ch.text),'char_start':ch.char_start,'char_end':ch.char_end})
        total+=len(item['chunks']); fd.append({k:v for k,v in item.items() if k not in {'payload','text','chunks'}}|{'chunk_count':len(item['chunks']),'chunks':cr,'raw_relpath':str(rp.relative_to(recovery_out)),'canonical_text_relpath':str(tp.relative_to(recovery_out))})
    return True,{'theme':theme,'candidate_rank':rank,'dataset_id':dsid,'selection_number':selnum,'selection_key_sha256':candidate['selection_key_sha256'],'publisher_key':pub,'title':title,'description':desc,'dataset_chunk_count':total,'metadata_detail_relpath':str(dp.relative_to(source_out)),'metadata_detail_file_sha256':base.sha_file(dp),'metadata_detail_response_sha256':w['response_sha256'],'metadata_detail_retrieved_utc':w['retrieved_utc'],'distributions':fd}

def ensure_checkpoint(log,source_out,recovery_out,config):
    rows=parse_log(log); cand,ordered,byrank=load_order(source_out)
    for r in rows:
        if (r['theme'],r['dataset_id']) not in cand or byrank.get((r['theme'],r['candidate_rank']))!=r['dataset_id']: raise RuntimeError(f'frozen order mismatch {r}')
    cp=recovery_out/'checkpoint_selected_from_v2_4_log.jsonl'; sm=recovery_out/'checkpoint_summary.json'
    if cp.exists():
        if loadj(cp)!=rows: raise RuntimeError('existing recovery checkpoint differs from V2.4 log')
    else:
        for r in rows: appendj(cp,r)
        atomic(sm,{'source_log_sha256':base.sha_file(log),'checkpoint_counts':{t:sum(x['theme']==t for x in rows) for t in config['metadata_api']['themes']},'checkpoint_last_rank':{t:max([x['candidate_rank'] for x in rows if x['theme']==t],default=-1) for t in config['metadata_api']['themes']},'candidate_universe_sha256':base.sha_file(source_out/'candidate_universe.jsonl'),'candidate_order_sha256':base.sha_file(source_out/'candidate_order.jsonl'),'note':'Recovered dataset-selection identities from preserved V2.4 stdout log after destructive pre-query reset. Original checkpoint payload bytes are not claimed recovered.'})
    return rows,ordered

def stat(recovery_out,rows,themes):
    o=loadj(recovery_out/'candidate_outcomes_after_checkpoint.jsonl'); s=loadj(recovery_out/'selected_extension_manifest.jsonl')
    return {'checkpoint_selected':{t:sum(x['theme']==t for x in rows) for t in themes},'processed_after_checkpoint':{t:sum(x['theme']==t for x in o) for t in themes},'selected_after_checkpoint':{t:sum(x['theme']==t for x in s) for t in themes},'last_processed_rank':{t:max([x['candidate_rank'] for x in o if x['theme']==t],default=None) for t in themes}}

def resume(config,source_out,recovery_out,rows,ordered):
    themes=config['metadata_api']['themes']; target=int(config['selection']['target_per_theme']); pubs=defaultdict(Counter); counts=Counter(); bytheme={t:[x for x in rows if x['theme']==t] for t in themes}
    for t in themes:
        for r in bytheme[t]: pubs[t][checkpoint_pub(r,config,source_out)]+=1; counts[t]+=1
    op=recovery_out/'candidate_outcomes_after_checkpoint.jsonl'; sp=recovery_out/'selected_extension_manifest.jsonl'; outcomes=loadj(op); sels=loadj(sp); last={}
    seen=set()
    for r in outcomes:
        k=(r['theme'],int(r['candidate_rank']))
        if k in seen: raise RuntimeError(f'duplicate outcome {k}')
        seen.add(k); last[r['theme']]=max(last.get(r['theme'],-1),int(r['candidate_rank']))
    for r in sels: counts[r['theme']]+=1; pubs[r['theme']][r['publisher_key']]+=1
    sess=requests.Session(); sess.headers.update({'User-Agent':base.UA})
    print('RECOVERY_RESUME_START',json.dumps(stat(recovery_out,rows,themes),sort_keys=True),flush=True)
    for t in themes:
        if counts[t]>=target: print(f'RECOVERY_THEME_ALREADY_COMPLETE {t} selected={counts[t]}',flush=True); continue
        cplast=max([r['candidate_rank'] for r in bytheme[t]],default=-1); start=max(cplast,last.get(t,-1))+1
        print(f'RECOVERY_THEME_RESUME {t} start_rank={start} selected={counts[t]}/{target}',flush=True)
        for rank,cand in ordered[t]:
            if rank<start: continue
            if counts[t]>=target: break
            ok,res=evaluate(sess,config,source_out,recovery_out,t,rank,cand,pubs,counts[t]+1)
            if ok:
                appendj(sp,res); pubs[t][res['publisher_key']]+=1; counts[t]+=1
                appendj(op,{'theme':t,'candidate_rank':rank,'dataset_id':cand['dataset_id'],'outcome':'selected','selection_number':counts[t],'dataset_chunk_count':res['dataset_chunk_count']})
                print(f"RECOVERY_SELECT {t} {counts[t]}/{target} rank={rank} dataset={cand['dataset_id']} chunks={res['dataset_chunk_count']}",flush=True)
            else: appendj(op,res)
            if rank%100==0: print(f'RECOVERY_PROGRESS {t} rank={rank} selected={counts[t]}/{target}',flush=True)
        if counts[t]!=target: raise RuntimeError(f'RECOVERY_INSUFFICIENT {t} {counts[t]}/{target}')
        print(f'RECOVERY_THEME_COMPLETE {t} selected={counts[t]}',flush=True)
    s=stat(recovery_out,rows,themes); atomic(recovery_out/'selection_resume_complete.json',s); print('RECOVERY_SELECTION_COMPLETE',json.dumps(s,sort_keys=True),flush=True)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',type=Path,default=ROOT/'config'/'second_corpus_frozen_config_v2_5.json'); ap.add_argument('--source-out',type=Path,default=ROOT/'results'/'second_corpus_dataeuropa_v2'); ap.add_argument('--source-log',type=Path,default=ROOT/'results'/'second_corpus_select_v2_4.log'); ap.add_argument('--recovery-out',type=Path,default=ROOT/'results'/'second_corpus_dataeuropa_v2_recovery_v2_6'); ap.add_argument('--mode',choices=['checkpoint','status','resume'],default='resume'); a=ap.parse_args()
    config=json.loads(a.config.read_text(encoding='utf-8')); core.verify_frozen_candidate_universe(config,a.source_out); rows,ordered=ensure_checkpoint(a.source_log,a.source_out,a.recovery_out,config)
    if a.mode=='checkpoint': print('RECOVERY_CHECKPOINT_PASS'); print(json.dumps(stat(a.recovery_out,rows,config['metadata_api']['themes']),indent=2,sort_keys=True)); return
    if a.mode=='status': print(json.dumps(stat(a.recovery_out,rows,config['metadata_api']['themes']),indent=2,sort_keys=True)); return
    resume(config,a.source_out,a.recovery_out,rows,ordered)
if __name__=='__main__': main()
