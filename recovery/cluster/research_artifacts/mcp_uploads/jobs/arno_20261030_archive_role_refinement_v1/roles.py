#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,re
from datetime import datetime,timezone
R=Path.home()/'research_artifacts'
P=R/'mcp_uploads/jobs/arno_20261030_archive_audit_v1/ALL_MEMBERS.csv'
O=R/'mcp_uploads/jobs/arno_20261030_archive_role_refinement_v1/REPORT.json'
def kind(p):
 n=Path(p).name.lower()
 for ext,t in [('.sarif','SARIF'),('.patch','PATCH'),('.diff','PATCH'),('.zip','ARCHIVE'),('.tar','ARCHIVE'),('.gz','ARCHIVE'),('.log','LOG'),('.json','JSON'),('.jsonl','JSON'),('.csv','CSV'),('.txt','TEXT'),('.md','TEXT')]:
  if n.endswith(ext):return t
 if any(n.endswith(e) for e in ['.py','.sh','.sbatch','.js','.ts','.yaml','.yml']):return 'CODE'
 return 'OTHER'
def main():
 with P.open(newline='',encoding='utf8') as f: rows=list(csv.DictReader(f))
 if len(rows)!=4610:raise RuntimeError('Archive census mismatch')
 per=defaultdict(list)
 for r in rows:
  r['new_role']=kind(r['member']);per[r['archive']].append(r)
 report={'status':'CORRECTED_ARCHIVE_ROLES','utc':datetime.now(timezone.utc).isoformat(),
 'archive_roles':{a:dict(Counter(x['new_role'] for x in seq)) for a,seq in per.items()},
 'unregistered_roles':{a:dict(Counter(x['new_role'] for x in seq if x['digest_registered']=='0')) for a,seq in per.items()},
 'all_roles':dict(Counter(x['new_role'] for x in rows)),
 'unique_patch_hashes':len({x['sha256'] for x in rows if x['new_role']=='PATCH'}),
 'specific_missing_O_names':{n:sum(Path(x['member']).name==n for x in rows) for n in ['CASE_08461_O.patch','CASE_15151_O.patch']},
 'limit':'Role uses actual member basename, not parent archive title. Missing registered hash does not prove absence of BLOB bytes.'}
 O.parent.mkdir(parents=True,exist_ok=True)
 with O.open('x') as f:json.dump(report,f,indent=2)
 print(json.dumps(report),flush=True)
if __name__=='__main__':main()
