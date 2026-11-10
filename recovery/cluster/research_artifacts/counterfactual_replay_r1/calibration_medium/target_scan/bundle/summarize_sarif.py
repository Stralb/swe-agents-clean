#!/usr/bin/env python3
import json, sys, re, csv
from pathlib import Path

def load_results(path, target):
    d=json.load(open(path,encoding='utf-8'))
    out=[]
    for run in d.get('runs',[]):
        for r in run.get('results',[]):
            rid=r.get('ruleId') or r.get('rule',{}).get('id')
            if rid != target: continue
            locs=r.get('locations') or []
            if not locs: continue
            pl=locs[0].get('physicalLocation',{})
            al=pl.get('artifactLocation',{})
            uri=(al.get('uri') or '').replace('\\','/')
            reg=pl.get('region',{})
            st=int(reg.get('startLine') or 0); en=int(reg.get('endLine') or st)
            msg=(r.get('message',{}) or {}).get('text','')
            pf=r.get('partialFingerprints') or {}
            fp=pf.get('primaryLocationLineHash') or pf.get('primaryLocationStartColumnFingerprint') or ''
            key=(rid,uri,fp) if fp else (rid,uri,st,msg)
            out.append({'key':key,'uri':uri,'start':st,'end':en,'message':msg})
    return out

def added_lines(patch):
    byfile={}; cur=None; newln=None
    for line in Path(patch).read_text(encoding='utf-8',errors='replace').splitlines():
        if line.startswith('+++ '):
            p=line[4:].split('\t')[0]
            if p.startswith('b/'): p=p[2:]
            cur=None if p=='/dev/null' else p
            if cur: byfile.setdefault(cur,set())
        elif line.startswith('@@'):
            m=re.search(r'\+(\d+)(?:,(\d+))?',line)
            newln=int(m.group(1)) if m else None
        elif newln is not None and cur:
            if line.startswith('+') and not line.startswith('+++'):
                byfile[cur].add(newln); newln+=1
            elif line.startswith('-') and not line.startswith('---'):
                pass
            else:
                newln+=1
    return byfile

def norm_uri(u):
    u=u.replace('file://','').lstrip('/')
    # CodeQL usually emits source-root-relative paths. If absolute, retain the tail after common work dirs.
    for marker in ('/repo/','/src/','/head/','/base/'):
        if marker in '/'+u:
            u=('/'+u).split(marker,1)[1]
    return u

base_s, head_s, patch, target, run_id, pair_id, role, out_csv = sys.argv[1:9]
b=load_results(base_s,target); h=load_results(head_s,target)
bkeys={x['key'] for x in b}
introduced=[x for x in h if x['key'] not in bkeys]
adds=added_lines(patch)
linked=[]
for x in introduced:
    u=norm_uri(x['uri'])
    cand=None
    for f,lines in adds.items():
        nf=norm_uri(f)
        if u==nf or u.endswith('/'+nf) or nf.endswith('/'+u):
            cand=lines; break
    if cand and any(ln in cand for ln in range(x['start'],x['end']+1)):
        linked.append(x)
row={
'run_id':run_id,'pair_id':pair_id,'role':role,'target_rule':target,
'base_target_count':len(b),'head_target_count':len(h),
'introduced_target_count':len(introduced),'added_line_linked_target_count':len(linked),
'historical_rule_reproduced':'YES' if introduced else 'NO',
'linked_to_patch':'YES' if linked else 'NO'}
with open(out_csv,'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=row.keys()); w.writeheader(); w.writerow(row)
print(','.join(f'{k}={v}' for k,v in row.items()))
