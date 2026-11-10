#!/usr/bin/env python3
"""E097 independent from-reset native comparison, fixed development vc33 only.
No recorded prefix, checkpoint loading, game source or privileged state.
All policy learning is within its current episode. The learned inverse/forward
models are lightweight Bayesian feature tables, NOT neural RL weights.
"""
import argparse,hashlib,importlib.util,json,logging,sys,time
from pathlib import Path
from collections import Counter
import numpy as np
logging.disable(logging.INFO)
ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
sys.path.insert(0,str(ROOT))
from src.adapter import ArcSession,index_to_action
C=Path(__file__).with_name('E097_clean_core_v3.py')
CORE_SHA='bd30c53e7abe5b63424aec23b949a685822c4ae3c9d89920ab5ed203c199a279'
assert hashlib.sha256(C.read_bytes()).hexdigest()==CORE_SHA
spec=importlib.util.spec_from_file_location('e093_core_fixed',C)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
E075=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e075_20261019_onegame_capability/E075_vc33_capability_v2.py')
OLD_SHA='ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7'
assert hashlib.sha256(E075.read_bytes()).hexdigest()==OLD_SHA
spec=importlib.util.spec_from_file_location('e075_prior_controller',E075)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
MODES=('full','no_memory','no_causal','no_goal','frozen_repeat')
def digest(frame):return hashlib.sha256(np.asarray(frame,dtype=np.int8).tobytes()).hexdigest()
def experiment(mode,seed,budget,env_seed,dest):
 arc=ArcSession()
 first=arc.start_run('vc33',budget,env_seed)
 frozen=old.Controller('repeat',seed)
 agent=core.OnlineAgent(mode,seed)
 agent.reset(0,first.frame)
 initial=digest(first.frame)
 log=dest/(mode+'.jsonl')
 history=[np.asarray(first.frame,dtype=np.int8).copy()]
 levels=[];checks=Counter();stage2_prefix=[]
 start=time.monotonic()
 with log.open('x') as fp:
  while not arc.done:
   obs=arc.obs
   current=int(arc.tracker.high_water)
   if mode=='frozen_repeat' or current<2:
    idx,reason,hyp=frozen.select(obs);sc=None
    method='frozen_E075_from_observation'
   else:
    if agent.stage!=current:agent.reset(current,obs.frame)
    idx,reason,hyp,sc=agent.choose(obs)
    method='online_hypothesis_experiment_plan'
    if idx is None:
     idx,_,_=frozen.select(obs);reason='fallback_e075_legal_probe'
   if not bool(obs.mask[idx]):raise RuntimeError('Emitted illegal action')
   act,xy=index_to_action(int(idx))
   tr=arc.step(int(idx))
   if method=='frozen_E075_from_observation' or idx is None:
    evidence=frozen.observe(tr,idx,reason,hyp)
   else:
    evidence=agent.observe(tr.obs.frame,tr.next_obs.frame,idx,hyp,sc)
   if current<2:
    stage2_prefix.append((idx,digest(tr.next_obs.frame)))
   if tr.reward>0:
    levels.append({'action':int(arc.tracker.actions),
      'reward':float(tr.reward),'high_water':int(arc.tracker.high_water)})
   history.append(np.asarray(tr.next_obs.frame,dtype=np.int8).copy())
   row={'mode':mode,'action':int(arc.tracker.actions),'idx':int(idx),
     'type':int(act),'xy':list(xy) if xy is not None else None,
     'reason':reason,'reward':float(tr.reward),
     'high_water':int(arc.tracker.high_water),'before':digest(tr.obs.frame),
     'after':digest(tr.next_obs.frame),'predicted_hypothesis':hyp,
     'new_evidence':evidence,'stage_of_policy_decision':current,
     'action_source':method}
   fp.write(json.dumps(row,default=str)+'\n')
 frames=dest/(mode+'_frames.npz')
 with frames.open('xb') as f:np.savez_compressed(f,frames=np.stack(history))
 card=arc.scorecard() or {}
 data={'mode':mode,'seed':seed,'env_seed':env_seed,'native_game':'vc33',
  'budget':budget,'scorer_actions':int(arc.tracker.actions),
  'environment_commands':int(arc.tracker.env_commands),
  'native_levels_completed':int(arc.tracker.high_water),
  'win_levels':int(arc.obs.win_levels),
  'official_native_game_score':float(card.get('score',0.0)),
  'native_progress':levels,'started_frame_sha256':initial,
  'pre_level2_prefix_SHA256':hashlib.sha256(json.dumps(stage2_prefix).encode()).hexdigest(),
  'autonomous_legal_actuator':True,'recorded_trajectories_loaded':False,
  'teacher_or_hidden_game_state_used':False,'original_E075_code_unchanged':True,
  'online_gradient_updates':0,'model_is_online_Bayesian_tabular_not_neural':True,
  'agent_stats':dict(agent.stats),'forward_inverse_stats':dict(agent.memory.stats),
  'frozen_explorer_stats':dict(frozen.count),
  'seconds':round(time.monotonic()-start,3),
  'trace_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
  'frames_sha256':hashlib.sha256(frames.read_bytes()).hexdigest()}
 print('E097_NATIVE_MODE_RESULT',json.dumps(data,sort_keys=True),flush=True)
 return data

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--self-test',action='store_true')
 p.add_argument('--mode',nargs='+',choices=MODES,default=list(MODES))
 p.add_argument('--seed',type=int,default=28901)
 p.add_argument('--env-seed',type=int,default=0)
 p.add_argument('--budget',type=int,default=160)
 p.add_argument('--out',default='')
 args=p.parse_args()
 core.selftest()
 if args.self_test:return
 if not args.out:raise ValueError('--out required')
 import torch
 from src.e027.reproducibility import install_reproducibility
 torch.set_num_threads(1)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 install_reproducibility()
 out=Path(args.out)
 if out.exists():raise FileExistsError('No overwriting output '+str(out))
 out.mkdir(parents=True)
 rows=[experiment(mode,args.seed,args.budget,args.env_seed,out) for mode in args.mode]
 assert len(set(x['started_frame_sha256'] for x in rows))==1
 # Before Stage 3 all policies use the same frozen E075 source and policy RNG.
 assert len(set(x['pre_level2_prefix_SHA256'] for x in rows))==1
 report={'kind':'E097_FROM_RESET_ONLINE_HYPOTHESES_AND_ABLATIONS',
  'game':'vc33','historically_exposed_development_only':True,
  'authoritative_initial_state_identical':True,
  'identical_exploration_until_stage3':True,
  'E097_core_sha256':CORE_SHA,'E075_frozen_source_sha256':OLD_SHA,
  'E097_runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  'no_external_demo_or_operator_table_loaded':True,
  'not_neural_training_or_unseen_game_generalization':True,
  'policy_seed':args.seed,'env_seed':args.env_seed,'budget':args.budget,
  'rows':rows}
 with (out/'E097_REPORT.json').open('x') as f:json.dump(report,f,indent=2)
 print('E097_EXPERIMENT_COMPLETED',str(out/'E097_REPORT.json'),flush=True)
if __name__=='__main__':main()
