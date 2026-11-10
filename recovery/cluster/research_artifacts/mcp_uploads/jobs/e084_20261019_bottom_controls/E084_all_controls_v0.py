#!/usr/bin/env python3
"""E083: Native controlled causal-action intervention on a single public development game.

Input prefix was produced by E075 from its own observation-driven actions.
The prefix is used ONLY to align independent diagnostic experiments at the
same visible level-3 starting state. No replay prefix is a deployable policy.
Each intervention replays the exact same 91 legal steps and then tests a legal
action for four steps, comparing against a time-matched neutral action sequence.
No hidden simulator state, oracle, game code, teacher feedback, or heldout game.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,logging,sys,time
import numpy as np
logging.disable(logging.INFO)
ROOT=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
sys.path.insert(0,str(ROOT))
from src.adapter import ArcSession,N_SIMPLE,N_ACTIONS,index_to_action
from src.e027.reproducibility import install_reproducibility
SOURCE=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
RECORD=json.loads((SOURCE/'E075_REPORT.json').read_text())
REP=next(x for x in RECORD['rows'] if x['mode']=='repeat')
ACTION_FILE=SOURCE/'repeat.jsonl'
assert hashlib.sha256(ACTION_FILE.read_bytes()).hexdigest()==REP['trace_sha256']
EVENTS=[json.loads(s) for s in ACTION_FILE.read_text().splitlines()]
END=next(i for i,r in enumerate(EVENTS) if r['native_level_reward']>0 and r['progress']>=2)
PREFIX=EVENTS[:END+1]
EXPECTED_FRAME=PREFIX[-1]['frame_sha_after']
GAME='vc33'; SEED=0; MAX_TOTAL=160; STEPS=4

def sha(frame):return hashlib.sha256(np.asarray(frame,dtype=np.int8).tobytes()).hexdigest()

def objects(frame):
 f=np.asarray(frame,dtype=np.uint8)
 assert f.shape==(64,64)
 seen=np.zeros((64,64),dtype=bool)
 color_counts=Counter(map(int,f.ravel()))
 bg=color_counts.most_common(1)[0][0]
 components=defaultdict(list)
 for y in range(64):
  for x in range(64):
   if seen[y,x]:continue
   col=int(f[y,x]);stack=[(y,x)];seen[y,x]=1;cells=[]
   while stack:
    yy,xx=stack.pop();cells.append((yy,xx))
    for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
     if 0<=ny<64 and 0<=nx<64 and not seen[ny,nx] and f[ny,nx]==col:
      stack.append((ny,nx));seen[ny,nx]=1
   if col==bg or not 1<=len(cells)<=128:continue
   cx=round(sum(xx for yy,xx in cells)/len(cells))
   cy=round(sum(yy for yy,xx in cells)/len(cells))
   if cy<=1 or cx<=1 or cx>=62:continue
   components[col].append((len(cells),cx,cy))
 for col in components:components[col].sort(key=lambda t:(abs(t[0]-4),t[1],t[2]))
 return components

def candidates(obs):
 mask=obs.mask
 rows=[];seen=set()
 def add(idx,label):
  if 0<=idx<len(mask) and bool(mask[idx]) and idx not in seen:
   seen.add(idx);a,xy=index_to_action(idx)
   rows.append({'index':int(idx),'label':label,'action_id':int(a),'xy':list(xy) if xy is not None else None})
 for idx in range(N_SIMPLE):add(idx,'legal_primitive')
 for xy,label in [((32,20),'neutral_background'),((3,5),'neutral_alt_background'),((0,0),'edge_control')]:
  add(N_SIMPLE+xy[1]*64+xy[0],label)
 comps=objects(obs.frame)
 # Deliberately compare distinct visual object classes, not hand-entered vc33 coordinates.
 for col in [9]:
  for size,x,y in comps.get(col,[])[:8]:
   add(N_SIMPLE+y*64+x,f'component_color{col}_n{size}')
 # Add complementary spatial coverage, avoiding the high-density timer header.
 for x,y in ((7,30),(28,49),(46,25),(59,41)):
  add(N_SIMPLE+y*64+x,'coverage')
 return rows

def reset_replay():
 s=ArcSession()
 s.start_run(GAME,MAX_TOTAL,SEED)
 assert len(PREFIX)==91
 for i,row in enumerate(PREFIX):
  # Full state equality at each checkpoint; no hidden simulator access.
  if sha(s.obs.frame)!=row['frame_sha_before']:
   raise RuntimeError(f'Prefix pre-hash diverged {i}')
  tr=s.step(int(row['action_index']))
  if sha(tr.next_obs.frame)!=row['frame_sha_after']:
   raise RuntimeError(f'Prefix post-hash diverged {i}')
 assert int(s.tracker.high_water)==2
 assert sha(s.obs.frame)==EXPECTED_FRAME
 return s

def test_action(idx):
 s=reset_replay()
 before=np.asarray(s.obs.frame,dtype=np.int8).copy()
 observations=[];rewards=[]
 for step in range(STEPS):
  if s.done:break
  if not bool(s.obs.mask[idx]):break
  t=s.step(idx)
  frame=np.asarray(t.next_obs.frame,dtype=np.int8).copy()
  observations.append(frame)
  rewards.append(float(t.reward))
 return before,observations,rewards

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--out',required=True)
 ap.add_argument('--max-interventions',type=int,default=23)
 args=ap.parse_args()
 install_reproducibility()
 root=Path(args.out)
 if root.exists():raise FileExistsError('Refuse to overwrite old causal probe')
 root.mkdir(parents=True)
 anchor=reset_replay()
 initial_candidates=candidates(anchor.obs)
 if len(initial_candidates)>args.max_interventions:
  initial_candidates=initial_candidates[:args.max_interventions]
 print('E083_PROBE_ANCHOR',json.dumps({'family':GAME,'prefix_steps':len(PREFIX),
  'frame_sha':EXPECTED_FRAME,'legal_primitives':list(map(int,np.flatnonzero(anchor.obs.mask[:N_SIMPLE]))),
  'candidate_count':len(initial_candidates),'candidates':initial_candidates}),flush=True)
 # Prefer a click on blank background. Cross-check it against alternative neutral action.
 neutral=next((x for x in initial_candidates if x['label']=='neutral_background'),None)
 if neutral is None:raise RuntimeError('Neutral reference action unavailable')
 _,neutralframes,neutralrewards=test_action(neutral['index'])
 if len(neutralframes)!=STEPS:raise RuntimeError('Baseline unexpectedly terminal before 4 steps')
 print('E083_NEUTRAL_4_STEP',json.dumps({'index':neutral['index'],
  'relative_pixel_changes_from_original':[int((f!=neutralframes[0]).sum()) for f in neutralframes],
  'native_rewards':neutralrewards}),flush=True)
 ranking=[];captured={};start=time.monotonic()
 for row in initial_candidates:
  idx=row['index']
  if idx==neutral['index']:
   frames=neutralframes;rewards=neutralrewards
  else:
   _,frames,rewards=test_action(idx)
  captured['action_'+str(idx)]=np.stack(frames) if frames else np.zeros((0,64,64),dtype=np.int8)
  deviations=[int((a!=b).sum()) for a,b in zip(frames,neutralframes)]
  causal=sum(deviations)
  if frames:
   new=frames[0]
   diff=(new!=neutralframes[0])
   color_pairs=Counter((int(a),int(b)) for a,b in zip(neutralframes[0][diff],new[diff]))
   pixel_xy=np.argwhere(diff)
   bounds=([int(pixel_xy[:,1].min()),int(pixel_xy[:,0].min()),
     int(pixel_xy[:,1].max()),int(pixel_xy[:,0].max())] if len(pixel_xy) else None)
  else:color_pairs=Counter();bounds=None
  record={**row,'causal_pixels_vs_neutral_by_step':deviations,
    'total_causal_pixels_across_4':causal,
    'native_advances_in_4':sum(rewards),
    'effect_bbox_first_step':bounds,
    'top_color_transitions_first_step':[(list(p),c) for p,c in color_pairs.most_common(4)],
    'native_score_claimed':False,'replay_as_deployed_policy':False}
  ranking.append(record)
  print('E083_ACTION_CONTRAST',json.dumps(record,sort_keys=True),flush=True)
 ranking.sort(key=lambda r:(r['total_causal_pixels_across_4'],r['native_advances_in_4']),reverse=True)
 np.savez_compressed(root/'E084_CONTROLS_FRAMES.npz',**captured)
 summary={'kind':'E084_ALL_BOTTOM_AFFORDANCE_CAUSAL_CENSUS',
 'development_game_only':GAME,
 'model_free_intervention_not_trained_policy':True,
 'prefix_source':'E075 recorded actions; diagnostic only',
 'prefix_len':len(PREFIX),'exact_parent_state_SHA256':EXPECTED_FRAME,
 'same_state_per_intervention_verified':True,
 'comparison':'4 steps same action versus 4 steps background click at identical state',
 'native_advancements_from_interventions':sum(x['native_advances_in_4'] for x in ranking),
 'probes':ranking,'elapsed_seconds':round(time.monotonic()-start,3),
 'excluded_holdouts_opened':False}
 with (root/'E083_CONTROLLED_CONTRASTS.json').open('x') as f:json.dump(summary,f,indent=2)
 print('E084_CAUSAL_CONTRAST_COMPLETE',json.dumps({'root':str(root),
  'ranked_top':ranking[:10],'zero_causal_effects':sum(x['total_causal_pixels_across_4']==0 for x in ranking),
  'total_tested':len(ranking)}),flush=True)

if __name__=='__main__':main()
