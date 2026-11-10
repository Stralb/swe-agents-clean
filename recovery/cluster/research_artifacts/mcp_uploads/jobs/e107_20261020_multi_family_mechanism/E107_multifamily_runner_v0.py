#!/usr/bin/env python3
"""E106: preregistered multi-family SDK evaluation of game-agnostic online policy.

No demonstrations, human annotations, simulator source, oracle, game-specific
coordinates, special colors, target state, scripted prefix, or hidden rewards.
Use only current observed legal mask, frame and action feedback.
"""
import argparse,hashlib,importlib.util,json,logging,os,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
logging.disable(logging.INFO)
ROOT=Path("/home-mscluster/astrauss/RL-ARC-AGI-3-Project")
STAGE=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent")
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(STAGE))
E107=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e107_20261020_multi_family_mechanism")
sys.path.insert(0,str(E107))
from src.adapter import ArcSession,index_to_action,N_SIMPLE
from src.e027.reproducibility import install_reproducibility
from E106_perception_v0 import frame_digest,selftest as perception_selftest
from E106_online_explorer_v0 import AdaptiveExplorer as E106FrozenAgent
from E107_contrastive_agent_v0 import ContrastiveAgent,selftest as learner_selftest
PARENT=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e075_20261019_onegame_capability/E075_vc33_capability_v2.py")
PARENT_SHA="ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7"
PIXEL_SHA="78f3d86b77fd05c4409d0a3d900b7353d534ec095b285677e50abff8c1840d2f"
CORE_SHA="6d6ae06baa96d1ef7fcf0fdac725307af63a5cc1430003ddcde9d3dae8cf94d0"
E106_CORE_SHA="9bbcb04e7f1c2c1797e878e60aceeb4150bdbd0bf5a2346bb661859682dca304"
def digest(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def check_sources():
 if digest(PARENT)!=PARENT_SHA:raise RuntimeError("frozen baseline source changed")
 if digest(STAGE/"E106_perception_v0.py")!=PIXEL_SHA:raise RuntimeError("perception source changed")
 if digest(E107/"E107_contrastive_agent_v0.py")!=CORE_SHA:raise RuntimeError("contrastive policy changed")
 if digest(STAGE/"E106_online_explorer_v0.py")!=E106_CORE_SHA:raise RuntimeError("E106 comparator changed")
check_sources()
spec=importlib.util.spec_from_file_location("e075_frozen_baseline",PARENT)
e075=importlib.util.module_from_spec(spec);spec.loader.exec_module(e075)
POLICIES=("contrastive","no_contrast","no_reliability","no_drift","no_context","e106_frozen","event_repeat","type_random")

def run_native(game,seed,mode,budget,env_seed,root):
 root.mkdir(parents=True,exist_ok=False)
 session=ArcSession()
 initial=session.start_run(game,budget,env_seed)
 initial_digest=frame_digest(initial.frame)
 agent=(E106FrozenAgent(seed,"full") if mode=="e106_frozen" else
        ContrastiveAgent(seed,mode if mode in ("contrastive","no_contrast","no_reliability","no_drift","no_context") else "contrastive"))
 agent.reset(initial.frame)
 baseline=e075.Controller("random" if mode=="type_random" else "repeat",seed)
 first_mask=initial.mask
 first_primitives=[int(x) for x in np.flatnonzero(first_mask[:N_SIMPLE])]
 first_click_bins=int(first_mask[N_SIMPLE:].sum())
 native_progress=[];framehist=[np.asarray(initial.frame,dtype=np.uint8).copy()]
 initial_time=time.monotonic()
 log=root/"native_legal_interactions.jsonl"
 decisions=0
 with log.open("x") as file:
  while not session.done:
   obs=session.obs
   if mode in ("event_repeat","type_random"):
    action,why,pred=baseline.select(obs)
   else:
    action,why,pred=(agent.decide(obs.frame,obs.mask) if mode=="e106_frozen" else agent.choose(obs.frame,obs.mask))
   if not bool(obs.mask[action]):raise AssertionError("policy emitted masked illegal action")
   aid,xy=index_to_action(int(action))
   prev_level=int(session.tracker.high_water)
   t=session.step(int(action))
   progressed=int(session.tracker.high_water)>prev_level
   if mode in ("event_repeat","type_random"):
    update=baseline.observe(t,action,why,pred)
   else:
    update=agent.update(t.obs.frame,t.next_obs.frame,action,t.reward,progressed)
   if t.reward>0:
    native_progress.append({
     "charged_action":int(session.tracker.actions),
     "native_reward":float(t.reward),
     "native_levels":int(session.tracker.high_water)})
   newframe=np.asarray(t.next_obs.frame,dtype=np.uint8)
   framehist.append(newframe.copy())
   logrow={"policy":mode,"game":game,"seed":seed,
     "native_charged_actions":int(session.tracker.actions),
     "action_idx":int(action),"action_type":int(aid),
     "xy":list(xy) if xy is not None else None,
     "action_reason":why,
     "predicted_signature":pred,
     "observed_update":update,
     "native_reward":float(t.reward),
     "native_high_water":int(session.tracker.high_water),
     "before_digest":frame_digest(t.obs.frame),
     "after_digest":frame_digest(t.next_obs.frame)}
   file.write(json.dumps(logrow,sort_keys=True,default=str)+"\n")
   decisions+=1
 frames=root/"observations.npz"
 with frames.open("xb") as f:np.savez_compressed(f,frames=np.stack(framehist))
 native_charges=int(session.tracker.actions)
 if decisions>native_charges or native_charges>budget:
  raise AssertionError("charged SDK actions inconsistent")
 if native_charges-decisions>max(2,int(session.tracker.resets)+1):
  raise AssertionError("unexplained charges")
 score=session.scorecard() or {}
 outcome={"game":game,"mode":mode,"policy_seed":seed,"env_seed":env_seed,
  "budget":budget,"native_levels":int(session.tracker.high_water),
  "native_game_win_levels":int(session.obs.win_levels),
  "native_sdk_score":float(score.get("score",0.0)),
  "charged_actions":native_charges,"explicit_actions":decisions,
  "missing_charge_decisions":native_charges-decisions,
  "native_advancements":native_progress,
  "first_frame":initial_digest,
  "legal_primitives_at_start":first_primitives,
  "legal_click_bins_at_start":first_click_bins,
  "controller_stats":dict(agent.stats) if mode not in ("event_repeat","type_random") else {},
  "baseline_stats":dict(baseline.count) if mode in ("event_repeat","type_random") else {},
  "causal_model_updates":sum(agent.visits.values()) if mode not in ("event_repeat","type_random") else 0,
  "trial_seconds":round(time.monotonic()-initial_time,2),
  "trace_sha256":digest(log),"frame_archive_sha256":digest(frames),
  "game_specific_policy_parameters":False,"recorded_demonstrations_used":False,
  "oracle_or_simulator_source_used":False,
  "offline_gradient_training_updates":0,"research_type":"online_contrastive_prequential_affordance_learning"}
 with (root/"trial.json").open("x") as f:json.dump(outcome,f,indent=2)
 print("E107_NATIVE_GAME_RESULT",json.dumps(outcome,sort_keys=True),flush=True)
 return outcome

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--games",nargs="+",required=False,default=[])
 p.add_argument("--modes",nargs="+",default=list(POLICIES),choices=POLICIES)
 p.add_argument("--seeds",nargs="+",default=[28901],type=int)
 p.add_argument("--budget",type=int,default=160)
 p.add_argument("--env-seed",type=int,default=0)
 p.add_argument("--out")
 p.add_argument("--self-test",action="store_true")
 args=p.parse_args()
 check_sources()
 perception_selftest();learner_selftest()
 if args.self_test:return
 if not args.out or not args.games:raise ValueError("--games and --out required")
 import torch
 torch.set_num_threads(1)
 try:torch.set_num_interop_threads(1)
 except RuntimeError:pass
 install_reproducibility()
 out=Path(args.out)
 if out.exists():raise FileExistsError("No overwrite: "+str(out))
 out.mkdir(parents=True)
 manifest={"experiment":"E107_FIVE_FAMILY_CONTRASTIVE_ONLINE_DISCOVERY",
  "timestamp_before_any_native_game":datetime.now(timezone.utc).isoformat(),
  "game_ids_used_only_by_evaluation_harness":list(args.games),
  "modes":list(args.modes),"seeds":list(args.seeds),
  "native_budget":args.budget,"env_seed":args.env_seed,
  "source_SHA256":{"perception":PIXEL_SHA,"core":CORE_SHA,"E106_comparator":E106_CORE_SHA,
   "baseline":PARENT_SHA,"harness":digest(Path(__file__))},
  "forbidden_source_families_unopened":["cn04","lp85","m0r0","r11l","sk48"],
  "policy_does_not_load_game_names_or_solutions":True,
  "native_scores_not_intrinsically_shaped":True,
  "not_neural_trained_RL":True}
 with (out/"PREREGISTRATION.json").open("x") as f:json.dump(manifest,f,indent=2)
 print("E106_PROTOCOL_FROZEN_BEFORE_INTERACTION",json.dumps(manifest,sort_keys=True),flush=True)
 results=[]
 for game in args.games:
  for seed in args.seeds:
   starts=[]
   for mode in args.modes:
    root=out/game/str(seed)/mode
    print("E107_BEGIN",game,seed,mode,flush=True)
    try:
     result=run_native(game,seed,mode,args.budget,args.env_seed,root)
     results.append(result);starts.append(result["first_frame"])
    except Exception as exc:
     error={"game":game,"policy_seed":seed,"mode":mode,
      "error":str(exc),"traceback":traceback.format_exc()}
     results.append(error)
     print("E107_PRESERVED_FAILURE",json.dumps(error),flush=True)
   if len(starts)==len(args.modes):
    if len(set(starts))!=1:raise RuntimeError("Matched starting frames differ")
 report={"preregistration":manifest,"results":results,
   "completed":sum("native_levels" in x for x in results),
   "failed":sum("error" in x for x in results),
   "expected":len(args.games)*len(args.seeds)*len(args.modes)}
 with (out/"E107_EVALUATION_RESULT.json").open("x") as f:json.dump(report,f,indent=2)
 print("E107_COHORT_COMPLETE",json.dumps({
  "report":str(out/"E106_EVALUATION_RESULT.json"),
  "native_summary":[[x["game"],x["policy_seed"],x["mode"],x.get("native_levels","ERR"),
     x.get("controller_stats",{}).get("predictions_evaluated",0)] for x in results],
  "failed":report["failed"],"completed":report["completed"]}),flush=True)
if __name__=="__main__":main()
