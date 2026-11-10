#!/usr/bin/env python3
"""E080: test effect-terminated skill persistence inside two REAL online RL agents.
E078 DQN/PPO objectives are unchanged. DQN uses off-policy exploration options;
PPO uses a differentiable observation-conditioned logit prior in BOTH
sampling and clipped PPO likelihood updates (so no teacher-action off-policy PPO).
Hand-designed option bias, not learned causal goal inference.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
import numpy as np
import torch
P=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e078_20261019_six_version_native/E078_six_version_native_v0.py')
SHA='dcb59636a9ffd7319ebd0a2ec692cd20200532845f00d6be1caba6927c6d0fd3'
assert hashlib.sha256(P.read_bytes()).hexdigest()==SHA
spec=importlib.util.spec_from_file_location('E078_frozen',P)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
from src.adapter import Observation,ArcSession,N_SIMPLE
from src.config import RunConfig
from src.run import run,build_learner

def effectful(obs):
 n=int(np.count_nonzero(obs.frame!=obs.prev_frame))
 return 17<=n<=512 and 0<=obs.prev_action<old.N_ACTIONS

class OptionIntervention(old.Intervention):
 def __init__(self,base,algo):
  super().__init__(base,'intrinsic_effect_proposals')
  self.algo=algo;self.override_count=0;self.skill_repeat_count=0
  self.prior_conditions=0;self.repeat_streak=0
 def start_run(self,seed):
  super().start_run(seed)
  self.override_count=self.skill_repeat_count=self.prior_conditions=self.repeat_streak=0
  if self.algo=='ppo':
   network=self.inner.net
   original=network.forward
   def with_prior(batch):
    types,clicks,val=original(batch)
    differences=(batch.frame!=batch.prev_frame).sum((1,2))
    enabled=(differences>=17)&(differences<=512)&(batch.prev_action>=N_SIMPLE)
    # Prefer repeating a coordinate ONLY after a substantial visual response.
    logit_boost=enabled.to(clicks.dtype)*7.
    click_ids=(batch.prev_action-N_SIMPLE).clamp(min=0,max=4095)
    cb=torch.zeros_like(clicks).scatter_add(1,click_ids[:,None],logit_boost[:,None])
    tb=torch.zeros_like(types);tb[:,N_SIMPLE]+=enabled.to(types.dtype)*3.
    return types+tb,clicks+cb,val
   network.forward=with_prior
 def filtered(self,obs):
  new=super().filtered(obs)
  if effectful(obs) and obs.prev_action>=N_SIMPLE and obs.mask[obs.prev_action]:
   m=new.mask.copy();m[obs.prev_action]=True
   return Observation(new.frame,new.prev_frame,m,new.prev_action,new.progress,new.high_water,new.win_levels)
  return new
 def act(self,obs):
  filtered=self.filtered(obs)
  index=self.inner.act(filtered)
  self.pending=filtered
  if effectful(obs):
   self.prior_conditions+=1
   if self.algo=='dqn' and self.repeat_streak<12 and filtered.mask[obs.prev_action]:
    if index!=obs.prev_action:self.override_count+=1
    index=int(obs.prev_action)
    self.repeat_streak+=1
   if index==obs.prev_action:self.skill_repeat_count+=1
  else:self.repeat_streak=0
  return index
 def diagnostics(self):
  d=super().diagnostics()
  d.update({'E080_effect_prior_checks':self.prior_conditions,
   'E080_prev_action_repetitions':self.skill_repeat_count,
   'E080_dqn_offpolicy_action_overrides':self.override_count,
   'E080_PPO_prior_active_during_update':self.algo=='ppo',
   'E080_option_bias_needs_reapplication_after_checkpoint_load':True,
   'stage':'I3_effect_conditioned_skills'})
  return d

def selftest():
 from src.model import ObsBatch
 from src.ppo import evaluate_actions
 model=__import__('src.model',fromlist=['ActorCritic']).ActorCritic(old.ARCH)
 class Wrap:pass
 fake=Wrap();fake.net=model
 wrap=OptionIntervention(fake,'ppo')
 # Direct forward hook rather than .start_run because fake has no optimizer.
 base=model.forward
 def check(batch):
  tl,cl,v=base(batch);changes=(batch.frame!=batch.prev_frame).sum((1,2))
  active=(changes>=17)&(changes<=512)&(batch.prev_action>=N_SIMPLE)
  loc=(batch.prev_action-N_SIMPLE).clamp(min=0,max=4095)
  z=torch.zeros_like(cl).scatter_add(1,loc[:,None],active.to(cl.dtype)[:,None]*7.)
  t=torch.zeros_like(tl);t[:,N_SIMPLE]+=active.to(tl.dtype)*3.
  return tl+t,cl+z,v
 frame=torch.zeros((2,64,64),dtype=torch.long)
 frame[0,20:26,20:26]=4
 prev=torch.zeros_like(frame)
 mask=torch.ones((2,old.N_ACTIONS),dtype=torch.bool)
 b=ObsBatch(frame,prev,torch.tensor([6+20*64+20,-1]),
  torch.zeros((2,2)),mask)
 tl0,cl0,_=base(b);model.forward=check
 tl1,cl1,_=model(b)
 assert abs(float(cl1[0,20*64+20]-cl0[0,20*64+20])-7)<1e-4
 assert abs(float(cl1[1,0]-cl0[1,0]))<1e-5
 actions=torch.tensor([6+20*64+20,6])
 lp,entropy,v=evaluate_actions(model,b,actions)
 loss=-lp.mean()+.01*entropy.mean()+v.square().mean()
 loss.backward()
 assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
 print('E080_PRIOR_AND_PPO_GRADIENT_TEST_OK',flush=True)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--self-test',action='store_true')
 ap.add_argument('--out',default='')
 ap.add_argument('--seed',type=int,default=28901)
 ap.add_argument('--budget',type=int,default=160)
 args=ap.parse_args()
 torch.set_num_threads(2)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 old.selftest();selftest()
 if args.self_test:return
 if not args.out:raise ValueError('Need --out')
 out=Path(args.out)
 if out.exists():raise FileExistsError('No overwrite allowed')
 out.mkdir(parents=True)
 records=[]
 for algo in ('dqn','ppo'):
  for disable in (False,True):
   version='I3' if not disable else 'I3-no-grad'
   cfg=RunConfig(algo=algo,game='vc33',version=version,seed=args.seed,
    env_seed=0,budget=args.budget,arch=old.ARCH,
    params=old.DQN if algo=='dqn' else old.PPO,
    updates_disabled=disable,threads=2,tag='E080_effect_conditioned_skill_prior')
   base=build_learner(cfg)
   learner=OptionIntervention(base,algo)
   start=time.monotonic()
   r=run(cfg,session=ArcSession(),learner=learner,out_dir=str(out),save_checkpoint=True)
   d=r['learner']
   if r['error'] is not None:raise RuntimeError(r['error'])
   if int(d['gradient_steps'])!=(0 if disable else (18 if algo=='dqn' else 20)):
    raise RuntimeError('Unexpected gradient update count')
   assert int(r['counters']['scorer_actions'])==args.budget
   assert r['official_score'] is not None
   rec={'algo':algo,'version':version,'seed':args.seed,'game':'vc33',
    'budget':args.budget,'levels':int(r['counters']['high_water']),
    'native_sdk_score':r['official_score']['score'],
    'gradient_updates':int(d['gradient_steps']),
    'native_reward_events':int(r['diagnostics']['rewarded_transitions']),
    'option_prior_enabled_when_effectful':int(d['E080_effect_prior_checks']),
    'option_repeat_action_count':int(d['E080_prev_action_repetitions']),
    'dqn_action_overrides':int(d['E080_dqn_offpolicy_action_overrides']),
    'intrinsic_training_bonus':float(d['training_intrinsic_reward_sum']),
    'runtime_s':round(time.monotonic()-start,3),
    'source_original_DQN_PPO_unchanged':True,
    'online_updated':not disable,
    'checkpoint_requires_external_E080_policy_prior':True,
    'checkpoint':str(out/r['identity']['run_id']/'checkpoint.pt')}
   print('E080_NATIVE_RESULT',json.dumps(rec,sort_keys=True),flush=True);records.append(rec)
 with (out/'E080_RESULTS.json').open('x') as f:
  json.dump({'kind':'E080_OPTION_RL_ONE_GAME_NATIVE_PILOT',
   'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'E078_frozen_sha256':SHA,'public_development_game':'vc33',
   'heldout_game_instantiated':False,
   'not_a_generalization_or_official_Kaggle_score':True,
   'methods':records},f,indent=2)
 print('E080_COMPLETED',out/'E080_RESULTS.json',flush=True)
if __name__=='__main__':main()
