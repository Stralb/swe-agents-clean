#!/bin/bash
#SBATCH --job-name=arc3-export-core
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/export-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/export-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json,os,shutil,hashlib,re,subprocess
src=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
out=Path('evidence/exported_original');out.mkdir(parents=True,exist_ok=True)
rel=['src/dqn_v1/exploration.py','src/dqn_v1/prior.py','src/dqn_v1/action_bank.py','src/dqn_v1/agent.py','src/dqn_v1/learner.py','src/dqn_v1/qnet.py','src/dqn_v1/replay.py','src/dqn.py','src/ppo.py','src/model.py','src/config.py','src/learner.py','src/adapter.py','src/bridge.py','src/run.py','src/synthetic.py','tests/test_dqn_v1.py','tests/test_random_agent.py','tests/conftest.py','requirements.txt','README.md','run_v0_v1_smoke.slurm','scripts/compare_dqn_baselines.sh','configs/splits.json']
manifest={'files':[],'assets':[],'tests':[],'git':{},'src_extra':[]}
for r in rel:
 f=src/r
 if not f.is_file():continue
 data=f.read_bytes()
 if len(data)>800000:continue
 dest=out/r;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 manifest['files'].append({'path':r,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
for f in sorted((src/'assets').rglob('*')):
 if not f.is_file():continue
 p=str(f.relative_to(src)); sz=f.stat().st_size
 manifest['assets'].append({'path':p,'bytes':sz,'sha256':hashlib.sha256(f.read_bytes()).hexdigest() if sz<2000000 else None})
for f in sorted((src/'src').rglob('*.py')):
 rel=str(f.relative_to(src))
 if rel not in [x['path'] for x in manifest['files']]:
  manifest['src_extra'].append(rel)
for f in sorted((src/'tests').glob('*.py')):
 manifest['tests'].append(str(f.relative_to(src)))
if (src/'.git').exists():
 def git(*args):
  r=subprocess.run(['git','-C',str(src),*args],capture_output=True,text=True,timeout=8)
  return r.stdout.strip()[:500] if r.returncode==0 else 'nonzero'
 manifest['git']['branch']=git('branch','--show-current')
 manifest['git']['sha']=git('rev-parse','HEAD')
 manifest['git']['status']=git('status','--porcelain')
Path('evidence/export_manifest.json').write_text(json.dumps(manifest,indent=2))
print('EXPORT_FILES',len(manifest['files']))
print('MISSING_SOURCE',' '.join(x for x in rel if x not in [i['path'] for i in manifest['files']]))
print('ASSETS',json.dumps(manifest['assets'][:30]))
print('SOURCE_EXTRA',json.dumps(manifest['src_extra'][-40:]))
print('TESTS',json.dumps(manifest['tests']))
print('GIT',manifest['git'])
PY
