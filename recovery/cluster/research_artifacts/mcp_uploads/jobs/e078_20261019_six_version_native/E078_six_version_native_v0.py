#!/usr/bin/env python3
"""E078 course evidence: TWO trained methods, stage-wise substantive improvements.
Original Wits src.dqn.DQN and src.ppo.PPO code is imported unchanged.
I1: novelty-weighted, region-local visual effect intrinsic reward in learner updates.
I2: I1 + observation-derived legal click proposal masking.
Evaluation/scorecards remain native and untouched; adaptation is ONLINE within a run.
Single historically exposed development game vc33, never touch reserved heldouts.
"""
from __future__ import annotations
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from collections import Counter
import numpy as np
ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
sys.path.insert(0,str(ROOT))
from src.adapter import Observation,Transition,N_SIMPLE,N_ACTIONS,ArcSession
from src.config import RunConfig
from src.run import run,build_learner
from src.learner import RandomPolicy
import torch
OLD=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e075_20261019_onegame_capability/E075_vc33_capability_v2.py')
OLD_SHA='ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7'
if hashlib.sha256(OLD.read_bytes()).hexdigest()!=OLD_SHA:raise RuntimeError('E075 frozen candidate source changed')
import importlib.util
spec=importlib.util.spec_from_file_location('frozen_e075',OLD)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
ALGOS=('dqn','ppo')
GAMES=('vc33',)
STAGES=('baseline','intrinsic_effect','intrinsic_effect_proposals')
DQN={'lr':5e-4,'gamma':.98,'batch':8,'replay_capacity':256,
 'warmup':16,'train_every':8,'target_update':48,'eps_start':.85,'eps_end':.12,
 'eps_decay_actions':160,'huber_delta':1.,'double':True,'grad_clip':10.}
PPO={'rollout':16,'epochs':1,'minibatches':2,'lr':5e-4,'gamma':.98,
 'gae_lambda':.95,'ent_coef':.003,'vf_coef':.5,'clip':.2,'grad_clip':.5}
ARCH={'id':'onehotcnn_stack2','channels':8,'context_dim':48}
def digest(f):
 return hashlib.sha256(np.asarray(f,dtype=np.int8).tobytes()).hexdigest()
def proposal_mask(obs):
 mask=np.zeros(N_ACTIONS,dtype=bool)
 mask[:N_SIMPLE]=obs.mask[:N_SIMPLE]
 proposals=old.candidate_points(obs.frame,limit=140)
 for x,y in proposals:
  a=N_SIMPLE+y*64+x
  if obs.mask[a]:mask[a]=True
 if not mask.any():mask=obs.mask.copy()
 if np.any(mask &~obs.mask):raise RuntimeError('nonlegal action candidate')
 return mask
def locality_signature(before,after):
 a=np.asarray(before,dtype=np.int8)
 b=np.asarray(after,dtype=np.int8)
 diff=(a!=b)
 n=int(diff.sum())
 # A single-pixel background animation is NOT evidence for actionable progress.
 if n<8 or n>512:return None,n
 coords=np.argwhere(diff)
 ym=int(np.median(coords[:,0]))//8
 xm=int(np.median(coords[:,1]))//8
 return (xm,ym,min(12,n//12)),n
class Intervention:
 def __init__(self,inner,stage):
  self.inner,self.stage=inner,stage
  self.pending=None;self.seen=Counter()
  self.bonus=0.;self.shaped_steps=0;self.novel_events=0
  self.candidate_count=Counter()
  self.state_change_count=0
 def start_run(self,seed):
  self.pending=None;self.seen.clear()
  self.bonus=0.;self.shaped_steps=0;self.novel_events=0
  self.candidate_count.clear();self.state_change_count=0
  self.inner.start_run(seed)
 def filtered(self,o):
  if self.stage!='intrinsic_effect_proposals':return o
  m=proposal_mask(o)
  self.candidate_count[int(m[N_SIMPLE:].sum())]+=1
  return Observation(o.frame,o.prev_frame,m,o.prev_action,o.progress,o.high_water,o.win_levels)
 def act(self,o):
  v=self.filtered(o)
  idx=self.inner.act(v)
  if not v.mask[idx]:raise RuntimeError('learner selected illegal or masked-out action')
  self.pending=v
  return idx
 def observe(self,t):
  if self.pending is None:raise RuntimeError('missing actor observation')
  intrinsic=0.
  if self.stage!='baseline':
   signature,n=locality_signature(t.obs.frame,t.next_obs.frame)
   if signature is not None:
    self.state_change_count+=1
    self.seen[signature]+=1
    if self.seen[signature]==1:
     intrinsic=.04
     self.novel_events+=1
    else:intrinsic=.005
  self.bonus+=intrinsic;self.shaped_steps+=int(intrinsic>0)
  filt_next=self.filtered(t.next_obs)
  train_t=Transition(self.pending,t.action,float(t.reward+intrinsic),
   filt_next,t.terminal,t.truncated,dict(t.info))
  self.inner.observe(train_t)
  self.pending=None
 def finish(self,obs):
  self.inner.finish(self.filtered(obs) if obs is not None else None)
 def diagnostics(self):
  d=self.inner.diagnostics()
  d.update({'training_intrinsic_reward_sum':round(self.bonus,5),
    'novel_local_effect_signatures':self.novel_events,
    'qualifying_nontrivial_changes':self.state_change_count,
    'intrinsic_reward_steps':self.shaped_steps,
    'proposal_click_bin_counts':dict(self.candidate_count),
    'stage':self.stage,'native_reward_modified':False})
  return d
 def model_info(self):return self.inner.model_info()
 def state_dict(self):return self.inner.state_dict()
 def load_state_dict(self,state):self.inner.load_state_dict(state)
def selftest():
 m=np.zeros(N_ACTIONS,dtype=bool)
 m[0]=True;m[N_SIMPLE:]=True
 a=np.zeros((64,64),dtype=np.int8);a[10:18,30:35]=4
 o=Observation(a,a,m,-1,0,0,7)
 filtered=proposal_mask(o)
 assert filtered.any() and not np.any(filtered &~m)
 assert 0<int(filtered[N_SIMPLE:].sum())<=140
 b=a.copy();b[10:18,30:35]=0
 signature,n=locality_signature(a,b)
 assert n==40 and signature is not None
 drift=b.copy();drift[0,0]=7
 assert locality_signature(b,drift)[0] is None
 class Fake:
  def start_run(self,seed):pass
  def act(self,x):return 0
  def observe(self,t):self.t=t
  def finish(self,x):pass
  def diagnostics(self):return {'gradient_steps':1}
  def model_info(self):return {}
  def state_dict(self):return {}
 ab=Fake();pol=Intervention(ab,'intrinsic_effect_proposals')
 pol.start_run(28901);idx=pol.act(o)
 nxt=Observation(b,a,m,idx,0,0,7)
 raw=Transition(o,idx,0.,nxt,False,False,{})
 pol.observe(raw)
 assert pol.bonus>0 and raw.reward==0 and ab.t.reward>0
 assert ab.t.obs.mask.sum()<m.sum()
 print('E078_UNIT_PASSED',{'proposals':int(filtered.sum()),'test_bonus':ab.t.reward},flush=True)
def do_run(algo,stage,seed,budget,dir,disabled=False):
 params=DQN if algo=='dqn' else PPO
 label={'baseline':'V0','intrinsic_effect':'I1','intrinsic_effect_proposals':'I2'}[stage]
 if disabled:label+='-no-grad'
 cfg=RunConfig(algo=algo,game='vc33',version=label,seed=seed,
  env_seed=0,budget=budget,arch=ARCH,params=params,
  updates_disabled=disabled,threads=2,tag='E078_course_online_onegame_'+stage)
 inner=build_learner(cfg)
 policy=Intervention(inner,stage)
 t0=time.monotonic()
 r=run(cfg,session=ArcSession(),learner=policy,out_dir=str(dir),save_checkpoint=True)
 diag=r['learner'];levels=r['counters']['high_water']
 completed=bool(r['status']!='error' and r['error'] is None)
 if not completed:raise RuntimeError(f'{algo}/{stage}: {r["error"]} status={r["status"]}')
 grads=int(diag.get('gradient_steps',0))
 if disabled and grads:raise RuntimeError('Disabled update produced grads')
 if not disabled and grads==0:raise RuntimeError('No learner optimizer steps')
 row={'algo':algo,'stage':stage,'disabled_gradient':disabled,'seed':seed,
  'game':'vc33','env_seed':0,'budget':budget,'status':r['status'],
  'scorer_actions':r['counters']['scorer_actions'],
  'environment_commands':r['counters']['env_commands'],
  'reset_count':r['counters']['resets'],'native_levels':levels,
  'official_sdk_score':(r['official_score'] or {}).get('score'),
  'official_sdk_version':(r['official_score'] or {}).get('arc_agi_version'),
  'gradient_steps':grads,'rollout_events':diag.get('rollout_update_events',0),
  'native_rewarded_transitions':r['diagnostics']['rewarded_transitions'],
  'intrinsic_reward_sum':diag['training_intrinsic_reward_sum'],
  'novel_effect_signatures':diag['novel_local_effect_signatures'],
  'click_candidate_mask_histogram':diag['proposal_click_bin_counts'],
  'duration_s':round(time.monotonic()-t0,3),
  'checkpoint_path':str(dir/r['identity']['run_id']/'checkpoint.pt'),
  'run_id':r['identity']['run_id'],
  'config_sha':r['identity']['config_hash'],
  'architecture_parameters':r['identity']['model_info'].get('parameters'),
  'game_history_reused_between_runs':False,'unseen_game_claimed':False,
  'online_learning_during_scored_dev_run':not disabled,
  'human_demonstrations_used':False,'privileged_state_used':False}
 print('E078_NATIVE_RESULT',json.dumps(row,sort_keys=True),flush=True)
 return row
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--self-test',action='store_true')
 p.add_argument('--seed',type=int,default=28901)
 p.add_argument('--budget',type=int,default=160)
 p.add_argument('--out')
 p.add_argument('--full-controls',action='store_true')
 args=p.parse_args()
 selftest()
 if args.self_test:return
 if not args.out:raise ValueError('--out mandatory')
 torch.set_num_threads(2)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 out=Path(args.out)
 if out.exists():raise FileExistsError('No overwriting E078 comparison directory')
 out.mkdir(parents=True)
 rows=[]
 for algo in ALGOS:
  for stage in STAGES:
   rows.append(do_run(algo,stage,args.seed,args.budget,out))
  if args.full_controls:
   rows.append(do_run(algo,STAGES[-1],args.seed,args.budget,out,True))
 config={'kind':'E078_SIX_VERSION_NATIVE_ONE_GAME_ONLINE_RL_STAGING',
  'original_unmodified_learning_implementations':{'dqn':'src/dqn.py','ppo':'src/ppo.py'},
  'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
  'frozen_E075_evidence_source_sha256':OLD_SHA,
  'arc_environment':'vc33','exposed_development_game_only':True,'seed':args.seed,
  'budget':args.budget,'same_game_and_native_scorecard':True,
  'online_intra_run_training':True,'trained_ppo_and_dqn':True,
  'improvements':{'I1':'reward from newly observed local visual effects; original scores unshaped',
   'I2':'I1 plus connected-component click candidate masking based solely on observation'},
  'native_rl_conclusion_requires_multiple_seeds':True,
  'heldout_gamelist_closed':['cn04','lp85','m0r0','r11l','sk48'],
  'rows':rows}
 with (out/'E078_REPORT.json').open('x') as f:json.dump(config,f,indent=2)
 print('E078_SIX_VERSION_FROZEN',out/'E078_REPORT.json',flush=True)
if __name__=='__main__':main()
