#!/usr/bin/env python3
"""E075: one-game observation-only effect hypotheses and event-terminated options.
Development diagnostic, not a newly trained RL or private-benchmark solver.
Reads only the public current frame, legal-action mask, and prior own outcomes.
No simulator cloning, demonstrated trajectories, source inspection, or game branches.
"""
from __future__ import annotations
import argparse, hashlib, json, random, os, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path("/home-mscluster/astrauss/RL-ARC-AGI-3-Project")
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.adapter import ArcSession, index_to_action, N_SIMPLE, N_ACTIONS

MODES=("random","structured","repeat","blind_repeat","belief_verify")
GAME="vc33" # pre-registered, historically exposed development game; no game-specific policy logic

def digest(frame):
 return hashlib.sha256(np.asarray(frame,dtype=np.int8).tobytes()).hexdigest()

def candidate_points(frame,limit=140):
 """Observation-only 4-connected same-colour components plus a coverage grid."""
 f=np.asarray(frame)
 if f.shape!=(64,64):raise ValueError("unexpected native observation shape")
 colors,count=np.unique(f,return_counts=True)
 bg=int(colors[int(np.argmax(count))])
 visited=np.zeros((64,64),dtype=bool)
 comps=[]
 for col in colors:
  c=int(col)
  if c==bg:continue
  for y in range(64):
   for x in range(64):
    if visited[y,x] or int(f[y,x])!=c:continue
    todo=[(y,x)];visited[y,x]=True;cells=[]
    while todo:
     ay,ax=todo.pop();cells.append((ay,ax))
     for ny,nx in ((ay-1,ax),(ay+1,ax),(ay,ax-1),(ay,ax+1)):
      if 0<=ny<64 and 0<=nx<64 and not visited[ny,nx] and int(f[ny,nx])==c:
       visited[ny,nx]=True;todo.append((ny,nx))
    comps.append((len(cells),c,cells))
 # Colour-balanced small interaction regions before huge background-like structures.
 comps.sort(key=lambda t:(t[0]>160,abs(t[0]-8),t[1],t[2][0]))
 coords=[];seen=set()
 def add(x,y):
  if 0<=x<64 and 0<=y<64 and (x,y) not in seen:
   seen.add((x,y));coords.append((x,y))
 for _,col,cells in comps[:100]:
  cy=float(sum(p[0] for p in cells))/len(cells)
  cx=float(sum(p[1] for p in cells))/len(cells)
  picks=[min(cells,key=lambda p:(p[0]-cy)**2+(p[1]-cx)**2),
         min(cells,key=lambda p:p[0]),
         max(cells,key=lambda p:p[0]),
         min(cells,key=lambda p:p[1]),
         max(cells,key=lambda p:p[1])]
  for y,x in picks:add(x,y)
 if len(coords)<limit:
  for y in range(4,64,8):
   for x in range(4,64,8):add(x,y)
 return coords[:limit]

def primitive_indices(obs):
 return [int(i) for i in np.flatnonzero(obs.mask[:N_SIMPLE])]

def legal_candidates(obs):
 legal=primitive_indices(obs)
 if np.any(obs.mask[N_SIMPLE:]):
  legal.extend(N_SIMPLE+y*64+x for x,y in candidate_points(obs.frame) if obs.mask[N_SIMPLE+y*64+x])
 # ensure action space complete even if no extracted object evidence
 if not legal:legal=list(map(int,np.flatnonzero(obs.mask)))
 return sorted(set(legal))

class Controller:
 def __init__(self,mode,seed):
  assert mode in MODES
  self.mode=mode;self.rng=random.Random(seed)
  self.models={}             # action -> [positive evidence, no-effect evidence]
  self.events={}             # action -> running signed colour-count delta (diagnostic)
  self.visits=Counter()      # (visible state, action) repetition
  self.active=None;self.consecutive=0;self.blind_left=0
  self.count=Counter();self.reasons=Counter()
  self.prior_positive=Counter()
 def posterior(self,idx):
  p,n=self.models.get(idx,(0,0))
  return (p+1)/(p+n+2)
 def select(self,obs):
  legal=list(map(int,np.flatnonzero(obs.mask)))
  if not legal:raise RuntimeError("no legal action")
  if self.mode=="random":
   # Type-uniform random, not flat-coordinate-biased.
   ids=primitive_indices(obs)
   if np.any(obs.mask[N_SIMPLE:]): ids.append(6)
   if not ids:raise RuntimeError("no legal types")
   kind=self.rng.choice(ids)
   idx=N_SIMPLE+self.rng.randrange(4096) if kind==6 else legal[kind-1] if kind in (1,2,3,4,5) else 5
   if not obs.mask[idx]:idx=self.rng.choice(legal)
   self.reasons["random"]+=1
   return idx,"random",None
  if self.mode in ("repeat","belief_verify") and self.active is not None and obs.mask[self.active]:
   self.count["option_steps"]+=1;self.reasons["repeat_until_event"]+=1
   return self.active,"repeat_until_event",self.posterior(self.active) if self.active in self.models else None
  if self.mode=="blind_repeat" and self.active is not None and self.blind_left>0 and obs.mask[self.active]:
   self.blind_left-=1;self.count["blind_repeat_steps"]+=1
   self.reasons["blind_fixed_repeat"]+=1
   return self.active,"blind_fixed_repeat",self.posterior(self.active) if self.active in self.models else None
  candidates=legal_candidates(obs)
  state=digest(obs.frame)
  self.rng.shuffle(candidates)
  if self.mode=="belief_verify":
   # Explicit, falsifiable Bernoulli hypotheses about effect/no effect.
   # Prefer uncertainty / novel state-action combinations, never reward oracle hints.
   def utility(idx):
    p,n=self.models.get(idx,(0,0))
    prob=(p+1)/(p+n+2)
    info=4*prob*(1-prob)
    reuse=.30*prob if p>n else 0.
    penalty=min(1.0,self.visits[(state,idx)])*1.2
    return info+reuse-penalty+0.002*self.rng.random()
   idx=max(candidates,key=utility)
  else:
   # Candidate exploration without model-based action preference.
   few=min(self.visits[(state,idx)] for idx in candidates)
   idx=self.rng.choice([idx for idx in candidates if self.visits[(state,idx)]==few])
  self.reasons["new_probe"]+=1;self.count["probe_actions"]+=1
  return idx,"new_probe",self.posterior(idx) if idx in self.models else None
 def observe(self,tr,idx,reason,pred):
  before=np.asarray(tr.obs.frame,dtype=np.int8)
  after=np.asarray(tr.next_obs.frame,dtype=np.int8)
  fraction=float(np.mean(before!=after))
  changed=(fraction>=.004 or tr.reward>0)
  self.visits[(digest(before),idx)]+=1
  old=self.models.get(idx,(0,0))
  if old[0]+old[1]>0:
   self.count["predictions_checked"]+=1
   pred_class=((old[0]+1)/(sum(old)+2))>=.5
   if pred_class!=changed:self.count["contradictions"]+=1
   else:self.count["predictions_matched"]+=1
  else:self.count["new_hypotheses"]+=1
  self.models[idx]=(old[0]+int(changed),old[1]+int(not changed))
  va=np.bincount(np.asarray(before,dtype=np.uint8).ravel(),minlength=16).astype(int)
  vb=np.bincount(np.asarray(after,dtype=np.uint8).ravel(),minlength=16).astype(int)
  delta=(vb-va).tolist()
  self.events[idx]=delta
  if changed:self.count["effectful_actions"]+=1
  if tr.reward>0:self.count["level_advancements"]+=int(tr.reward);self.prior_positive[idx]+=int(tr.reward)
  if self.mode in ("repeat","belief_verify"):
   if changed and reason=="new_probe":
    self.active=idx;self.consecutive=0;self.count["options_started"]+=1
   elif changed and reason=="repeat_until_event":
    self.consecutive+=1
    # Guard against unbounded self-reinforcing effectful cycles.
    if self.consecutive>=12:
     self.active=None;self.count["option_ttl_stops"]+=1
   elif reason=="repeat_until_event":
    self.active=None;self.consecutive=0;self.count["options_stopped_by_mismatch"]+=1
  elif self.mode=="blind_repeat":
   if changed and reason=="new_probe":self.active=idx;self.blind_left=4;self.count["options_started"]+=1
   elif reason=="blind_fixed_repeat" and self.blind_left==0:self.active=None
  if tr.reward>0:
   self.active=None;self.consecutive=0;self.blind_left=0
   self.count["level_boundaries"]+=1
  if tr.terminal:
   self.active=None;self.consecutive=0;self.blind_left=0
  return {"changed_fraction":round(fraction,6),"effect":bool(changed),
          "colour_count_delta":delta,"predicted_probability":round(pred,4) if pred is not None else None}

def selftest():
 a=np.zeros((64,64),np.int8);a[4:7,8:11]=2;a[33:38,44:46]=3
 pts=candidate_points(a)
 assert len(pts)>1
 assert (9,5) in pts or any(8<=x<=10 and 4<=y<=6 for x,y in pts)
 assert any(44<=x<=45 and 33<=y<=37 for x,y in pts)
 c=Controller("belief_verify",1)
 assert abs(c.posterior(6)-.5)<1e-8
 print("E075_SELFTEST_PASSED",{"candidates":len(pts),"types":MODES},flush=True)

def run(args):
 import torch
 torch.set_num_threads(1)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 from src.e027.reproducibility import install_reproducibility
 install_reproducibility()
 out=Path(args.out)
 if out.exists():raise FileExistsError("Refusing to overwrite existing E075 run output: "+str(out))
 out.mkdir(parents=True)
 srcsha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 summaries=[];starts=[]
 for mode in MODES:
  ctrl=Controller(mode,args.seed)
  session=ArcSession()
  obs=session.start_run(GAME,args.budget,args.env_seed)
  startsha=digest(obs.frame);starts.append(startsha)
  trace=out/f"{mode}.jsonl";framehist=[np.asarray(obs.frame,dtype=np.int8).copy()]
  begin=time.monotonic()
  first_progress=None
  with open(trace,'x') as f:
   while not session.done:
    obs=session.obs
    idx,reason,pred=ctrl.select(obs)
    if not obs.mask[idx]:raise RuntimeError("Policy emitted illegal action")
    aid,xy=index_to_action(idx)
    tr=session.step(idx)
    ev=ctrl.observe(tr,idx,reason,pred)
    if tr.reward>0 and first_progress is None:first_progress=session.tracker.actions
    framehist.append(np.asarray(tr.next_obs.frame,dtype=np.int8).copy())
    row={"mode":mode,"game":GAME,"seed":args.seed,"env_seed":args.env_seed,
      "action_number":int(session.tracker.actions),"all_environment_commands":int(session.tracker.env_commands),
      "resets":int(session.tracker.resets),"episode":int(tr.info.get("episode",-1)),
      "frame_sha_before":digest(tr.obs.frame),"frame_sha_after":digest(tr.next_obs.frame),
      "action_index":int(idx),"action_id":int(aid),"xy":list(xy) if xy is not None else None,
      "reason":reason,"native_level_reward":float(tr.reward),
      "progress":int(tr.next_obs.progress),"terminal":bool(tr.terminal),
      "game_state":tr.info.get("state"),"source":"public SDK observation only",**ev}
    f.write(json.dumps(row,sort_keys=True)+"\n")
  framesfile=out/f"{mode}_frames.npz"
  with open(framesfile,"xb") as fp:np.savez_compressed(fp,frames=np.stack(framehist))
  card=session.scorecard() or {}
  result={"mode":mode,"game":GAME,"seed":args.seed,"env_seed":args.env_seed,
   "budget_scorer_actions":args.budget,"scorer_actions":int(session.tracker.actions),
   "environment_commands_including_all_resets":int(session.tracker.env_commands),
   "resets":int(session.tracker.resets),"final_status":session.status,
   "levels_completed":int(session.tracker.high_water),"win_levels":int(session.obs.win_levels),
   "first_progress_at":first_progress,"sdk_score":float(card.get("score",0.0)),
   "elapsed_seconds":round(time.monotonic()-begin,3),
   "started_frame_sha256":startsha,"hypotheses":len(ctrl.models),
   "counts":dict(ctrl.count),"reasons":dict(ctrl.reasons),
   "trace_jsonl":str(trace),"trace_sha256":hashlib.sha256(trace.read_bytes()).hexdigest(),
   "frames":str(framesfile),"frames_sha256":hashlib.sha256(framesfile.read_bytes()).hexdigest(),
   "manual_solution":False,"human_demo_used":False,"oracle_used":False,
   "native_online_rl_updates":0,"historically_exposed_development_game":True}
  summaries.append(result)
  print("E075_RESULT",json.dumps(result,sort_keys=True),flush=True)
 payload={"experiment":"E075_ONE_GAME_OBSERVATION_ONLY_CAPABILITY_SMOKE","git_root":str(ROOT),
   "script_sha256":srcsha,"models_are_handdesigned_diagnostic":True,
   "not_a_trained_RL_algorithm":True,"not_official_aggregated_benchmark":True,
   "development_game_only":GAME,"heldout_game_instances_opened":False,
   "same_initial_frame":len(set(starts))==1,"rows":summaries}
 with open(out/"E075_REPORT.json","x") as f:json.dump(payload,f,indent=2)
 print("E075_RUN_COMPLETE",str(out/"E075_REPORT.json"),flush=True)

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--self-test",action="store_true")
 p.add_argument("--out",default="")
 p.add_argument("--seed",type=int,default=28901)
 p.add_argument("--env-seed",type=int,default=0)
 p.add_argument("--budget",type=int,default=160)
 a=p.parse_args()
 selftest()
 if not a.self_test:
  if not a.out:raise ValueError("--out is required")
  run(a)
if __name__=="__main__":main()
