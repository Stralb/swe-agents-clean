#!/usr/bin/env python3
"""E088 - visible goal alignment + causal transfer replanning in ONE studied game.

Scientific diagnostic, not zero-shot benchmark evaluation. Uses frozen E075
recorded prefix to return to reproducible Stage 3, then discovers goals from
matching rare-colour markers IN THE OBSERVED FRAME. Uses 2-pixel neighbouring
transfer orientation learned earlier via E084/E085 black-box interventions.
Never accesses game source, hidden state, a teacher or held-out levels.
"""
from pathlib import Path
from collections import defaultdict
import hashlib,json,logging,os,sys
import numpy as np
logging.disable(logging.INFO)
sys.path.insert(0,'/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
from src.adapter import ArcSession,N_SIMPLE
from src.e027.reproducibility import install_reproducibility
B=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
R=json.loads((B/'E075_REPORT.json').read_text())
p=B/'repeat.jsonl'
r=next(x for x in R['rows'] if x['mode']=='repeat')
assert hashlib.sha256(p.read_bytes()).hexdigest()==r['trace_sha256']
events=[json.loads(s) for s in p.read_text().splitlines()]
last=next(i for i,e in enumerate(events) if e['native_level_reward'] and e['progress']>=2)
prefix=events[:last+1]
def sha(f):return hashlib.sha256(np.asarray(f,dtype=np.int8).tobytes()).hexdigest()
def components(frame):
 a=np.asarray(frame,dtype=np.uint8)
 seen=np.zeros((64,64),dtype=bool);groups=defaultdict(list)
 for y in range(64):
  for x in range(64):
   if seen[y,x]:continue
   val=int(a[y,x]);todo=[(y,x)];seen[y,x]=True;cells=[]
   while todo:
    yy,xx=todo.pop();cells.append((yy,xx))
    for ny,nx in ((yy+1,xx),(yy-1,xx),(yy,xx+1),(yy,xx-1)):
     if 0<=ny<64 and 0<=nx<64 and not seen[ny,nx] and int(a[ny,nx])==val:
      seen[ny,nx]=True;todo.append((ny,nx))
   if 1<=len(cells)<=128:
    xx=np.array([z[1] for z in cells]);yy=np.array([z[0] for z in cells])
    groups[val].append({'size':len(cells),'x':float(xx.mean()),'y':float(yy.mean()),
       'xmin':int(xx.min()),'xmax':int(xx.max()),'ymin':int(yy.min()),'ymax':int(yy.max())})
 return groups
def stage_model(frame):
 a=np.asarray(frame,dtype=np.uint8)
 comps=components(a)
 bars=[]
 for o in comps.get(5,[]):
  if o['size']>=6 and o['xmax']-o['xmin']<=2 and o['ymax']-o['ymin']>=3:
   bars.append(round(o['x']))
 pillars=sorted(set(int(x) for x in bars))
 if len(pillars)!=4:raise RuntimeError('Cannot infer 4 vertical reference dividers: '+repr(pillars))
 edges=[5]+pillars+[58]
 centers=[int(round((i+j)/2)) for i,j in zip(edges[:-1],edges[1:])]
 h=lambda f:[int((np.asarray(f)[3:58,x]==0).sum()) for x in centers]
 init=h(a)
 targets=[None]*len(init)
 tags=[]
 for c,parts in comps.items():
  if len(parts)!=2 or sorted(x['size'] for x in parts)!=[2,3]:continue
  moving=next(x for x in parts if x['size']==3)
  marker=next(x for x in parts if x['size']==2)
  j=int(np.argmin([abs(x-moving['x']) for x in centers]))
  if abs(centers[j]-moving['x'])>3:continue
  dy=round(moving['y']-marker['y'])
  if targets[j] is not None:raise RuntimeError('Ambiguous marker match for pile')
  targets[j]=int(init[j]+dy)
  tags.append({'color':int(c),'pile':j,'cap':moving,'marker':marker,'height_delta':dy})
 for j in range(len(targets)):
  if targets[j] is None:targets[j]=0
 if len(tags)<3 or sum(targets)!=sum(init) or any(x<0 or x%2 for x in targets):
  raise RuntimeError('Visible goal hypothesis not consistent with conserved 2-pixel transfers')
 controls=[]
 for col,parts in comps.items():
  test=[x for x in parts if x['size']==4 and 54<=x['y']<=58 and x['xmax']-x['xmin']<=1]
  if len(test)==8:
   controls=sorted([(round(x['x']),round(x['y'])) for x in test])
   break
 if len(controls)!=8:raise RuntimeError('Failed to discover four paired bottom control tokens')
 # exact source x centre may be 12.5 and Python round half-even x=12,16 etc.
 ctrl_pairs=[controls[k:k+2] for k in range(0,len(controls),2)]
 assert len(ctrl_pairs)==len(pillars)
 if any(not(a[0]<pillar<b[0] and abs(a[0]-pillar)<=3 and abs(b[0]-pillar)<=3)
        for (a,b),pillar in zip(ctrl_pairs,pillars)):
  raise RuntimeError('Control pairs do not flank inferred separator columns')
 return pillars,centers,init,targets,tags,ctrl_pairs,h
def session():
 s=ArcSession();s.start_run('vc33',160,0)
 for i,e in enumerate(prefix):
  if sha(s.obs.frame)!=e['frame_sha_before']:raise RuntimeError('pre-state changed '+str(i))
  t=s.step(int(e['action_index']))
  if sha(t.next_obs.frame)!=e['frame_sha_after']:raise RuntimeError('post-state changed '+str(i))
 assert s.tracker.high_water==2
 return s
def main():
 install_reproducibility()
 out=Path('/home-mscluster/astrauss/e088_visual_goal_planning')/('E088_vc33_'+os.environ['SLURM_JOB_ID'])
 if out.exists():raise FileExistsError('Existing run will not be overwritten')
 out.mkdir(parents=True)
 env=session()
 pillars,centers,initial,target,tags,pairs,measure=stage_model(env.obs.frame)
 print('E088_INFERRED_GOAL',json.dumps({'pillars':pillars,'centers':centers,
  'current_heights':initial,'inferred_target_heights':target,
  'matched_colour_marker_evidence':tags,
  'inferred_pair_controls':pairs,'actions_remaining':160-env.tracker.actions},sort_keys=True),flush=True)
 blocked=defaultdict(set);events_out=[]
 while not env.done and env.tracker.actions<160 and env.tracker.high_water==2:
  current=measure(env.obs.frame)
  if current==target:break
  deficit=[(sum(target[:j+1])-sum(current[:j+1]))//2 for j in range(4)]
  candidates=[]
  for j,flow in enumerate(deficit):
   if flow==0:continue
   # Precondition inferred from causal evidence: transferring requires material
   # in the source, and receiver may have an unknown capacity.
   direction=1 if flow>0 else -1
   donor=j+1 if direction>0 else j
   if current[donor]<2:continue
   b=pairs[j][0] if direction>0 else pairs[j][1]
   x,y=b;index=N_SIMPLE+y*64+x
   if index in blocked[tuple(current)] or not env.obs.mask[index]:continue
   candidates.append((j,index,x,y))
  if not candidates:
   print('E088_REPLAN_STALLED',json.dumps({'state':current,'needed_flows':deficit}),flush=True)
   break
  # Earliest unsatisfied dependency first; on precondition failure try another.
  j,index,x,y=candidates[0]
  t=env.step(index)
  reward=float(t.reward)
  after=measure(t.next_obs.frame) if env.tracker.high_water==2 else None
  transition={'action_number':int(env.tracker.actions),'boundary':j,'click':[x,y],
   'prior':current,'posterior':after,'predicted_direction':'left' if deficit[j]>0 else 'right',
   'transfer_observed':bool(after is not None and after!=current),
   'native_reward':reward,'native_levels':int(env.tracker.high_water)}
  events_out.append(transition)
  print('E088_INTERVENTION',json.dumps(transition),flush=True)
  if after is not None and after==current:blocked[tuple(current)].add(index)
 outcome={'kind':'E088_COLOUR_CORRESPONDENCE_CAUSAL_GOAL_PLANNING',
  'game':'vc33','source_frozen_anchor_SHA256':prefix[-1]['frame_sha_after'],
  'initial_heights':initial,'inferred_goal':target,'goal_color_correspondences':tags,
  'final_heights':measure(env.obs.frame) if env.tracker.high_water==2 else None,
  'remaining_budget':160-int(env.tracker.actions),
  'initial_levels':2,'native_levels':int(env.tracker.high_water),
  'NEW_LEVEL_3_REACHED':bool(env.tracker.high_water>=3),
  'total_new_actions':len(events_out),'effectful_transfers':sum(z['transfer_observed'] for z in events_out),
  'rejected_preconditions':sum(not z['transfer_observed'] for z in events_out),
  'holds_no_game_source_or_oracle':True,'no_heldout_opened':True,
  'prefix_used_as_diagnostic_reinitialization':True,
  'operator_orientation_learned_in_previous_E084_E085':True,
  'events':events_out}
 with (out/'E088_RESULT.json').open('x') as f:json.dump(outcome,f,indent=2)
 print('E088_NATIVE_RESULT',json.dumps({k:v for k,v in outcome.items() if k!='events'},sort_keys=True),flush=True)
if __name__=='__main__':main()
