#!/bin/bash
#SBATCH --job-name=case21942issue
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import zipfile,io,os,hashlib
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
bundle=root/'two_new_clean_baselines_job70029/PHASE2_TWO_NEW_CASES_ONE_ZIP.zip'
out=root/('case21942_full_issue_audit_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
with zipfile.ZipFile(bundle) as z:
 original=z.read('CASE_1_21942/SOURCE_21942.zip')
 assert hashlib.sha256(original).hexdigest()=='eb431888a4a29c866ddbf6dbc019350ab6c2a3bcd42cf039c4d920fced8a4788'
with zipfile.ZipFile(io.BytesIO(original)) as z:
 files=z.namelist()
 print('FILES',len(files),flush=True)
 for file in ['ISSUE.md','REPO/src/cli/installer.ts','REPO/__tests__/codex-plugin.test.ts','REPO/package.json']:
  if file in files:
   b=z.read(file)
   (out/('ISSUE_ORIGINAL.md' if file=='ISSUE.md' else file.replace('/','__'))).write_bytes(b)
   print('WROTE',file,len(b),flush=True)
  else:
   print('MISSING',file,flush=True)
 print('REPO SAMPLE',files[:18],flush=True)
PY
