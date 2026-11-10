#!/bin/bash
#SBATCH --job-name=onezip7_smoke
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:07:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import zipfile,tempfile,subprocess,json,hashlib
f=Path.home()/'research_artifacts/prevention_pilot_phase2/seven_case_onezip_20261020/ALL_SEVEN_CASES_COMPLETE_TEMP_CHAT_INPUT_20261020.zip'
with tempfile.TemporaryDirectory(prefix="master7smoke_") as tmp:
 d=Path(tmp)
 with zipfile.ZipFile(f) as z: z.extractall(d)
 proc=lambda *args: subprocess.run(['python3','TOOLS/workflow.py',*args],cwd=d,capture_output=True,text=True,check=True)
 for case in ('08152','32759'):
  proc('prepare','--case',case,'--arm','H1')
  w=d/'WORKSPACE'/('CASE_'+case+'_H1_r01')/'WORK'
  (w/'__RESEARCHER_SMOKE_MARKER.txt').write_text('Temporary isolated harness verification only.\n')
  (d/'OUTPUT'/'runlogs').mkdir(parents=True,exist_ok=True)
  (d/'OUTPUT'/'runlogs'/('CASE_'+case+'_H1_r01_runlog.txt')).write_text('Researcher smoke test, no actual implementation.\n')
  proc('export','--case',case,'--arm','H1')
 r=proc('pack','--allow-partial')
 with zipfile.ZipFile(d/'ALL_7_CASE_MININFO_PATCHES_FOR_WITS.zip') as z:
  m=json.loads(z.read('RUN_MANIFEST.json'))
  assert len(m['results'])==2 and len(m['missing'])==19
  assert all(z.read('patches/CASE_'+c+'_H1_r01.patch') for c in ('08152','32759'))
 print(json.dumps({'smoke':'PASS','cases':['08152','32759'],'export':'PASS','partial_pack':'PASS','master_sha256':hashlib.sha256(f.read_bytes()).hexdigest()}))
PY
