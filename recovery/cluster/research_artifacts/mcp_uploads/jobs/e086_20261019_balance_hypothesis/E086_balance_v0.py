#!/usr/bin/env python3
"""E086 goal-hypothesis falsification on previously explored vc33 ONLY.
All input operations were learned in E084/E085 from native frames, never source.
The recorded 91-action prefix is a diagnostic reset control, NOT autonomous play.
Hypothesis: Level 3 rewards equalizing five conserved black columns.
"""
import hashlib,json,logging,os,sys
from pathlib import Path
import numpy as np
logging.disable(logging.INFO)
sys.path.insert(0,'/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
from src.adapter import ArcSession,N_SIMPLE
from src.e027.reproducibility import install_reproducibility
E075=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
E084=Path('/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_71855/E083_CONTROLLED_CONTRASTS.json')
BASE=json.loads((E075/'E075_REPORT.json').read_text())
REC=next(x for x in BASE['rows'] if x['mode']=='repeat')
source=E075/'repeat.jsonl'
assert hashlib.sha256(source.read_bytes()).hexdigest()==REC['trace_sha256']
data=[json.loads(x) for x in source.read_text().splitlines()]
pos=next(i for i,e in enumerate(data) if e['native_level_reward']>0 and e['progress']>=2)
prefix=data[:pos+1]
def sha(f):return hashlib.sha256(np.asarray(f,dtype=np.int8).tobytes()).hexdigest()
def heights(f,cols):
 z=np.asarray(f,dtype=np.uint8)
 return [int((z[3:58,x]==0).sum()) for x in cols]
def main():
 install_reproducibility()
 prior=json.loads(E084.read_text())
 cols=[9,20,31,42,53]  # measured only from E084 native screenshot, not game code
 ctrls=sorted((x for x in prior['probes'] if x['label'].startswith('component_color9')),key=lambda x:x['xy'][0])
 assert len(ctrls)==8
 left_buttons=[int(ctrls[2*i]['index']) for i in range(4)]
 controls=[x['xy'] for x in ctrls]
 s=ArcSession();s.start_run('vc33',160,0)
 for i,e in enumerate(prefix):
  if sha(s.obs.frame)!=e['frame_sha_before']:raise RuntimeError('Replay diverged pre '+str(i))
  t=s.step(int(e['action_index']))
  if sha(t.next_obs.frame)!=e['frame_sha_after']:raise RuntimeError('Replay diverged post '+str(i))
 initial=heights(s.obs.frame,cols)
 total=sum(initial);n=len(initial)
 assert total==44 and all(v%2==0 for v in initial)
 lower=(total//(2*n))*2
 remainder=(total-n*lower)//2
 target=[lower]*(n-remainder)+[lower+2]*remainder
 assert sum(target)==total
 transfers=[(sum(target[:i+1])-sum(initial[:i+1]))//2 for i in range(n-1)]
 assert all(v>=0 for v in transfers)
 goal_actions=[(j,left_buttons[j]) for j in reversed(range(4)) for k in range(transfers[j])]
 print('E086_FROZEN_BALANCING_PREDICTION',json.dumps({
  'initial':initial,'target':target,'transfers_by_boundary':transfers,
  'actions_planned':len(goal_actions),'measured_controls':controls,
  'num_actions_remaining':160-s.tracker.actions}),flush=True)
 result=[]
 for j,idx in goal_actions:
  if s.done:break
  assert bool(s.obs.mask[idx])
  before=heights(s.obs.frame,cols)
  t=s.step(idx);after=heights(t.next_obs.frame,cols)
  reward=float(t.reward)
  event={'boundary':j,'idx':idx,'xy':[int((idx-N_SIMPLE)%64),int((idx-N_SIMPLE)//64)],
   'before':before,'after':after,'reward':reward,
   'level':int(s.tracker.high_water),'action':int(s.tracker.actions)}
  result.append(event);print('E086_GOAL_HYPOTHESIS_STEP',json.dumps(event),flush=True)
  if s.tracker.high_water>2:break
 final=heights(s.obs.frame,cols)
 out=Path('/home-mscluster/astrauss/e086_single_game_hypotheses')/('E086_balance_'+os.environ['SLURM_JOB_ID'])
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True)
 record={'hypothesis':'min_variance_equilibrium_of_five_adjacent_redistributed_columns',
  'source':'own visual E084 causal interventions',
  'initial_heights':initial,'target':target,'transfer_plan':transfers,
  'final_heights':final,'new_level_3_reached':s.tracker.high_water>=3,
  'final_level':int(s.tracker.high_water),'interventions':len(result),
  'equal_target_reached':final==target,'events':result,
  'recorded_prefix_for_lab_initialization_not_deployed_policy':True,
  'oracle_hidden_state_used':False,'heldout_opened':False}
 with (out/'E086_BALANCE_RESULT.json').open('x') as f:json.dump(record,f,indent=2)
 print('E086_HYPOTHESIS_RESULT',json.dumps({k:v for k,v in record.items() if k!='events'}),flush=True)
if __name__=='__main__':main()
