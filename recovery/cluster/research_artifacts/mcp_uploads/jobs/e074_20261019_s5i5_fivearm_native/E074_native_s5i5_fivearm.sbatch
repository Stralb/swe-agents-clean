#!/bin/bash
#SBATCH --job-name=E074_s5i5_native_dev
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export PYTHONUNBUFFERED=1
export E074_JOB_ID="${SLURM_JOB_ID:-unknown}"
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
from collections import Counter
import hashlib,json,os,random,sys,time
import numpy as np, torch, arc_agi
from arc_agi import OperationMode
from arcengine import GameAction
R=Path('/home-mscluster/astrauss/E074_HUMAN_TO_POLICY_20261019')
W=Path('/home-mscluster/astrauss/e074_human_training')
OUT=W/'native_dev'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'vendor/e069/code'))
from history_ddqn import load,coarse
torch.set_num_threads(2)
freeze=json.loads((W/'E074_TRAINING_COMPLETE_FREEZE.json').read_text())
gate=json.loads((W/'E074_VALIDATED_HUMAN_GATE.json').read_text())
if not all(gate['gates'].values()) or freeze.get('official_rhae') is not None:raise RuntimeError('Unexpected E074 freeze/gate')
modehash={x['mode']:x['sha256'] for x in freeze['models']}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  while b:=f.read(1<<20):h.update(b)
 return h.hexdigest()
policies={}
for mode in ('bc','ddqn','shuffled','no_history'):
 ck=W/'trained_human'/f'history_{mode}.pt'
 if sha(ck)!=modehash[mode]:raise RuntimeError('Checkpoint changed: '+mode)
 policies[mode],payload=load(ck)
 if int(payload['updates'])!=2500 or int(payload['seed'])!=2069:raise RuntimeError('Unfrozen training settings')
arc=arc_agi.Arcade(operation_mode=OperationMode.NORMAL)
SEED=2069; BUDGET=60
runid=os.environ['E074_JOB_ID']
trace=OUT/f'E074_s5i5_native_dev_{runid}.jsonl'
summaryfile=OUT/f'E074_s5i5_native_dev_{runid}.json'
rows=[]
print('E074_NATIVE_SOURCE_FAMILY_ONLY_BEGIN','s5i5','budget',BUDGET,flush=True)
with open(trace,'x') as sink:
 for mode in ('bc','ddqn','shuffled','no_history','random'):
  env=arc.make('s5i5')
  if env is None:raise RuntimeError('Native environment missing')
  f=env.reset()
  calls=1
  levels=max(0,int(f.levels_completed))
  startsig=sha_data=np.asarray(f.frame[-1],dtype=np.uint8).tobytes()
  startsig=hashlib.sha256(startsig).hexdigest()
  clickbins=Counter();actions=Counter();gameovers=0; resets=1; reward_events=0
  rng=random.Random(SEED)
  hist=[coarse(np.asarray(f.frame[-1],dtype=np.uint8))];ah=[];xyhist=[]
  start=time.monotonic()
  while calls<BUDGET and str(f.state.value)!='WIN':
   if str(f.state.value)=='GAME_OVER':
    gameovers+=1
    f=env.reset();calls+=1;resets+=1
    if not f.frame:raise RuntimeError('No reset frame')
    hist=[coarse(np.asarray(f.frame[-1],dtype=np.uint8))];ah=[];xyhist=[]
    continue
   legal=sorted(set(int(x) for x in f.available_actions if int(x)!=0))
   if not legal:
    print('NO_LEGAL_ACTIONS',mode,calls,flush=True);break
   if mode=='random':
    aid=int(rng.choice(legal)); xy=(rng.randrange(64),rng.randrange(64)) if aid==6 else None
    value=None; binidx=None
   else:
    m=len(hist)
    frames=np.zeros((1,4,16,16),dtype=np.uint8)
    acts=np.zeros((1,4),dtype=np.int64)
    locs=np.zeros((1,4,2),dtype=np.float32)
    frames[0,-m:]=np.stack(hist)
    if m>1:
     acts[0,-(m-1):]=np.asarray(ah[-(m-1):],dtype=np.int64)
     locs[0,-(m-1):]=np.asarray(xyhist[-(m-1):],dtype=np.float32)
    with torch.inference_mode():
     q,cl=policies[mode](torch.from_numpy(frames),torch.from_numpy(acts),torch.from_numpy(locs))
    v=q[0].detach().numpy()
    aid=int(max(legal,key=lambda x:(float(v[x]),-x)))
    value=round(float(v[aid]),6)
    binidx=int(cl[0].argmax().item())
    xy=(binidx%16*4+2,binidx//16*4+2) if aid==6 else None
   if aid not in legal:raise RuntimeError('Illegal action was selected')
   action=GameAction.from_id(aid)
   if xy is not None:
    nextframe=env.step(action,data={'x':int(xy[0]),'y':int(xy[1])})
    clickbins[str((xy[1]//4)*16+(xy[0]//4))]+=1
   else:nextframe=env.step(action)
   calls+=1;actions[str(aid)]+=1
   nxt=int(nextframe.levels_completed)
   reward=max(0,nxt-levels);reward_events+=reward;levels=max(levels,nxt)
   state=str(nextframe.state.value)
   line={'mode':mode,'game':'s5i5','seed':SEED,'call_number':calls,'action_id':aid,
    'xy':list(xy) if xy else None,'greedy_q':value,'click_bin':binidx,
    'reward_advancement':reward,'levels_completed':nxt,'state':state,
    'available_actions':legal,'terminal':state in ('WIN','GAME_OVER'),
    'full_reset':bool(getattr(nextframe,'full_reset',False))}
   sink.write(json.dumps(line,separators=(',',':'))+'\n');sink.flush()
   if nextframe.frame:
    z=coarse(np.asarray(nextframe.frame[-1],dtype=np.uint8))
    if line['full_reset']:
     hist=[z];ah=[];xyhist=[]
    else:
     hist.append(z);hist=hist[-4:]
     ah.append(aid);ah=ah[-3:]
     xyhist.append((xy[0]/63.,xy[1]/63.) if xy else (0.,0.));xyhist=xyhist[-3:]
   elif state not in ('WIN','GAME_OVER'):
    raise RuntimeError('Missing nonterminal native frame')
   f=nextframe
  result={'mode':mode,'family':'s5i5','training_family':True,
    'game_initial_sha256':startsig,'policy_seed':SEED,'max_total_calls':BUDGET,
    'total_calls_charged_initial_reset_and_retries':calls,'resets':resets,
    'native_level_advancements':reward_events,'maximum_level_reached':levels,
    'win_levels':int(f.win_levels),'native_win':str(f.state.value)=='WIN',
    'game_over_count':gameovers,'actions':dict(actions),
    'unique_chosen_click_bins':len(clickbins),'elapsed_seconds':round(time.monotonic()-start,3),
    'checkpoint_sha256':modehash.get(mode),
    'official_score':None,'online_weight_updates':0,'heldout_environment_opened':False}
  print('E074_NATIVE_RESULT',json.dumps(result,sort_keys=True),flush=True)
  rows.append(result)
data={'kind':'E074_FROZEN_POLICY_NATIVE_SOURCE5_DEV_PILOT',
 'job_id':runid,'source':str(R),'work':str(W),'trace':str(trace),
 'dataset':str(W/'human_five_training/E068_HUMAN_TRAINING_MANIFEST.json'),
 'training_freeze_sha256':sha(W/'E074_TRAINING_COMPLETE_FREEZE.json'),
 'modes':rows,'same_initial_frame':len(set(r['game_initial_sha256'] for r in rows))==1,
 'test_families_closed':['cn04','lp85','m0r0','r11l','sk48'],
 'official_score':None,'no_online_adaptation':True,
 'interpretation':'This is an in-distribution training-family development pilot, not an ARC heldout score or generalization result.'}
with open(summaryfile,'x') as f:json.dump(data,f,indent=2)
print('E074_NATIVE_PILOT_COMPLETE','summary',summaryfile,'trace',trace,'trace_sha256',sha(trace),flush=True)
PY