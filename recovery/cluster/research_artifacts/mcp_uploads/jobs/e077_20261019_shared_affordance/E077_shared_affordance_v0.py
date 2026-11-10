#!/usr/bin/env python3
"""E077: one-game visual affordance transfer vs fixed causal and repeat controls.
Hand-designed objective-blind experiment, not a trained RL algorithm."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
P=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e076_20261019_causal_options_v1/E076_causal_options_v1.py')
assert hashlib.sha256(P.read_bytes()).hexdigest()=='8b0f0b4873e39d103fcb3754e04f82b42d4f279df3d586b3625ec797131166b4'
spec=importlib.util.spec_from_file_location('e076_frozen',P)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
Old=e.CausalController
class Shared(Old):
 def __init__(self,mode,seed):
  super().__init__(mode,seed)
  self.group=defaultdict(lambda:[0,0])
  self.pairs=defaultdict(Counter);self.samples=Counter()
  self.pending=None
 def role(self,obs,idx):
  if idx<e.N_SIMPLE:return ('primitive',int(idx))
  y,x=divmod(int(idx-e.N_SIMPLE),64);z=np.asarray(obs.frame,dtype=np.uint8)
  p=z[max(0,y-2):y+3,max(0,x-2):x+3]
  a=np.bincount(p.ravel(),minlength=16)
  center=int(z[y,x]);dominant=int(a.argmax())
  v=int(np.count_nonzero(p[:,1:]!=p[:,:-1])) if p.shape[1]>1 else 0
  h=int(np.count_nonzero(p[1:]!=p[:-1])) if p.shape[0]>1 else 0
  return (center,dominant,min(4,len(np.flatnonzero(a))),min(5,v//3),min(5,h//3))
 def choose(self,obs):
  if self.mode!='shared_affordance':return super().choose(obs)
  pts=e.object_candidates(obs)
  if self.active is not None and self.active in pts and self.streak<3:
   idx=self.active;known=self.evidence[self.key(idx)]['events']
   pred=known.most_common(1)[0][0] if known else None
   self.pending=(self.role(obs,idx),None)
   self.counter['option_repeat']+=1
   return idx,'option_retest',pred
  pool=list(pts);self.rng.shuffle(pool)
  def score(idx):
   role=self.role(obs,idx);yes,no=self.group[role]
   v=self.tries[self.key(idx)];p=(yes+1)/(yes+no+2)
   return 1.4/(1+v)+.55*pts[idx][0]+(p if yes and not v else 0)+.06*self.rng.random()
  idx=max(pool,key=score)
  role=self.role(obs,idx);prev=self.pairs[role]
  pred=prev.most_common(1)[0][0] if prev else None
  self.pending=(role,pred)
  if self.group[role][0]>0 and not self.tries[self.key(idx)]:
   self.counter['shared_transfer_probes']+=1
  self.counter['new_probe']+=1
  return idx,'transfer_hypothesis',None
 def observe(self,before,after,idx,why,pred,reward,levelchanged):
  if self.mode!='shared_affordance':return super().observe(before,after,idx,why,pred,reward,levelchanged)
  if self.pending is None:raise AssertionError('No pre-action predicted hypothesis')
  role,pair=self.pending
  event=super().observe(before,after,idx,why,pred,reward,levelchanged)
  site=self.key(idx)
  if self.samples[(site,role)]<3:
   self.group[role][0 if event['effect'] else 1]+=1
   if event['signature']:
    s=event['signature'];self.pairs[role][(s[0],s[1])]+=1
   self.samples[(site,role)]+=1
  if pair is not None:
   self.counter['shared_predictions_tested']+=1
   s=event['signature'];actual=(s[0],s[1]) if s else None
   self.counter['shared_predictions_verified' if actual==pair else 'shared_predictions_falsified']+=1
  if why=='option_retest':
   self.streak+=1
   if not event['effect'] or (pred is not None and event['signature']!=pred) or self.streak>=3:
    self.active=None;self.streak=0;self.counter['options_stopped']+=1
  elif event['effect'] and why=='transfer_hypothesis':
   self.active=idx;self.streak=0;self.counter['options_started']+=1
  if reward or levelchanged:self.active=None;self.streak=0
  self.counter['shared_classes_observed']=len(self.group)
  self.pending=None
  return {**event,'role_pre_action':role,'predicted_pair_pre_action':pair}
e.MODES=('frozen_repeat','causal_option','shared_affordance')
e.CausalController=Shared
def main():
 p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true')
 p.add_argument('--out');p.add_argument('--seed',type=int,default=28901)
 p.add_argument('--env-seed',type=int,default=0);p.add_argument('--budget',type=int,default=160)
 args=p.parse_args()
 e.selftest()
 test=np.zeros((64,64),dtype=np.uint8);test[12:17,13:16]=4
 class Dummy:pass
 o=Dummy();o.frame=test;o.mask=np.zeros(e.N_ACTIONS,dtype=bool);o.mask[e.N_SIMPLE:]=True
 a=Shared('shared_affordance',args.seed);idx,r,pr=a.choose(o)
 assert o.mask[idx]
 z=test.copy();z[12:17,13:16]=0
 v=a.observe(test,z,idx,r,pr,0,False)
 assert a.counter['shared_classes_observed']>=1
 print('E077_SELFTEST_PASSED',flush=True)
 if args.self_test:return
 if not args.out:raise ValueError('--out is required')
 e.run(args)
 f=Path(args.out)/'E076_RESULTS.json';record=json.loads(f.read_text())
 assert record['prefix_identical']
 assert {x['mode'] for x in record['rows']}==set(e.MODES)
 side={'experiment':'E077_SHARED_VISUAL_AFFORDANCE_ONE_GAME_V0',
 'parent_E076_source_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),
 'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'parent_report_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
 'still_handdesigned_not_trained_RL':True,'heldout_opened':False,'rows':record['rows']}
 with (Path(args.out)/'E077_RESULTS.json').open('x') as fp:json.dump(side,fp,indent=2)
 print('E077_RESULTS_FROZEN',args.out,flush=True)
if __name__=='__main__':main()
