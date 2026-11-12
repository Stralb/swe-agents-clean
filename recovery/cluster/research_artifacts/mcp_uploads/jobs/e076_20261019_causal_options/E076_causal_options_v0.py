#!/usr/bin/env python3
"""E076 native dev: source-preserving, objective-blind structured causal probing.
One historically exposed development game vc33 only.
No hidden game access, no solver scripts, no demo traces as policy inputs.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,random,sys,time
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np

SRC075=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e075_20261019_onegame_capability/E075_vc33_capability_v2.py")
EXPECTED075="ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7"
if hashlib.sha256(SRC075.read_bytes()).hexdigest()!=EXPECTED075:
 raise RuntimeError("E075 frozen source changed")
spec=importlib.util.spec_from_file_location("E075_frozen_source",SRC075)
e075=importlib.util.module_from_spec(spec);spec.loader.exec_module(e075)
from src.adapter import ArcSession,index_to_action,N_SIMPLE,N_ACTIONS
MODES=("frozen_repeat","object_probe","causal_option")
GAME="vc33"
def digest(a):return hashlib.sha256(np.asarray(a,dtype=np.int8).tobytes()).hexdigest()
def local_event(pre,post):
 a=np.asarray(pre,dtype=np.uint8);b=np.asarray(post,dtype=np.uint8)
 changed=a!=b
 n=int(changed.sum())
 indices=np.argwhere(changed)
 if not n:return {"effect":False,"pixels":0,"region":None,"signature":None,"single":None}
 pairs=Counter((int(i),int(j)) for i,j in zip(a[changed],b[changed]))
 label,k=pairs.most_common(1)[0]
 y,x=indices.mean(axis=0)
 region=(int(x//8),int(y//8))
 signature=(label[0],label[1],region[0],region[1],int(n>=24))
 return {"effect":bool(n>=6),"pixels":n,"region":region,"signature":signature if n>=6 else None,
  "single":(label[0],label[1],int(indices[0,0]//8)) if n==1 else None}
def object_candidates(obs):
 f=np.asarray(obs.frame,dtype=np.uint8)
 mask=obs.mask
 if f.shape!=(64,64):raise RuntimeError("Unexpected ARC grid geometry")
 bg=int(np.bincount(f.ravel(),minlength=16).argmax())
 seen=np.zeros((64,64),dtype=bool)
 pts={}
 def add(x,y,score,tag):
  if not 0<=x<64 or not 0<=y<64:return
  idx=int(N_SIMPLE+y*64+x)
  if idx>=len(mask) or not mask[idx]:return
  if idx not in pts or score>pts[idx][0]:pts[idx]=(score,tag)
 for col in sorted(set(map(int,np.unique(f)))):
  if col==bg:continue
  for y in range(64):
   for x in range(64):
    if seen[y,x] or int(f[y,x])!=col:continue
    stack=[(y,x)];seen[y,x]=True;cells=[]
    while stack:
     yy,xx=stack.pop();cells.append((yy,xx))
     for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,nx-1),(yy,nx+1)):
      if 0<=ny<64 and 0<=nx<64 and not seen[ny,nx] and f[ny,nx]==col:
       seen[ny,nx]=True;stack.append((ny,nx))
    if len(cells)>128:continue
    if min(yy for yy,xx in cells)==0 and max(yy for yy,xx in cells)==0:
     continue # single-row interface stripe; generic exclusion of UI bars
    cy=sum(yy for yy,xx in cells)/len(cells);cx=sum(xx for yy,xx in cells)/len(cells)
    items=[min(cells,key=lambda p:(p[0]-cy)**2+(p[1]-cx)**2),
       min(cells,key=lambda p:p[0]),max(cells,key=lambda p:p[0]),
       min(cells,key=lambda p:p[1]),max(cells,key=lambda p:p[1])]
    weight=1.0 if len(cells)<=24 else .60
    for yy,xx in items:add(xx,yy,weight,"object")
 for x,y in e075.candidate_points(f,limit=140):
  add(x,y,.38,"legacy_candidate")
 if len(pts)<20:
  for y in range(4,64,8):
   for x in range(4,64,8):add(x,y,.2,"coverage")
 for i in np.flatnonzero(mask[:N_SIMPLE]):pts[int(i)]=(.55,"primitive")
 if not pts:
  for i in np.flatnonzero(mask):pts[int(i)]=(.1,"legal_fallback")
 return pts
class CausalController:
 def __init__(self,mode,seed):
  assert mode in MODES[1:]
  self.mode=mode;self.rng=random.Random(seed+2026)
  self.tries=Counter();self.tried_state=Counter()
  self.evidence=defaultdict(lambda:{"effect":0,"none":0,"events":Counter(),"last":None})
  self.drift=Counter();self.drift_sites=defaultdict(set)
  self.active=None;self.streak=0;self.locked=None;self.cooldown={}
  self.counter=Counter();self.last_prediction=None
 def key(self,idx):
  if idx<N_SIMPLE:return ("primitive",int(idx))
  z=int(idx-N_SIMPLE);return (z%64//8,z//64//8)
 def choose(self,obs):
  pts=object_candidates(obs)
  valid=list(pts)
  if self.mode=="causal_option" and self.active in pts and self.streak<5:
   idx=self.active;key=self.key(idx)
   hyp=self.evidence[key]
   self.counter["option_actions"]+=1
   predicted=hyp["events"].most_common(1)[0][0] if hyp["events"] else None
   self.last_prediction=predicted
   return idx,"verify_predicted_local_event",predicted
  state=digest(obs.frame)
  pool=valid.copy();self.rng.shuffle(pool)
  def score(idx):
   k=self.key(idx);t=self.evidence[k];v=self.tries[k]
   novelty=1./(1+v)
   quality=(t["effect"]+1)/(t["effect"]+t["none"]+2)
   # Priors are generic: interactive-looking small objects and untested regions.
   intrinsic=.65*pts[idx][0]+1.5*novelty+.20*quality
   if self.mode=="causal_option":
    # Exercise independently verified controls, but do not monopolize one.
    intrinsic+=.30*quality if t["effect"]>=2 else 0
   return intrinsic-.20*self.tried_state[(state,k)]+.07*self.rng.random()
  idx=max(pool,key=score)
  self.counter["probe_actions"]+=1
  self.last_prediction=None
  return idx,"probe_object_hypothesis",None
 def observe(self,before,after,idx,why,pred,reward,levelchanged):
  ev=local_event(before,after)
  k=self.key(idx)
  old=self.evidence[k]
  state=digest(before)
  self.tries[k]+=1;self.tried_state[(state,k)]+=1
  if ev["single"]:
   sig=ev["single"];self.drift[sig]+=1
   self.drift_sites[sig].add(k)
   if len(self.drift_sites[sig])>=3 and self.drift[sig]>=4:
    self.counter["background_drift_hypotheses_confirmed"]+=1
  if ev["effect"]:
   old["effect"]+=1;old["events"][ev["signature"]]+=1
   self.counter["localized_events_observed"]+=1
  else:old["none"]+=1
  if pred is not None:
   self.counter["registered_predictions_tested"]+=1
   if ev["signature"]==pred:
    self.counter["predictions_verified"]+=1
   else:
    self.counter["predictions_falsified"]+=1
  elif why=="probe_object_hypothesis":
   self.counter["new_probe_hypotheses"]+=1
  if self.mode=="causal_option":
   if why=="verify_predicted_local_event":
    self.streak+=1
    if not ev["effect"] or (pred is not None and ev["signature"]!=pred):
     self.active=None;self.streak=0
     self.counter["options_stopped_after_evidence"]+=1
    elif self.streak>=5:
     self.active=None;self.streak=0;self.counter["options_stopped_by_limit"]+=1
   elif ev["effect"] and why=="probe_object_hypothesis":
    self.active=idx;self.streak=0;self.counter["options_started"]+=1
  if reward or levelchanged:
   self.active=None;self.streak=0
   self.counter["stage_boundaries"]+=1
  return {**ev,"predicted_event_signature":pred,
   "observed_signature":ev["signature"],"site":k}
def selftest():
 a=np.zeros((64,64),dtype=np.uint8);b=a.copy()
 a[12:16,10:13]=4;a[42:47,45:48]=5
 b=a.copy();b[42:47,45:48]=0
 assert local_event(a,b)["effect"]
 t=a.copy();t[0,33]=7;u=t.copy();u[0,33]=4
 assert not local_event(t,u)["effect"]
 class Fake:pass
 obs=Fake();obs.frame=a;obs.mask=np.zeros(N_ACTIONS,dtype=bool)
 obs.mask[N_SIMPLE:]=True;obs.mask[0]=True
 candidates=object_candidates(obs)
 assert candidates and any(x>=N_SIMPLE for x in candidates)
 for mode in MODES[1:]:
  ag=CausalController(mode,28901)
  action,reason,pred=ag.choose(obs)
  assert obs.mask[action]
  ev=ag.observe(a,b,action,reason,pred,0,False)
  assert ev["effect"] and ag.counter["localized_events_observed"]==1
 print("E076_SELFTEST_PASSED",json.dumps({"candidates":len(candidates),"methods":MODES}),flush=True)
def run(args):
 from src.e027.reproducibility import install_reproducibility
 import torch
 torch.set_num_threads(1)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 install_reproducibility()
 dest=Path(args.out)
 if dest.exists():raise FileExistsError("refuse existing E076 output")
 dest.mkdir(parents=True)
 rows=[]
 for mode in MODES:
  baseline=e075.Controller("repeat",args.seed)
  agent=None if mode=="frozen_repeat" else CausalController(mode,args.seed)
  session=ArcSession();session.start_run(GAME,args.budget,args.env_seed)
  start=digest(session.obs.frame)
  prefix=[];progress=[];active=False
  actions=[];frames=[np.asarray(session.obs.frame,dtype=np.int8).copy()]
  started=time.monotonic()
  logpath=dest/(mode+".jsonl")
  with logpath.open("x") as f:
   while not session.done:
    obs=session.obs
    if session.tracker.high_water>=2:active=True
    if not active or mode=="frozen_repeat":
     idx,reason,pred=baseline.select(obs)
    else:
     idx,reason,pred=agent.choose(obs)
    if not obs.mask[idx]:raise RuntimeError("illegal policy action")
    aid,xy=index_to_action(idx)
    tr=session.step(idx)
    native=float(tr.reward)
    if not active or mode=="frozen_repeat":
     outcome=baseline.observe(tr,idx,reason,pred)
     if not active:prefix.append((int(idx),digest(tr.obs.frame),digest(tr.next_obs.frame)))
    else:
     outcome=agent.observe(tr.obs.frame,tr.next_obs.frame,idx,reason,pred,native,bool(native))
    frames.append(np.asarray(tr.next_obs.frame,dtype=np.int8).copy())
    if native>0:progress.append((int(session.tracker.actions),float(native)))
    record={"mode":mode,"game":GAME,"seed":args.seed,"stage3_active":active,
     "scorer_action":int(session.tracker.actions),"environment_commands":int(session.tracker.env_commands),
     "action_index":int(idx),"action_type":int(aid),"xy":list(xy) if xy is not None else None,
     "reason":reason,"native_reward":native,"high_water":int(session.tracker.high_water),
     "episode":int(tr.info.get("episode",-1)),"state":str(tr.info.get("state")),
     "frame_sha_before":digest(tr.obs.frame),"frame_sha_after":digest(tr.next_obs.frame),
     "transition_evidence":outcome}
    f.write(json.dumps(record,default=str)+"\n")
    actions.append(record)
  prefix_hash=hashlib.sha256(json.dumps(prefix).encode()).hexdigest()
  framespath=dest/(mode+"_frames.npz")
  with framespath.open("xb") as ff:np.savez_compressed(ff,frames=np.stack(frames))
  card=session.scorecard() or {}
  row={"mode":mode,"source":"E076_ONE_GAME_STRUCTURED_CAUSAL_DEV","seed":args.seed,
   "budget":args.budget,"native_levels":int(session.tracker.high_water),"win_levels":int(session.obs.win_levels),
   "scorer_calls":int(session.tracker.actions),"raw_commands":int(session.tracker.env_commands),
   "resets":int(session.tracker.resets),"status":session.status,
   "sdk_score":float(card.get("score",0.0)),"rewards":progress,
   "identical_prefix_sha256":prefix_hash,"prefix_length":len(prefix),"start_frame_sha256":start,
   "causal_counts":dict(agent.counter) if agent else {},
   "causal_effect_regions":len(agent.evidence) if agent else 0,
   "duration_s":round(time.monotonic()-started,3),
   "trace":str(logpath),"trace_sha256":hashlib.sha256(logpath.read_bytes()).hexdigest(),
   "frames":str(framespath),"frames_sha256":hashlib.sha256(framespath.read_bytes()).hexdigest(),
   "policy_training_updates":0,"oracle_simulator_used":False}
  print("E076_ONE_GAME_RESULT",json.dumps(row,sort_keys=True),flush=True)
  rows.append(row)
 assert len({r["identical_prefix_sha256"] for r in rows})==1, "pre-stage causal comparison prefix differs"
 assert len({r["start_frame_sha256"] for r in rows})==1, "initial frames differ"
 report={"kind":"E076_SINGLE_GAME_CAUSAL_OPTION_PRE_REGISTERED_V0",
   "game":GAME,"development_only":True,"source_e075_sha256":EXPECTED075,
   "e076_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   "no_heldout_instantiated":True,"no_oracle_or_human_in_policy":True,
   "algorithm_is_hand_designed_not_newly_trained_rl":True,
   "prefix_identical":True,"rows":rows}
 with (dest/"E076_RESULTS.json").open("x") as f:json.dump(report,f,indent=2)
 print("E076_DONE",str(dest/"E076_RESULTS.json"),flush=True)
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--self-test",action="store_true")
 p.add_argument("--out",default="")
 p.add_argument("--seed",type=int,default=28901)
 p.add_argument("--env-seed",type=int,default=0)
 p.add_argument("--budget",type=int,default=160)
 a=p.parse_args();selftest()
 if not a.self_test:
  if not a.out:raise ValueError("--out mandatory")
  run(a)
if __name__=="__main__":main()
