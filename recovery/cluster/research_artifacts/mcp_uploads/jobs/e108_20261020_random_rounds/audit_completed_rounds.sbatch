#!/bin/bash
#SBATCH --job-name=E108_round_mechanisms
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import json
W=Path('/home-mscluster/astrauss/e108_random_development_rounds')
for rn in (1,2):
 root=W/('round_%02d'%rn);fs=list(root.glob('*/*/candidate/result.json'))
 allstats=Counter();micro=0;micro_changed=0;steps=0;success=0
 for file in fs:
  r=json.loads(file.read_text())
  if r.get('error'):continue
  allstats.update(r['stats']);success+=r['completed_levels']>0
  for line in (file.parent/'trace.jsonl').read_text().splitlines():
   x=json.loads(line);u=x['observation_update'];steps+=1
   if 0<u.get('pixels',999)<4:
    micro+=1;micro_changed+=bool(u.get('state_changed'))
 print('BATCH_MECHANISM_AUDIT',json.dumps({'round':rn,'completed_candidate_trials':len(fs),
  'trials_with_native_progress':success,'decisions':steps,'microchanges':micro,
  'microchanges_altering_state_hash':micro_changed,'stats':dict(allstats)},sort_keys=True),flush=True)
PY