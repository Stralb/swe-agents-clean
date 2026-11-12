#!/bin/bash
#SBATCH --job-name=E083_verify_l3_replay
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,logging,sys
logging.disable(logging.INFO)
ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
sys.path.insert(0,str(ROOT))
from src.adapter import ArcSession
from src.e027.reproducibility import install_reproducibility
import numpy as np
install_reproducibility()
base=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
report=json.loads((base/'E075_REPORT.json').read_text())
rec=next(r for r in report['rows'] if r['mode']=='repeat')
src=base/'repeat.jsonl'
assert hashlib.sha256(src.read_bytes()).hexdigest()==rec['trace_sha256']
events=[json.loads(x) for x in src.read_text().splitlines()]
checkpoint=next(i for i,r in enumerate(events) if float(r['native_level_reward'])>0 and int(r['progress'])>=2)
print('E083_ORIGINAL_PREFIX_ACTIONS',checkpoint+1,'levels',2,'action_at',events[checkpoint]['action_number'],flush=True)
s=ArcSession();s.start_run('vc33',160,0)
def digest(frame):return hashlib.sha256(np.asarray(frame,dtype=np.int8).tobytes()).hexdigest()
checks=0
for i,row in enumerate(events[:checkpoint+1]):
 before=digest(s.obs.frame)
 if before!=row['frame_sha_before']:
  raise RuntimeError(f'diverged BEFORE action index={i}; expected {row["frame_sha_before"]} observed {before}')
 t=s.step(int(row['action_index']))
 after=digest(t.next_obs.frame)
 if after!=row['frame_sha_after']:
  raise RuntimeError(f'diverged AFTER action index={i}; expected {row["frame_sha_after"]} observed {after}')
 assert int(s.tracker.high_water)==int(row['progress']), (i,s.tracker.high_water,row['progress'])
 checks+=2
assert s.tracker.high_water>=2
print('E083_NATIVE_PREFIX_REPLAY_VERIFIED',
 json.dumps({'game':'vc33','seed':0,'original_policy_seed':28901,
 'transition_count':checkpoint+1,'frame_hash_checks':checks,
 'levels_reached':s.tracker.high_water,'score_actions':s.tracker.actions,
 'last_frame_sha256':digest(s.obs.frame),
 'remaining_actions':160-s.tracker.actions,
 'prefix_is_privileged':True,'heldout_opened':False}),flush=True)
PY