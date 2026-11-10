#!/usr/bin/env python3
"""E092: falsify same-color vertical-marker alignment on previously studied vc33.
Two direction-controlled native branches from identical, hash-verified observed
Level-4 start. Experimental replay of earlier Level-3 solution is NOT autonomous.
No game source inspection, hidden state, or protected environments.
"""
from pathlib import Path
import hashlib,importlib.util,json,logging,os,sys
import numpy as np
logging.disable(logging.INFO)
SRC=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e088_20261019_color_goal/E088_visual_goal_v0.py')
assert hashlib.sha256(SRC.read_bytes()).hexdigest()=='e37c3c77c85cdb3f07b72070bacdcc1d80b71fe60f86a5256d03b1866b818062'
spec=importlib.util.spec_from_file_location('e088',SRC);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from src.adapter import N_SIMPLE
R=Path('/home-mscluster/astrauss/e088_visual_goal_planning/E088_vc33_71867/E088_RESULT.json')
data=json.loads(R.read_text());assert data['NEW_LEVEL_3_REACHED']
def initial():
 s=m.session()
 for i,e in enumerate(data['events']):
  x,y=e['click'];a=N_SIMPLE+y*64+x
  t=s.step(a)
  if s.tracker.high_water!=e['native_levels']:raise RuntimeError('prefix diverged')
 assert s.tracker.high_water==3
 assert m.sha(s.obs.frame)=='ac5815e1998bbfd9381d2110fcab03e01b56f7480b48d8aeba1b944c6f63d46e'
 return s
def alignment(frame):
 comps=m.components(frame)
 by={}
 for color,v in comps.items():
  if color in (0,3,5,7,9):continue
  for o in v:
   if o['size']>1 and o['y']>8:
    by.setdefault(color,[]).append(o)
 matches=[]
 for c,v in by.items():
  for a in v:
   for b in v:
    if a is b:continue
    if a['size']>=b['size'] and a['x']<b['x']-8 and a['size']/b['size']<=3:
     matches.append((int(c),a,b))
 return matches
def buttons(frame):
 c=m.components(frame).get(9,[])
 pts=sorted((int(round(x['x'])),int(round(x['y']))) for x in c if x['size']>=4 and x['y']>=56)
 return pts
def run():
 from src.e027.reproducibility import install_reproducibility
 install_reproducibility()
 o=Path('/home-mscluster/astrauss/e092_stage4_goal_hypothesis')/('E092_'+os.environ['SLURM_JOB_ID'])
 if o.exists():raise FileExistsError(o)
 o.mkdir(parents=True)
 ctrl=buttons(initial().obs.frame)
 assert len(ctrl)==6
 seed=alignment(initial().obs.frame)
 print('E092_VISIBLE_COLOUR_CORRESPONDENCES',json.dumps([{'col':c,'moving':a,'marker':b,'dy':round(a['y']-b['y'])} for c,a,b in seed],sort_keys=True),flush=True)
 print('E092_CONTROLS_DERIVED_FROM_FRAME',ctrl,flush=True)
 rows=[]
 for v in ('first_left','first_right'):
  s=initial();site=ctrl[0] if v=='first_left' else ctrl[1]
  x,y=site;idx=N_SIMPLE+y*64+x
  trace=[]
  for n in range(10):
   if s.done or not s.obs.mask[idx]:break
   t=s.step(idx)
   tags=alignment(t.next_obs.frame)
   metrics=[]
   for c,a,b in tags:
    metrics.append({'color':c,'moving_y':a['y'],'reference_y':b['y'],
      'dy':round(a['y']-b['y'],2)})
   record={'branch':v,'action':s.tracker.actions,'y_differences':metrics,
      'native_reward':float(t.reward),'completed_levels':int(s.tracker.high_water),
      'image_sha256':m.sha(t.next_obs.frame)}
   trace.append(record)
   print('E092_TAG_PREDICTION_CHECK',json.dumps(record,sort_keys=True),flush=True)
   if s.tracker.high_water>=4:break
  rows.append({'branch':v,'site':site,'final_level':int(s.tracker.high_water),
   'new_level4':bool(s.tracker.high_water>=4),'events':trace})
 report={'kind':'E092_SAME_COLOR_MARKER_ALIGNMENT_RESEARCH_FALSIFICATION',
 'game':'vc33','level4_entry_experimental_replay':True,
 'source_future_reward_not_consulted_in_choice':True,
 'candidate_markers_from_only_observation':True,
 'controls_from_only_observation':True,'heldout_opened':False,'rows':rows}
 with (o/'E092_HYPOTHESIS_RESULT.json').open('x') as f:json.dump(report,f,indent=2)
 print('E092_ALIGNMENT_HYPOTHESIS_FINISHED',json.dumps([{k:v for k,v in z.items() if k!='events'} for z in rows]),flush=True)
if __name__=='__main__':run()
