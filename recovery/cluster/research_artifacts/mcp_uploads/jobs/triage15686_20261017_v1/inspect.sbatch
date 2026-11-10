#!/bin/bash
#SBATCH --job-name=triage15686
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import json,os,re,zipfile
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
out=root/('triage15686_source_audit_job'+os.environ['SLURM_JOB_ID']);out.mkdir(exist_ok=False)
packet=root/'screen5_blind_batch_job70117/CASE_04_15686.zip'
data=[]
with zipfile.ZipFile(packet) as z:
 for n in z.namelist():
  if n.startswith('REPO/') and n.endswith(('.ts','.tsx','.js','.mjs','.cjs')) and not n.endswith('.map'):
   raw=z.read(n)
   if len(raw)>3000000:continue
   s=raw.decode('utf8',errors='replace')
   for m in re.finditer(r'\bgithubFetch\s*\(',s):
    line=s.count('\n',0,m.start())+1
    a=max(0,m.start()-240);b=min(len(s),m.end()+320)
    data.append({'path':n[5:],'line':line,'excerpt':s[a:b]})
summary={'all_call_sites':data,'count':len(data),'observation':'Frozen githubFetch accepts path starting with https:// as absolute URL and sends GITHUB_TOKEN Authorization header there; confirm no untrusted caller permits this path.'}
(out/'SOURCE_CALL_SITES.json').write_text(json.dumps(summary,indent=2)+'\n')
print('CALL_SITES',len(data),flush=True)
for x in data:
 print(x['path']+':'+str(x['line']),repr(x['excerpt'][:450]),flush=True)
PY