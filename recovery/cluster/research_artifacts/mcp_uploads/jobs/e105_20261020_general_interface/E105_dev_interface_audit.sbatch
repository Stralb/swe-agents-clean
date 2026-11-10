#!/bin/bash
#SBATCH --job-name=E105_dev_interface_audit
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import sys,numpy as np,hashlib,json,random,collections,os
sys.path.insert(0,'/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
from src.adapter import ArcSession,index_to_action,N_SIMPLE,N_ACTIONS
D=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e105_20261020_general_interface')
D.mkdir(parents=True,exist_ok=True)
out=D/('E105_DEV_ONLY_INTERFACE_AUDIT_'+os.environ['SLURM_JOB_ID']+'.json')
if out.exists():raise FileExistsError(out)
GAMES=['sb26','s5i5','lf52','tn36','g50t']
rows=[]
for game in GAMES:
 s=ArcSession()
 obs=s.start_run(game,20,0)
 rng=random.Random(106)
 frames=[]
 actions=[]
 for k in range(19):
  obs=s.obs
  if s.done:break
  f=np.asarray(obs.frame,dtype=np.uint8)
  counts=collections.Counter(map(int,f.ravel()))
  prim=[int(i) for i in np.flatnonzero(obs.mask[:N_SIMPLE])]
  clicks=np.flatnonzero(obs.mask[N_SIMPLE:])
  mask={'primitives':prim,'click_bins':len(clicks)}
  if k%3==0 and prim:idx=rng.choice(prim)
  elif len(clicks):idx=N_SIMPLE+int(rng.choice(list(clicks)))
  elif prim:idx=rng.choice(prim)
  else:break
  action,xy=index_to_action(idx)
  t=s.step(idx)
  b=np.asarray(t.next_obs.frame,dtype=np.uint8)
  delta=(f!=b)
  actions.append({'k':k,'action':int(action),'xy':list(xy) if xy else None,
  'native_reward':float(t.reward),'levels':int(s.tracker.high_water),
  'pixel_changed':int(delta.sum()),'changed_color_pair':[[[int(a),int(b)],int(n)] for (a,b),n in collections.Counter(zip(f[delta].tolist(),b[delta].tolist())).most_common(4)]})
  if k==0 or k==9:frames.append({'sample_step':k,'mask':mask,'color_hist':dict(counts),
     'unique_colors':len(counts),'nonmodal_pixels':4096-counts.most_common(1)[0][1]})
 rows.append({'game':game,'native_win_levels':int(s.obs.win_levels),'scorer_actions':int(s.tracker.actions),
    'interface_snapshots':frames,'events':actions})
 print('E105_DEV_INTERFACE_RESULT',json.dumps({'game':game,'num_primitives':frames[0]['mask']['primitives'] if frames else [],
  'click_bins':frames[0]['mask']['click_bins'] if frames else 0,
  'changed_pixel_counts':[v['pixel_changed'] for v in actions],
  'reward_events':[v for v in actions if v['native_reward']>0]},sort_keys=True),flush=True)
with out.open('x') as f:json.dump({'source':'native_sdk','GAMES_DEV_ONLY':GAMES,'rows':rows,
  'E074_reserve_unchanged':['cn04','lp85','m0r0','r11l','sk48'],
  'No_labels_solutions_or_hidden_state':True},f,indent=2)
print('E105_DEV_INTERFACE_COMPLETE',str(out),flush=True)
PY