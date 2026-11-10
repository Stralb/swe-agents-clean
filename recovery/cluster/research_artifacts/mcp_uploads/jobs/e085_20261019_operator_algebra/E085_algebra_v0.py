#!/usr/bin/env python3
"""E085: black-box algebra of visually discovered controls (one public dev game).
No source inspection, emulator cloning or human trajectory use by any policy.
Recorded E075 prefix is used solely to reset scientific interventions to exactly
the same observable state, and is never represented as autonomous play.
"""
from pathlib import Path
from collections import defaultdict
import sys,hashlib,json,logging,os,statistics
import numpy as np
logging.disable(logging.INFO)
sys.path.insert(0,'/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
from src.adapter import ArcSession,N_SIMPLE
from src.e027.reproducibility import install_reproducibility
START=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
E084=Path('/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_71855/E083_CONTROLLED_CONTRASTS.json')
record=json.loads((START/'E075_REPORT.json').read_text())
r=next(x for x in record['rows'] if x['mode']=='repeat')
assert hashlib.sha256((START/'repeat.jsonl').read_bytes()).hexdigest()==r['trace_sha256']
events=[json.loads(z) for z in (START/'repeat.jsonl').read_text().splitlines()]
END=next(i for i,z in enumerate(events) if z['native_level_reward'] and z['progress']>=2)
prefix=events[:END+1];END_SHA=prefix[-1]['frame_sha_after']
prior=json.loads(E084.read_text())
controls=sorted([z for z in prior['probes'] if z['label'].startswith('component_color9')],key=lambda z:z['xy'][0])
assert len(controls)==8
neutral=next(x for x in prior['probes'] if x['label']=='neutral_background')
pairs=[controls[i:i+2] for i in range(0,8,2)]
assert len(pairs)==4
def digest(f):return hashlib.sha256(np.asarray(f,dtype=np.int8).tobytes()).hexdigest()
def clean(f):
 a=np.asarray(f,dtype=np.uint8).copy();a[0]=0
 return a
def session():
 s=ArcSession();s.start_run('vc33',160,0)
 for k,x in enumerate(prefix):
  if digest(s.obs.frame)!=x['frame_sha_before']:raise RuntimeError('initial divergence '+str(k))
  tr=s.step(int(x['action_index']))
  if digest(tr.next_obs.frame)!=x['frame_sha_after']:raise RuntimeError('later divergence '+str(k))
 if s.tracker.high_water!=2 or digest(s.obs.frame)!=END_SHA:raise RuntimeError('wrong level3 anchor')
 return s
def rollout(aa):
 s=session();frames=[];rewards=[]
 for idx in aa:
  if not s.obs.mask[idx]:raise ValueError('Illegal action')
  if s.done:raise RuntimeError('Unexpected terminal')
  t=s.step(idx);frames.append(clean(t.next_obs.frame));rewards.append(float(t.reward))
 return frames,rewards,int(s.tracker.high_water)
def diff(a,b):return int((np.asarray(a)!=np.asarray(b)).sum())
def xy(idx):
 if idx<N_SIMPLE:return None
 t=idx-N_SIMPLE
 return [int(t%64),int(t//64)]
def main():
 install_reproducibility()
 out=Path('/home-mscluster/astrauss/e085_single_game_operator_algebra')/('E085_vc33_'+os.environ['SLURM_JOB_ID'])
 if out.exists():raise FileExistsError(out)
 out.mkdir(parents=True)
 nidx=int(neutral['index'])
 baseframes,baserewards,_=rollout((nidx,nidx))
 base=baseframes[-1]
 tasks=[]
 for group,(a,b) in enumerate(pairs):
  A=int(a['index']);B=int(b['index'])
  for seq,name in (((A,B),'AB'),((B,A),'BA'),((A,A),'AA'),((B,B),'BB')):
   tasks.append((f'within_{group}',name,seq))
 for j in range(3):
  A=int(pairs[j][0]['index']);B=int(pairs[j+1][0]['index'])
  tasks.extend([(f'across_{j}','AB',(A,B)),(f'across_{j}','BA',(B,A))])
 reports={};snapshots={};max_rew=0
 for group,order,seq in tasks:
  f,rews,level=rollout(seq)
  key=group+'_'+order
  reports[key]={'indices':list(seq),'xy':[xy(i) for i in seq],
   'causal_diff_vs_2_neutral':diff(f[-1],base),
   'frameSHA_without_header':digest(f[-1]),
   'native_reward_events':sum(rews),'levels_completed':level}
  snapshots[key]=f[-1]
  max_rew=max(max_rew,sum(rews))
  print('E085_OPERATOR_TEST',json.dumps({'key':key,**reports[key]},sort_keys=True),flush=True)
 relations=[]
 for g in list(range(4))+['across_'+str(i) for i in range(3)]:
  group='within_'+str(g) if isinstance(g,int) else g
  AB=snapshots[group+'_AB'];BA=snapshots[group+'_BA']
  result={'group':group,'AB_BA_noncommutativity_pixels':diff(AB,BA),
   'AB_reversal_distance_from_neutral':diff(AB,base),
   'BA_reversal_distance_from_neutral':diff(BA,base)}
  if group.startswith('within_'):
   result['AA_effect_vs_neutral']=diff(snapshots[group+'_AA'],base)
   result['BB_effect_vs_neutral']=diff(snapshots[group+'_BB'],base)
  relations.append(result)
  print('E085_ALGEBRA',json.dumps(result,sort_keys=True),flush=True)
 with (out/'E085_OPERATOR_FACTORIZATION.json').open('x') as f:
  json.dump({'kind':'E085_CAUSAL_OPERATOR_ALGEBRA_ONE_GAME',
    'tested_game':'vc33','seven_active_bottom_controls_confirmed_in_E084':True,
    'source_E084_sha256':hashlib.sha256(E084.read_bytes()).hexdigest(),
    'prefix_anchor_sha256':END_SHA,'controlled_interventions':len(reports),
    'reference_two_neutral_clicks':list([nidx,nidx]),
    'all_controls_discovered_by_color_component_analysis':True,
    'heldout_opened':False,'trajectory_prefix_is_scientific_control_not_deployable_policy':True,
    'results':reports,'structural_relations':relations,'max_native_reward':max_rew},f,indent=2)
 print('E085_ALGEBRA_COMPLETED',str(out),'relations',json.dumps(relations),flush=True)
if __name__=='__main__':main()
