#!/usr/bin/env python3
"""E089 read-only analysis of NEXT STAGE after verified E088 research solution.
The diagnostic replays recorded native actions solely to position the public
development game; no claim of autonomous play for stages 1-3 is made.
"""
from pathlib import Path
import hashlib,importlib.util,json,logging,sys,os
from collections import Counter
import numpy as np
from PIL import Image
logging.disable(logging.INFO)
ROOT=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
CODE=ROOT/'e088_20261019_color_goal/E088_visual_goal_v0.py'
EXPECTED='e37c3c77c85cdb3f07b72070bacdcc1d80b71fe60f86a5256d03b1866b818062'
assert hashlib.sha256(CODE.read_bytes()).hexdigest()==EXPECTED
spec=importlib.util.spec_from_file_location('e088_frozen',CODE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from src.adapter import N_SIMPLE
saved=Path('/home-mscluster/astrauss/e088_visual_goal_planning/E088_vc33_71867/E088_RESULT.json')
report=json.loads(saved.read_text())
assert report['NEW_LEVEL_3_REACHED'] and report['total_new_actions']==23
def run():
 session=m.session()
 for i,x in enumerate(report['events']):
  xx,yy=x['click'];idx=N_SIMPLE+yy*64+xx
  assert session.obs.mask[idx]
  t=session.step(idx)
  if int(session.tracker.high_water)!=int(x['native_levels']):
   raise RuntimeError('Native continuation diverged at click '+str(i))
  if int(session.tracker.high_water)==2:
   model=m.stage_model(t.next_obs.frame)
   h=model[6](t.next_obs.frame)
   if h!=x['posterior']:raise RuntimeError('Height evidence diverged at click '+str(i))
 assert session.tracker.high_water==3
 frame=np.asarray(session.obs.frame,dtype=np.uint8)
 c=m.components(frame)
 info={'game':'vc33','reached_level':int(session.tracker.high_water),
  'action_budget_spent':int(session.tracker.actions),
  'remaining_actions':160-int(session.tracker.actions),
  'state':str(session.obs.progress),
  'legal_primitives':list(map(int,np.flatnonzero(session.obs.mask[:N_SIMPLE]))),
  'frame_shape':list(frame.shape),
  'new_stage_frame_sha256':m.sha(frame),
  'palette_histogram':{str(a):int(b) for a,b in zip(*np.unique(frame,return_counts=True))},
  'component_inventory':{str(k):[{'n':x['size'],'x':x['x'],'y':x['y']} for x in v if x['size']<=14][:18] for k,v in c.items()},
  'prior_stage3_was_replayed_scientific_diagnostic':True,'heldout_opened':False}
 try:
  pillars,centers,h,target,tags,pairs,_=m.stage_model(frame)
  info['E088_goal_recognizer_transfer']={'applicable':True,'pillars':pillars,'centers':centers,
  'heights':h,'predicted_target':target,'matching_tags':len(tags),'buttons':pairs}
 except Exception as e:
  info['E088_goal_recognizer_transfer']={'applicable':False,'reason':str(e)}
 out=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e089_20261019_stage4_recon')
 out.mkdir(parents=True,exist_ok=True)
 jsonpath=out/'E089_stage4_71867_resume.json'
 if jsonpath.exists():raise FileExistsError(jsonpath)
 with jsonpath.open('x') as f:json.dump(info,f,indent=2)
 png=out/'E089_stage4_observed.png'
 if png.exists():raise FileExistsError(png)
 colors=[(0,0,0),(0,116,217),(255,65,54),(46,204,64),(255,220,0),(170,170,170),
 (240,18,190),(255,133,27),(127,219,255),(135,12,37),(255,255,255),(110,110,110),
 (40,70,155),(0,170,170),(200,100,80),(210,210,180)]
 pixel=Image.new('RGB',(64,64));pixel.putdata([colors[int(v)] for v in frame.ravel()])
 pixel.resize((640,640),Image.Resampling.NEAREST).save(png)
 print('E089_NEXT_STAGE_INSPECTION',json.dumps(info,sort_keys=True),flush=True)
 print('E089_FRAME_SNAPSHOT',str(png),hashlib.sha256(png.read_bytes()).hexdigest(),flush=True)
if __name__=='__main__':run()
