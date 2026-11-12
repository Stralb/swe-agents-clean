#!/usr/bin/env python3
"""E090: Stage 4 black-box temporal intervention test, studied vc33 ONLY.

Experimentally align the SAME visible stage-4 observation by replay of recorded
E075 + E088 research traces. Neither prefix is a deployable autonomous policy.
Interact only through legal public ArcSession actions. Discover control sites
from image pixels, not hidden game code or manual game-specific coordinates.
Compare repeated clicks against an identically timed background-click control.
"""
import hashlib,importlib.util,json,logging,os,sys
from pathlib import Path
from collections import Counter
import numpy as np
logging.disable(logging.INFO)
RESEARCH=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
SOURCE=RESEARCH/'e088_20261019_color_goal/E088_visual_goal_v0.py'
SOURCE_SHA='e37c3c77c85cdb3f07b72070bacdcc1d80b71fe60f86a5256d03b1866b818062'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
spec=importlib.util.spec_from_file_location('e088_frozen_stage3',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from src.adapter import N_SIMPLE
REPORT=Path('/home-mscluster/astrauss/e088_visual_goal_planning/E088_vc33_71867/E088_RESULT.json')
data=json.loads(REPORT.read_text())
assert data['NEW_LEVEL_3_REACHED'] and data['total_new_actions']==23
STEPS=4
def origin():
 s=m.session()
 for i,e in enumerate(data['events']):
  x,y=e['click'];idx=N_SIMPLE+y*64+x
  if not s.obs.mask[idx]:raise RuntimeError('Recorded action illegal')
  tr=s.step(idx)
  if int(s.tracker.high_water)!=int(e['native_levels']):
   raise RuntimeError('Record diverged at '+str(i))
 assert s.tracker.high_water==3
 assert int(s.tracker.actions)==115
 expected='ac5815e1998bbfd9381d2110fcab03e01b56f7480b48d8aeba1b944c6f63d46e'
 if m.sha(s.obs.frame)!=expected:raise RuntimeError('E089 independently observed next state mismatch')
 return s
def candidate_sites(obs):
 parts=m.components(obs.frame).get(9,[])
 controls=sorted([(int(round(q['x'])),int(round(q['y']))) for q in parts
   if q['size'] in (4,6,9) and q['y']>=56],key=lambda z:(z[0],z[1]))
 if len(controls)!=6:raise RuntimeError('Stage4 control count unexpectedly '+str(controls))
 return controls
def experiment(xy,initial):
 s=origin();prev=m.sha(s.obs.frame)
 assert prev==initial
 x,y=xy;idx=N_SIMPLE+y*64+x
 trace=[]
 for step in range(STEPS):
  if s.done or not s.obs.mask[idx]:break
  t=s.step(idx)
  f=np.asarray(t.next_obs.frame,dtype=np.int8).copy()
  trace.append({'frame':f,'reward':float(t.reward),
   'levels':int(s.tracker.high_water),'frameSHA':m.sha(f)})
 return trace
def main():
 from src.e027.reproducibility import install_reproducibility
 install_reproducibility()
 orig=origin()
 sha0=m.sha(orig.obs.frame)
 controls=candidate_sites(orig.obs)
 # Pick visibly green non-control screen region as the neutral action.
 neutral=(32,16)
 base=experiment(neutral,sha0)
 if len(base)!=STEPS:raise RuntimeError('Neutral continuation unexpectedly terminated')
 root=Path('/home-mscluster/astrauss/e090_single_game_stage4_causality')/('E090_vc33_'+os.environ['SLURM_JOB_ID'])
 if root.exists():raise FileExistsError('E090 output exists: '+str(root))
 root.mkdir(parents=True)
 print('E090_STAGE4_CONTROL_CENSUS',json.dumps({'control_sites':controls,'neutral_site':neutral,
  'original_frame_sha256':sha0,'native_levels_at_entry':3,'remaining_budget':45,
  'four_history_frames_retained':True,'manual_goal_provided':False}),flush=True)
 report=[];captures={'neutral':np.stack([x['frame'] for x in base])}
 for x,y in controls:
  trial=experiment((x,y),sha0)
  comp=[]
  for i,e in enumerate(trial):
   frame=e['frame'];ref=base[i]['frame']
   d=(frame!=ref)
   abs_change=int(d.sum())
   changes=Counter((int(a),int(b)) for a,b in zip(ref[d],frame[d]))
   comp.append({'t':i+1,'causal_pixel_count':abs_change,
    'native_levels':e['levels'],'native_reward':e['reward'],
    'changed_palette_pairs':[(list(k),v) for k,v in changes.most_common(5)],
    'delta_blue_count':int((frame==1).sum()-(ref==1).sum()),
    'delta_grey_count':int((frame==5).sum()-(ref==5).sum())})
  rec={'xy':[x,y],'comparison':comp,
    'causal_effect_sustained':bool(comp and comp[-1]['causal_pixel_count']>0),
    'max_native_level':max([r['levels'] for r in trial] or [3]),
    'native_rewards_total':sum(r['reward'] for r in trial)}
  report.append(rec)
  captures['control_'+str(x)]=np.stack([e['frame'] for e in trial])
  print('E090_STAGE4_CAUSAL_CONTRAST',json.dumps(rec),flush=True)
 with (root/'E090_STAGE4_CAUSAL_CONTRAST.json').open('x') as f:json.dump({
  'kind':'E090_STUDIED_GAME_STAGE4_NEUTRAL_CONTROLLED_CONTRAST',
  'game':'vc33','native_levels_at_initialization':3,'observed_stage4_frame_sha256':sha0,
  'control_candidates_derived_from_current_visible_pixels':True,
  'recorded_prefix_used_only_as_lab_state_reset':True,
  'E088_goal_recognizer_generalizes_unchanged':False,
  'four_frame_temporal_contrasts':True,'hidden_state_used':False,'heldout_opened':False,
  'results':report},f,indent=2)
 with (root/'E090_STAGE4_HISTORY_FRAMES.npz').open('xb') as f:np.savez_compressed(f,**captures)
 print('E090_STAGE4_CONTROL_EXPERIMENT_COMPLETED',str(root),
  'active_control_sites',sum(r['causal_effect_sustained'] for r in report),
  'native_advances',sum(r['native_rewards_total'] for r in report),flush=True)
if __name__=='__main__':main()
