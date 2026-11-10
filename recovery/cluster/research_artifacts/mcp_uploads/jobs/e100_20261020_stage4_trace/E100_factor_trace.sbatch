#!/bin/bash
#SBATCH --job-name=E100_stage4_trace_factors
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import hashlib,json,importlib.util,numpy as np
F=Path('/home-mscluster/astrauss/e095_from_reset_research/E095_seed28901_full_71888')
R=json.loads((F/'E095_REPORT.json').read_text())['rows'][0]
T=F/'full.jsonl';assert hashlib.sha256(T.read_bytes()).hexdigest()==R['trace_sha256']
rows=[json.loads(x) for x in T.read_text().splitlines()]
with np.load(F/'full_frames.npz') as z:frames=z['frames']
C=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e097_20261020_clean_ablation_v3/E097_clean_core_v3.py')
sp=importlib.util.spec_from_file_location('e097core',C);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
def factors(f):
 groups=m.components(f)
 grey=groups.get(11,[]);blue=groups.get(1,[]);yellow=groups.get(4,[])
 dy=None;left=None;right=None
 if len(grey)>1:
  g=sorted([q for q in grey if q['n']>=5],key=lambda q:q['x'])
  if len(g)>=2:left,right=g[0],g[-1];dy=round(left['y']-right['y'],2)
 sc=m.scene(f,np.ones(4102,dtype=bool))
 return {'grey_l_r_dy':dy,'grey_y':[round(q['y'],1) for q in grey if q['n']>=5],
  'blue_y':[round(q['y'],1) for q in blue if q['n']>=10],
  'blue_heights':[q['y1']-q['y0']+1 for q in blue if q['n']>=10],
  'h':sc['now'],'controls':len(sc['controls']),
  'left_yellow_y':round(min(yellow,key=lambda q:q['x'])['y'],1) if yellow else None}
for i,row in enumerate(rows):
 if row['stage_of_policy_decision']<3:continue
 a=frames[i];b=frames[i+1]
 old=factors(a);new=factors(b)
 print('E100_STAGE4_ACTION',json.dumps({'step':row['scorer_actions'] if 'scorer_actions' in row else row['action'],
  'site':row['xy'],'reason':row['reason'],'pixel_change':int((a!=b).sum()),
  'before':old,'after':new,'native_reward':row['reward']},sort_keys=True),flush=True)
PY