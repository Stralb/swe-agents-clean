#!/bin/bash
#SBATCH --job-name=E078_two_algo_smoke
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
import sys,time,json,torch
from pathlib import Path
ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
sys.path.insert(0,str(ROOT))
from src.config import RunConfig
from src.run import run
torch.set_num_threads(2)
try:torch.set_num_interop_threads(1)
except RuntimeError:pass
dd={'lr':5e-4,'replay_capacity':128,'warmup':16,'batch':8,'train_every':8,
 'target_update':32,'eps_start':.85,'eps_end':.15,'eps_decay_actions':80,'gamma':.98}
pp={'rollout':16,'epochs':1,'minibatches':2,'lr':5e-4,'ent_coef':.003}
root=Path('/home-mscluster/astrauss/e078_course_recovery')
out=root/('synthetic_smoke_'+__import__('os').environ['SLURM_JOB_ID'])
out.mkdir(parents=True,exist_ok=False)
for algo,params in [('dqn',dd),('ppo',pp)]:
 for disable in (True,False):
  cfg=RunConfig(algo=algo,game='synthetic:click',version='V0',seed=2087,
   env_seed=2901,budget=80,arch={'id':'onehotcnn_stack2','channels':8,'context_dim':48},
   params=params,updates_disabled=disable,threads=2,tag='E078_two_algo_smoke')
  t=time.monotonic();r=run(cfg,out_dir=str(out))
  diag=r['learner']
  row={'algo':algo,'updates_disabled':disable,'status':r['status'],'error':r['error'],
    'steps':r['counters']['scorer_actions'],'rewarded':r['diagnostics']['rewarded_transitions'],
    'gradient_steps':diag.get('gradient_steps',0),'rollout_events':diag.get('rollout_update_events',0),
    'cpu_s':round(time.monotonic()-t,3),
    'run_id':r['identity']['run_id']}
  print('SYNTHETIC_SMOKE_RESULT',json.dumps(row),flush=True)
  if row['error'] is not None:raise RuntimeError(row['error'])
  if not disable and row['gradient_steps']<1:raise RuntimeError('learning objective not executed')
  if disable and row['gradient_steps']!=0:raise RuntimeError('disabled updates ran')
print('E078_TWO_ALGORITHMS_TESTED_SUCCESSFULLY',out,flush=True)
PY