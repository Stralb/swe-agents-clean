#!/bin/bash
#SBATCH --job-name=E094_planner_trace_audit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import json,numpy as np,hashlib,importlib.util
D=Path('/home-mscluster/astrauss/e093_from_reset_research/E093_seed28901_full_71884')
S=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e093_20261020_online_hypothesis/E093_online_core_v0.py')
mod=importlib.util.module_from_spec(importlib.util.spec_from_file_location('E093',S))
mod.__spec__.loader.exec_module(mod)
rep=json.loads((D/'E093_REPORT.json').read_text())['rows'][0]
file=D/'full.jsonl'
assert hashlib.sha256(file.read_bytes()).hexdigest()==rep['trace_sha256']
trace=[json.loads(s) for s in file.read_text().splitlines()]
with np.load(D/'full_frames.npz') as z:frames=z['frames']
assert len(frames)==len(trace)+1
for i,r in enumerate(trace):
 if r['stage_of_policy_decision']<2:continue
 before=frames[i];after=frames[i+1]
 s=mod.scene(before,np.ones(4102,bool))
 h=s['now'];goal=s['goals'][0] if s['goals'] else None
 target=goal.get('target') if goal and goal['kind']=='height' else None
 bad=tuple(x-y for x,y in zip(h,target)) if target else None
 print('E094_STEP',json.dumps({'action':r['action'],'reason':r['reason'],'xy':r['xy'],
   'h':h,'target':target,'difference':bad,'delta':r['new_evidence'].get('delta'),
   'pred':r.get('predicted_hypothesis'),'reward':r['reward'],
   'controls':[(x[1],x[2]) for x in s['controls']],
   'pillars':s['pillars']},sort_keys=True),flush=True)
PY