#!/usr/bin/env python3
"""E087: online replanning after falsified causal operator preconditions.
Previously explored training-family vc33 only; fixed E075 prefix is an experimental
initialization, NOT an autonomous agent evaluation. The agent reads current
frames and retries alternative legal operations if a predicted transfer fails.
No hidden game state or game source, no new algorithm performance claim yet.
"""
from pathlib import Path
import hashlib,json,logging,os,random,sys
from collections import Counter,defaultdict
import numpy as np
logging.disable(logging.INFO)
sys.path.insert(0,'/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
from src.adapter import ArcSession
from src.e027.reproducibility import install_reproducibility
B=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
D=Path('/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_71855/E083_CONTROLLED_CONTRASTS.json')
def sha(f):return hashlib.sha256(np.asarray(f,dtype=np.int8).tobytes()).hexdigest()
report=json.loads((B/'E075_REPORT.json').read_text())
r=next(z for z in report['rows'] if z['mode']=='repeat')
prefixfile=B/'repeat.jsonl'
assert hashlib.sha256(prefixfile.read_bytes()).hexdigest()==r['trace_sha256']
events=[json.loads(s) for s in prefixfile.read_text().splitlines()]
end=next(i for i,row in enumerate(events) if row['native_level_reward'] and row['progress']>=2)
prefix=events[:end+1]
controls=sorted((z for z in json.loads(D.read_text())['probes']
  if z['label'].startswith('component_color9')),key=lambda z:z['xy'][0])
assert len(controls)==8
idx=[int(z['index']) for z in controls]
COLS=[9,20,31,42,53] # visible centers measured in E085 source-only frame inspection
def heights(frame):
 a=np.asarray(frame,dtype=np.uint8)
 return tuple(int((a[3:58,x]==0).sum()) for x in COLS)
def prepare():
 s=ArcSession();s.start_run('vc33',160,0)
 for i,row in enumerate(prefix):
  if sha(s.obs.frame)!=row['frame_sha_before']:raise RuntimeError('diverged before '+str(i))
  t=s.step(int(row['action_index']))
  if sha(t.next_obs.frame)!=row['frame_sha_after']:raise RuntimeError('diverged after '+str(i))
 assert s.tracker.high_water==2
 return s
def rank(mode,h,blocked,rng):
 n=len(h)
 if mode=='random_buttons':
  possibles=[a for a in idx if a not in blocked]
  rng.shuffle(possibles)
  return possibles
 if mode=='leftward_transport':
  return [idx[2*j] for j in range(n-1) if idx[2*j] not in blocked]
 if mode=='variance_goal_replan':
  mean=sum(h)/n
  old=sum((x-mean)**2 for x in h)
  values=[]
  for j in range(n-1):
   for sign in (1,-1):
    a=idx[2*j+(0 if sign==1 else 1)]
    if a in blocked:continue
    g=list(h);g[j]+=2*sign;g[j+1]-=2*sign
    hypothetical=sum((x-mean)**2 for x in g)
    expected=old-hypothetical
    penalty=4 if min(g)<0 else 0
    values.append((expected-penalty,j,sign,a))
  values.sort(key=lambda x:(-x[0],x[1],-x[2]))
  return [a for _,_,_,a in values]
 raise ValueError(mode)
def run():
 install_reproducibility()
 output=Path('/home-mscluster/astrauss/e087_single_game_replanning')/('E087_vc33_'+os.environ['SLURM_JOB_ID'])
 if output.exists():raise FileExistsError(output)
 output.mkdir(parents=True)
 allresults=[]
 for mode in ('leftward_transport','variance_goal_replan','random_buttons'):
  session=prepare()
  init=heights(session.obs.frame)
  if init!=(4,2,4,6,28):raise RuntimeError('Anchor features do not match E085')
  blocked=defaultdict(set);transitions=Counter()
  visited={init};rng=random.Random(28901)
  trace=[]
  while session.tracker.actions<160 and session.tracker.high_water==2 and not session.done:
   before=heights(session.obs.frame)
   candidates=rank(mode,before,blocked[before],rng)
   if not candidates:
    break
   a=candidates[0]
   if not session.obs.mask[a]:raise RuntimeError('Illegal action mask')
   t=session.step(a)
   after=heights(t.next_obs.frame)
   changed=after!=before
   if not changed:blocked[before].add(a)
   else:transitions[(a,before,after)]+=1;visited.add(after)
   r={'action':int(session.tracker.actions),
       'mode':mode,'xy':[int((a-6)%64),int((a-6)//64)],
       'before':before,'after':after,'effective_transfer':changed,
       'reward':float(t.reward),'level':int(session.tracker.high_water),
       'is_a_causal_lab_prototype':True}
   trace.append(r)
   if session.tracker.actions%12==0 or t.reward>0:
    print('E087_REPLAN_PROGRESS',json.dumps(r),flush=True)
  filepath=output/(mode+'.jsonl')
  with filepath.open('x') as f:
   for x in trace:f.write(json.dumps(x)+'\n')
  result={'mode':mode,'game':'vc33','initial':init,
   'final_heights':heights(session.obs.frame),'initial_completed_levels':2,
   'final_native_levels':int(session.tracker.high_water),
   'new_level_3_achieved':bool(session.tracker.high_water>=3),
   'suffix_actions':len(trace),'causally_effectful_ops':sum(x['effective_transfer'] for x in trace),
   'blocked_ops':sum(not x['effective_transfer'] for x in trace),
   'unique_column_states':len(visited),
   'total_actions_counting_prefix':int(session.tracker.actions),
   'source_trace':str(filepath),'sha256':hashlib.sha256(filepath.read_bytes()).hexdigest(),
   'uses_prior_causal_lab_for_control_sites':True,
   'model_used_only_current_observation_after_entry':True}
  allresults.append(result)
  print('E087_NATIVE_REPLAN_RESULT',json.dumps(result,sort_keys=True),flush=True)
 with (output/'E087_REPLAN_RESULTS.json').open('x') as f:
  json.dump({'kind':'E087_STATEFUL_TRANSFER_REPLANNING_SINGLE_STUDIED_GAME',
   'science_goal':'test whether action precondition monitoring improves beyond static scripts',
   'no_hidden_state':True,'holdout_environments_opened':False,
   'requires_recorded_dev_prefix_not_general_agent':True,
   'rows':allresults},f,indent=2)
 print('E087_COMPLETE',str(output),flush=True)
if __name__=='__main__':run()
