#!/bin/bash
#SBATCH --job-name=arno_missing_evidence
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --mem=3G
#SBATCH --cpus-per-task=1
python3 - <<'PY'
from pathlib import Path
import os,re,sqlite3,zlib,hashlib,json,csv,io,tarfile
R=Path.home()/'research_artifacts'
O=R/'mcp_uploads/jobs/arno_targeted_missing_evidence_20261028'
O.mkdir(parents=True,exist_ok=True)
db=R/'ARNO_MASTER_DB/ARNO_RESEARCH_MASTER.sqlite'
conn=sqlite3.connect(f'file:{db}?mode=ro',uri=True,timeout=120)
refs={n:b for n,b in conn.execute('SELECT source_path,content_zlib FROM arno_evidence_assets')}
def get(ending):
 hits=[(k,zlib.decompress(v)) for k,v in refs.items() if k.endswith(ending)]
 return hits
items={}
for key in ['C6_METHOD_AND_DECISIONS.md','C6_CONTEXT_QC_CORRECTIONS.csv','C5_CONTEXT_190_FROZEN.csv','C6_REPORT.md','C6_REPOSITORY_BLOCKED_CI.csv','C6_QC.json']:
 hits=get(key)
 items[key]=[{'name':k,'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'text':b.decode('utf8','replace')[:13000] if key.endswith(('.md','.json')) else b.decode('utf8','replace')[:8500]} for k,b in hits]
checks={'c5_sha':items['C5_CONTEXT_190_FROZEN.csv'][0]['sha256'] if items['C5_CONTEXT_190_FROZEN.csv'] else None,
 'c6_method_hints':items['C6_METHOD_AND_DECISIONS.md'],
 'c6_context_corrections':items['C6_CONTEXT_QC_CORRECTIONS.csv'],
 'C6_report':items['C6_REPORT.md'],
 'bootstrap_ci':items['C6_REPOSITORY_BLOCKED_CI.csv']}
namepat=re.compile(r'D[_-]?FINAL|D7|ROOT.*(ADJUD|DECISION|FINAL)|C3592|COMPLETE.?7.?CASE|SEVEN.?CASE|REPAIR|B3[_-]|C6.*(SCRIPT|BOOTSTRAP)',re.I)
skip={'node_modules','.git','.venv','real122_repo_cache','.t1_primary_pilot_repo_cache_v1','_work','worktrees','site-packages','__pycache__'}
roots=[R,R/'mcp_uploads',R/'ARNO_CODEQL_EXPORT_20261019',R/'D_COMPLETE_ROOT_PROVENANCE_v1_0']
outfiles=[];visited=0
for base,dirs,files in os.walk(R):
 rel=Path(base).relative_to(R)
 if len(rel.parts)>7:
  dirs[:]=[]
  continue
 dirs[:]=[d for d in dirs if d not in skip and not d.endswith('.git')]
 for fname in files:
  visited+=1
  if namepat.search(fname):
   p=Path(base)/fname
   try: size=p.stat().st_size
   except OSError:continue
   outfiles.append({'path':str(p.relative_to(R)),'bytes':size})
 outfiles=outfiles[:10000]
result={'status':'COMPLETE','files_visited':visited,'matched_file_names':len(outfiles),'filename_matches':outfiles,'frozen_c6_context':checks}
(O/'TARGETED_EVIDENCE_SEARCH.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
(O/'C6_CONTEXT_METHOD_EXCERPT.txt').write_text('\n\n'.join('### '+x+'\n'+(v[0]['text'] if v else 'NOT_FOUND') for x,v in items.items() if x not in ('C5_CONTEXT_190_FROZEN.csv',))[:55000])
print(json.dumps({'status':'COMPLETE','visited':visited,'matches':len(outfiles),'exact_named':[x for x in outfiles if any(z in x['path'] for z in ['D_FINAL_COMPLETE','COMPLETE_7_CASE','C3592','B3_'])][:45]},indent=2),flush=True)
PY