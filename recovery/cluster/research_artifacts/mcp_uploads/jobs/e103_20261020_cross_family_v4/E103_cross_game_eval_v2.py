#!/usr/bin/env python3
"""E103 preregistered cross-family evaluation of frozen E097.

Predeclared development cross-family tests: bp35, ka59, ls20.
These were outside E097 architecture development but WERE historically studied
elsewhere in the wider project: *not globally pristine or hidden Kaggle games*.
All five E074 prospective source tests remain sealed.
Policy source SHA is frozen; no retraining, tweaking or demonstrations.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,logging,sys,time,traceback,random
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import numpy as np
logging.disable(logging.INFO)

HOME=Path('/home-mscluster/astrauss')
J=HOME/'research_artifacts/mcp_uploads/jobs'
ROOT=HOME/'RL-ARC-AGI-3-Project'
sys.path.insert(0,str(ROOT))
from src.adapter import ArcSession,index_to_action
TEST_GAMES=('bp35','ka59','ls20')
UNOPENED_RESERVE=('cn04','lp85','m0r0','r11l','sk48')
SEEDS=(28901,28902,28903)
MODES=('full','full_from_reset','frozen_repeat','uniform_type_random')
ENV_SEED=0
BUDGET=160
CORE=J/'e097_20261020_clean_ablation_v3/E097_clean_core_v3.py'
CORE_SHA='bd30c53e7abe5b63424aec23b949a685822c4ae3c9d89920ab5ed203c199a279'
E075=J/'e075_20261019_onegame_capability/E075_vc33_capability_v2.py'
E075_SHA='ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for buf in iter(lambda:f.read(1024*1024),b''):h.update(buf)
 return h.hexdigest()
assert sha(CORE)==CORE_SHA
assert sha(E075)==E075_SHA
spec=importlib.util.spec_from_file_location('e097_policy_frozen',CORE)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
spec=importlib.util.spec_from_file_location('e075_reference_frozen',E075)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def digest(frame):return hashlib.sha256(np.asarray(frame,dtype=np.int8).tobytes()).hexdigest()
def run_one(game,seed,mode,work):
 work.mkdir(exist_ok=False,parents=True)
 s=ArcSession()
 first=s.start_run(game,BUDGET,ENV_SEED)
 first_hash=digest(first.frame)
 base=old.Controller('random' if mode=='uniform_type_random' else 'repeat',seed)
 learner=core.OnlineAgent('full',seed)
 learner.reset(0,first.frame)
 previous_stage=int(s.tracker.high_water)
 progress=[];activated=0;total=0;frames=[np.asarray(first.frame,dtype=np.int8).copy()]
 launched=time.monotonic()
 trace=work/'observed_actions.jsonl'
 with trace.open('x') as f:
  while not s.done:
   obs=s.obs;stage=int(s.tracker.high_water)
   # Only original E075 explorer before native Level 2 in 'full'.
   use_baseline=(mode in ('frozen_repeat','uniform_type_random') or
       (mode=='full' and stage<2))
   if use_baseline:
    action,reason,posterior=base.select(obs)
    scene=None
    mechanism='frozen_E075_observation_only'
   else:
    if learner.stage!=stage:learner.reset(stage,obs.frame)
    action,reason,posterior,scene=learner.choose(obs)
    if action is None:
     action,reason,posterior=base.select(obs)
     use_baseline=True
     mechanism='fallback_E075_observation_only'
    else:
     mechanism='E097_frozen_online_bayesian_controller'
   if not bool(obs.mask[action]):raise AssertionError('illegal policy action')
   aid,xy=index_to_action(int(action))
   tr=s.step(int(action))
   if use_baseline:
    evidence=base.observe(tr,action,reason,posterior)
   else:
    evidence=learner.observe(tr.obs.frame,tr.next_obs.frame,action,posterior,scene)
    activated+=1
   total+=1
   if tr.reward>0:
    progress.append({'charged_action':int(s.tracker.actions),
      'native_reward':float(tr.reward),'native_level_high_water':int(s.tracker.high_water)})
   current=np.asarray(tr.next_obs.frame,dtype=np.int8)
   frames.append(current.copy())
   f.write(json.dumps({'charged_action':int(s.tracker.actions),
     'mode':mode,'action_index':int(action),'native_action_id':int(aid),
     'xy':list(xy) if xy is not None else None,
     'action_reason':reason,'action_mechanism':mechanism,
     'native_reward':float(tr.reward),'level_high_water':int(s.tracker.high_water),
     'frame_before_SHA256':digest(tr.obs.frame),'frame_after_SHA256':digest(current),
     'learned_evidence':evidence,'hypothesis':posterior},default=str,sort_keys=True)+'\n')
 # SDK-native charged steps can include an internal reset or bookkeeping
 # operation. Preserve BOTH figures; never fabricate an explicit policy step.
 native_charged=int(s.tracker.actions)
 if total>native_charged or native_charged>BUDGET:
  raise AssertionError('native charge outside expected scorer budget')
 unobserved_charges=native_charged-total
 if unobserved_charges>max(2,int(s.tracker.resets)+1):
  raise AssertionError('too many scorer charges without policy decisions')
 arr=work/'frames.npz'
 with arr.open('xb') as fd:np.savez_compressed(fd,frames=np.stack(frames))
 score=s.scorecard() or {}
 result={'game':game,'seed':seed,'env_seed':ENV_SEED,'mode':mode,
   'budget':BUDGET,'native_levels':int(s.tracker.high_water),
   'game_total_levels':int(s.obs.win_levels),
   'native_sdk_score':float(score.get('score',0.0)),
   'actions_charged':int(s.tracker.actions),
   'explicit_policy_decisions':int(total),
   'sdk_charges_without_explicit_decision':int(unobserved_charges),
   'all_commands_including_reset':int(s.tracker.env_commands),
   'native_level_up_events':progress,'frozen_E097_decisions':activated,
   'frozen_E097_policy_activated':bool(activated),
   'first_frame_SHA256':first_hash,
   'trajectory_SHA256':sha(trace),'frames_SHA256':sha(arr),
   'policy_core_source_SHA256':CORE_SHA,'baseline_source_SHA256':E075_SHA,
   'only_sdk_observation_and_legal_actions_for_decision':True,
   'no_demonstrations_or_precomputed_solutions_loaded':True,
   'historically_exposed_wider_project_family':True,
   'same_game_family_as_E097_architecture_tuning':False,
   'elapsed_seconds':round(time.monotonic()-launched,3),
   'controller_stats':dict(learner.stats),
   'causal_predictions':dict(learner.memory.stats)}
 with (work/'result.json').open('x') as f:json.dump(result,f,indent=2)
 print('E103_CROSS_GAME_RESULT',json.dumps(result,sort_keys=True),flush=True)
 return result

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--out',required=True)
 a=parser.parse_args()
 from src.e027.reproducibility import install_reproducibility
 import torch
 torch.set_num_threads(1)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 install_reproducibility()
 output=Path(a.out)
 if output.exists():raise FileExistsError('Never overwrite prior evaluation '+str(output))
 output.mkdir(parents=True)
 # Written, exclusively, BEFORE instantiating ANY of the evaluation games.
 protocol={'experiment':'E103_FROZEN_CROSS_FAMILY_GENERALIZATION_CHECK',
  'date_utc':datetime.now(timezone.utc).isoformat(),
  'test_families':list(TEST_GAMES),'reserved_unopened':list(UNOPENED_RESERVE),
  'design_game':'vc33','source_training_families':['sb26','s5i5','lf52','tn36','g50t'],
  'literature_condition':'historically studied in wider project; held out from E097',
  'policy_seeds':list(SEEDS),'env_seed':ENV_SEED,'native_action_budget':BUDGET,
  'modes':list(MODES),'source_sha256':{'frozen_E097':CORE_SHA,'E075':E075_SHA,
   'E103_runner':sha(Path(__file__))},
  'no_policy_tuning_after_evaluation':True,'no_heldout_game_source_access':True,
  'preserve_E074_BC_training_firewall':True,
  'NOT_unseen_in_wider_project':True,'NOT_official_private_kaggle_score':True}
 with (output/'PREREGISTRATION_BEFORE_ANY_TEST_FRAME.json').open('x') as f:json.dump(protocol,f,indent=2)
 print('E103_PROTOCOL_FROZEN_BEFORE_GAME_START',json.dumps(protocol,sort_keys=True),flush=True)
 results=[]
 for game in TEST_GAMES:
  for seed in SEEDS:
   paired=[]
   for mode in MODES:
    path=output/game/str(seed)/mode
    print('E103_START_EVALUATION',game,seed,mode,flush=True)
    try:
     r=run_one(game,seed,mode,path)
     results.append(r);paired.append(r)
    except Exception as e:
     # NO silent pruning of hard games or failed controls.
     err={'game':game,'seed':seed,'mode':mode,'error_class':type(e).__name__,
      'error_message':str(e),'traceback':traceback.format_exc()}
     results.append(err)
     print('E103_FAILURE_PRESERVED',json.dumps(err,sort_keys=True),flush=True)
   good=[r for r in paired if 'native_levels' in r]
   if len(good)==len(MODES):
    if len(set(x['first_frame_SHA256'] for x in good))!=1:
     raise AssertionError('paired arms received different initial frames')
 summary={'experiment':'E103_FROZEN_CROSS_GAME_SDK_EVALUATION',
  'preregistration':protocol,'results':results,
  'number_of_games':len(TEST_GAMES),'policy_seeds':len(SEEDS),
  'expected_trials':len(TEST_GAMES)*len(SEEDS)*len(MODES),
  'completed_trials':sum('native_levels' in x for x in results),
  'errored_trials':sum('error_class' in x for x in results),
  'reserve_games_still_unopened':list(UNOPENED_RESERVE),
  'E097_algorithm_modified_for_test':False,
  'test_runner_modified_for_game_interface_and_initial_policy_switch_only':True,
  'full_from_reset_is_new_evaluation_condition_not_E097_training_configuration':True,
  'not_proof_of_globally_unseen_generalization':True}
 with (output/'E103_ALL_GAME_RESULTS.json').open('x') as f:json.dump(summary,f,indent=2)
 print('E103_ALL_UNSEEN_CHECKS_COMPLETE',json.dumps({
  'results_file':str(output/'E103_ALL_GAME_RESULTS.json'),
  'trial_summary':[(x['game'],x['seed'],x['mode'],x.get('native_levels','ERROR'),
      x.get('frozen_E097_decisions',0)) for x in results],
  'completed_trials':summary['completed_trials'],'errored_trials':summary['errored_trials']
 },sort_keys=True),flush=True)
if __name__=='__main__':main()
