#!/usr/bin/env python3
"""E107 multi-family, online, contrastive affordance learner.
No game names, coordinates, colour semantics, solutions, or recorded trajectories.
Causal claims remain INTERVENTIONAL HYPOTHESES, not identified causal effects:
the episode cannot be reset to an identical state for every alternative action.
"""
from collections import Counter, defaultdict, deque
import math, random
import numpy as np
from E106_perception_v0 import candidates, descriptor, signature, frame_digest

MODES=("contrastive","no_contrast","no_reliability","no_drift","no_context")

class ContrastiveAgent:
 def __init__(self,seed=1,mode="contrastive"):
  assert mode in MODES
  self.mode=mode;self.rng=random.Random(seed)
  self.data=defaultdict(Counter);self.classes=defaultdict(Counter)
  self.background=defaultdict(Counter)
  self.change_signature=defaultdict(Counter);self.other_signature=defaultdict(Counter)
  self.pixel_actions=defaultdict(set);self.visits=Counter();self.rewards=Counter()
  self.stats=Counter();self.recent=deque(maxlen=4)
  self.last_activity=0;self.active=None;self.option_age=0;self.trial_age=0
  self.trial_signature=None;self.trial_matches=0
  self.cached_frame=None;self.proposals=[];self.blocked={}
  self.selected=None;self.selected_desc=None;self.selected_context=None
  self.selected_kind=None;self.predicted=None;self.option_phase=None
 def reset(self,frame):
  self.data.clear();self.classes.clear();self.background.clear()
  self.change_signature.clear();self.other_signature.clear()
  self.pixel_actions.clear();self.visits.clear();self.rewards.clear()
  self.stats.clear();self.recent.clear()
  self.recent.append(np.asarray(frame,dtype=np.uint8).copy())
  self.last_activity=0;self.active=None;self.option_age=0;self.trial_age=0
  self.trial_signature=None;self.trial_matches=0
  self.cached_frame=None;self.proposals=[];self.blocked.clear()
  self.selected=None;self.selected_desc=None;self.selected_context=None
  self.selected_kind=None;self.predicted=None;self.option_phase=None

 @staticmethod
 def activity_bin(n):
  return 0 if n<=3 else 1 if n<=24 else 2
 @staticmethod
 def act_type(idx):
  return "primitive" if idx<6 else "click"

 def group(self,frame,idx):
  d=descriptor(frame,idx)
  return (self.act_type(idx),d)
 def context(self):
  return self.activity_bin(self.last_activity)

 def learned_prob(self,idx,group,context):
  """Beta-Bernoulli posterior combining exact-action and visual-class data."""
  a=self.data[(idx,context)]
  b=self.classes[(group,context)]
  yes=a["effect"]+0.4*b["effect"]
  no=a["none"]+0.4*b["none"]
  return (yes+1)/(yes+no+2),yes+no
 def environment_prob(self,idx,context):
  b=self.background[(self.act_type(idx),context)]
  return (b["effect"]+1)/(sum(b.values())+2)
 def expected_signature(self,idx,ctx):
  bag=self.change_signature[(idx,ctx)]
  if not bag:return None,0.
  sig,num=bag.most_common(1)[0]
  return sig,(num+1)/(sum(bag.values())+len(bag)+2)
 def effect_advantage(self,idx,group,context):
  p,n=self.learned_prob(idx,group,context)
  pnull=self.environment_prob(idx,context)
  if self.mode=="no_contrast":return p-.5,p,n
  return p-pnull,p,n

 def choose(self,frame,mask):
  legal=np.asarray(mask,dtype=bool)
  if self.active is not None:
   if legal[self.active] and self.option_age<8:
    idx=self.active
    self.selected=(idx,"verify_effect_under_intervention")
    self.selected_desc=self.group(frame,idx)
    self.selected_context=self.context()
    self.selected_kind=self.act_type(idx)
    self.predicted=self.expected_signature(idx,self.selected_context)[0]
    self.stats["verification_steps"]+=1
    return idx,"verify_effect_under_intervention",self.predicted
   self.active=None;self.option_age=0;self.trial_age=0
  key=frame_digest(frame)
  if key!=self.cached_frame:
   self.proposals=candidates(frame,legal)
   self.cached_frame=key
  available=[t for t in self.proposals if legal[t[0]]]
  if not available:
   available=candidates(frame,legal)
  primitive=[x for x in available if x[0]<6]
  clicks=[x for x in available if x[0]>=6]
  if primitive and clicks:
   # Balanced *legal-type* exploration, independent of game identity.
   trial=primitive if self.stats["choices"]%4==0 else clicks
  else:trial=available
  self.stats["choices"]+=1
  self.rng.shuffle(trial)
  ctx=self.context()
  def utility(item):
   idx,salience,origin=item
   grp=self.group(frame,idx)
   advantage,p,seen=self.effect_advantage(idx,grp,ctx)
   gain=(1.8/(1+self.visits[idx]))
   information=4*p*(1-p)/(1+.1*seen)
   scored=max(-.4,min(.6,advantage))*1.5
   reliability=self.data[(idx,ctx)]["effect"]
   if reliability<2 or self.mode=="no_reliability":
    scored*=.3
   if self.mode=="no_context":
    information=0.;scored=0.
   # Intrinsic utility is based on *conditional prediction*, not
   # on rewarding changes that could be automatic animation.
   reward=2.0*self.rewards[idx]/(1+self.visits[idx])
   # Penalize known no-effects only in the currently observed context.
   unproductive=self.data[(idx,ctx)]["none"]
   penalty=.10*max(0,unproductive-2)
   return (gain + .36*information + .35*salience + scored + reward
    -penalty + .04*self.rng.random())
  idx,_,origin=max(trial,key=utility)
  self.selected=(idx,"test_new_action_hypothesis")
  self.selected_desc=self.group(frame,idx)
  self.selected_context=ctx
  self.selected_kind=self.act_type(idx)
  self.predicted=self.expected_signature(idx,ctx)[0]
  self.stats["fresh_hypothesis_probes"]+=1
  return idx,"test_new_action_hypothesis_"+origin,self.predicted

 def update(self,before,after,idx,native_reward=0.,advanced=False):
  a=np.asarray(before,dtype=np.uint8)
  b=np.asarray(after,dtype=np.uint8)
  raw=a!=b
  # Controls for exogenous motion are estimated from differences under
  # distinct action descriptors, not from the current transition itself.
  drift=set()
  if self.mode!="no_drift":
   drift={p for p,groups in self.pixel_actions.items() if len(groups)>=3}
  residual=raw.copy()
  if drift:residual.ravel()[list(drift)]=False
  n=int(residual.sum())
  actual=signature(a,b,residual)
  context=self.selected_context if self.selected_context is not None else self.context()
  group=self.selected_desc if self.selected_desc is not None else self.group(a,idx)
  predicted,confidence=self.expected_signature(idx,context)
  total_seen=sum(self.data[(idx,context)].values())
  p_action,_=self.learned_prob(idx,group,context)
  p_bg=self.environment_prob(idx,context)
  # Prequential prediction test (before updating either distribution).
  label=int(n>=6 or native_reward>0)
  if self.stats["action_transitions"]>=10:
   self.stats["prequential_examples"]+=1
   self.stats["prequential_brier_action"]+=(p_action-label)**2
   self.stats["prequential_brier_null"]+=(p_bg-label)**2
   pa=min(.999,max(.001,p_action))
   pn=min(.999,max(.001,p_bg))
   self.stats["prequential_logloss_action"]+=-(label*math.log(pa)+(1-label)*math.log1p(-pa))
   self.stats["prequential_logloss_null"]+=-(label*math.log(pn)+(1-label)*math.log1p(-pn))
  if predicted is not None:
   self.stats["signature_predictions_tested"]+=1
   self.stats["signature_predictions_correct" if actual==predicted else "signature_predictions_wrong"]+=1
  else:self.stats["new_effect_signatures"]+=1
  self.data[(int(idx),context)]["effect" if label else "none"]+=1
  if self.mode!="no_context":
   self.classes[(group,context)]["effect" if label else "none"]+=1
  self.background[(self.act_type(idx),context)]["effect" if label else "none"]+=1
  self.change_signature[(int(idx),context)][actual]+=1
  self.other_signature[(self.act_type(idx),context)][actual]+=1
  if raw.sum()<=4 and raw.any():
   group_label=group
   for px in np.flatnonzero(raw):
    self.pixel_actions[int(px)].add(group_label)
  self.visits[int(idx)]+=1
  if native_reward>0:self.rewards[int(idx)]+=native_reward;self.stats["native_rewards"]+=1
  self.stats["action_transitions"]+=1
  self.stats["significant_changes" if label else "weak_effects"]+=1
  self.stats["pixels_explained_as_background"]+=int(raw.sum())-n
  self.recent.append(b.copy())
  self.last_activity=int(raw.sum())
  if len(self.recent)>=4:self.stats["four_frame_memory_actions"]+=1

  # Falsifiable hypothesis: a true affordance should reproduce a spatial
  # effect signature under an explicit repetition experiment.
  if self.selected and self.selected[1]=="verify_effect_under_intervention":
   self.trial_age+=1;self.option_age+=1
   if actual==self.trial_signature and label:
    self.trial_matches+=1
   repeat_limit=2 if self.mode!="no_reliability" else 7
   stop=(not label or advanced or self.option_age>=8 or
          (self.trial_age>=repeat_limit and (
           self.mode!="no_reliability" and self.trial_matches<2)))
   if stop:
    self.stats["hypotheses_falsified" if self.trial_matches<2 else "hypotheses_supported"]+=1
    self.active=None;self.option_age=0;self.trial_age=0
    self.trial_signature=None;self.trial_matches=0
    self.stats["options_ended"]+=1
   elif self.trial_age>=2 and self.trial_matches>=2:
    self.stats["reliably_repeated_actions"]+=1
  elif label and not advanced:
   if self.mode not in ("no_reliability",):
    self.active=idx;self.option_age=0;self.trial_age=0
    self.trial_signature=actual;self.trial_matches=0
    self.stats["hypotheses_proposed"]+=1
   else:
    self.active=idx;self.option_age=0;self.trial_age=0
  if advanced:
   self.active=None;self.option_age=0;self.trial_age=0
   self.trial_signature=None;self.trial_matches=0
   self.stats["level_boundaries"]+=1
  return {
   "raw_changed":int(raw.sum()),"background_discounted":int(raw.sum())-n,
   "residual_pixels":n,"effect_observed":bool(label),
   "effect_signature":list(actual),
   "predicted_effect_signature":list(predicted) if predicted is not None else None,
   "predicted_signature_correct":actual==predicted if predicted is not None else None,
   "prequential_p_action":round(p_action,4),"prequential_p_background":round(p_bg,4),
   "hypothesis_mode":self.mode,"action_context":context,
  }

def selftest():
 img=np.full((64,64),3,dtype=np.uint8)
 img[7:12,12:17]=7;img[30:38,44:48]=5
 masks=[]
 for legal in ([0,2,5],list(range(6,4102)),list(range(4102))):
  m=np.zeros(4102,dtype=bool);m[legal]=True;masks.append(m)
 for mode in MODES:
  for mask in masks:
   agent=ContrastiveAgent(16,mode);agent.reset(img)
   for i in range(22):
    idx,reason,pred=agent.choose(img,mask)
    assert mask[idx],(mode,idx)
    result=img.copy()
    if i%3!=0:result[7:12,12:17]=9
    obs=agent.update(img,result,idx)
    assert obs["residual_pixels"] in (0,25)
   assert agent.stats["action_transitions"]==22
   assert agent.stats["prequential_examples"]==12
   assert agent.stats["prequential_logloss_null"]>=0
 assert len(MODES)==5
 print("E107_CONTRASTIVE_BAYES_SELFTEST_PASSED",{"modes":len(MODES),"interfaces":len(masks)},flush=True)
if __name__=="__main__":selftest()
