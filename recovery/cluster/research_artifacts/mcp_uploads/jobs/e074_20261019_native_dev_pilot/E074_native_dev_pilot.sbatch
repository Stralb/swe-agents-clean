#!/bin/bash
#SBATCH --job-name=E074_native_dev_pilot
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc26/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
import sys,hashlib,json,random
import numpy as np,torch,arc_agi
from arc_agi import OperationMode
from arcengine import GameAction
R=Path('/home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019')
W=Path('/home-mscluster/astrauss/e074_human_training')
sys.path.insert(0,str(R/'vendor/e069/code'))
from history_ddqn import load,coarse
torch.set_num_threads(2)
freeze=json.loads((W/'E074_TRAINING_COMPLETE_FREEZE.json').read_text())
MODE_SHA={d['mode']:d['sha256'] for d in freeze['models']}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  while b:=f.read(1<<20):h.update(b)
 return h.hexdigest()
assert len(MODE_SHA)==4
models={}
for mode in ('bc','ddqn'):
 p=W/'trained_human'/f'history_{mode}.pt'
 assert sha(p)==MODE_SHA[mode]
 models[mode],_=load(p)
arc=arc_agi.Arcade(operation_mode=OperationMode.OFFLINE)
MAX_CALLS=60
for mode in ('bc','ddqn','random'):
 env=arc.make('s5i5')
 f=env.reset();charged=1;best=int(f.levels_completed);rng=random.Random(2069)
 hframes=[coarse(np.asarray(f.frame[-1],dtype=np.uint8))]
 hact=[];hxy=[]
 failures=0;acts={}
 while charged<MAX_CALLS and str(f.state.value)!='WIN':
  if str(f.state.value)=='GAME_OVER':
   failures+=1;f=env.reset();charged+=1
   hframes=[coarse(np.asarray(f.frame[-1],dtype=np.uint8))];hact=[];hxy=[];continue
  legal=sorted(set(int(x) for x in f.available_actions if int(x)!=0))
  if not legal:break
  if mode=='random':
   aid=rng.choice(legal);xy=(rng.randrange(64),rng.randrange(64)) if aid==6 else None
  else:
   m=len(hframes);hs=np.zeros((1,4,16,16),dtype=np.uint8)
   ha=np.zeros((1,4),dtype=np.int64)
   hp=np.zeros((1,4,2),dtype=np.float32)
   hs[0,-m:]=np.stack(hframes)
   if m>1:
    ha[0,-(m-1):]=np.asarray(hact[-(m-1):],dtype=np.int64)
    hp[0,-(m-1):]=np.asarray(hxy[-(m-1):],dtype=np.float32)
   with torch.inference_mode():
    q,click=models[mode](torch.from_numpy(hs),torch.from_numpy(ha),torch.from_numpy(hp))
   values=q[0].numpy()
   aid=int(max(legal,key=lambda x:(float(values[x]),-x)))
   b=int(click.argmax(1).item())
   xy=(4*(b%16)+2,4*(b//16)+2) if aid==6 else None
  action=GameAction.from_id(aid)
  if xy is not None:r=env.step(action,data={'x':int(xy[0]),'y':int(xy[1])})
  else:r=env.step(action)
  charged+=1;acts[str(aid)]=acts.get(str(aid),0)+1
  if not r.frame:
   if str(r.state.value)!='GAME_OVER':raise RuntimeError('Empty frame in live nonterminal')
   f=r;continue
  z=coarse(np.asarray(r.frame[-1],dtype=np.uint8))
  level=int(r.levels_completed)
  if level>best:
   best=level;hframes=[z];hact=[];hxy=[]
  else:
   hframes.append(z);hframes=hframes[-4:]
   hact.append(aid);hact=hact[-3:]
   hxy.append((xy[0]/63.,xy[1]/63.) if xy else (0.,0.));hxy=hxy[-3:]
  f=r
 print('NATIVE_DEV_PILOT',json.dumps({'mode':mode,'family':'s5i5','max_calls':MAX_CALLS,
 'charged_interactions_including_resets':charged,'levels_completed':best,
 'win_levels':int(f.win_levels),'deaths':failures,'actions':acts,
 'source_five_training_family_only':True,'official_score':None}),flush=True)
print('E074_DEV_NATIVE_PILOT_DONE',flush=True)
PY