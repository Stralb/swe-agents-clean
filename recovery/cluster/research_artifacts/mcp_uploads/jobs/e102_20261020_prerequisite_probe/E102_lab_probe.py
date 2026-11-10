#!/usr/bin/env python3
"""E102 causal prerequisite intervention on previously studied vc33 Stage 4.
A recorded earlier-stage prefix initializes IDENTICAL laboratory states only.
Never feed any of these actions as an autonomous policy; no game source/oracle.
Question: can another observable button B re-enable control A after A stalls?
Compare A,B,A against A,B,neutral; record exact third-frame contrast.
"""
import os,sys,json,hashlib,importlib.util,logging
from pathlib import Path
from collections import Counter
import numpy as np
logging.disable(logging.INFO)
P=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e090_20261020_temporal_control/E090_stage4_control_v0.py')
EXP='08c8e7f5db0cc53d767a029df302ac850eb1c176d7820328597ea657446ef63d'
assert hashlib.sha256(P.read_bytes()).hexdigest()==EXP
spec=importlib.util.spec_from_file_location('e090_frozen',P)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
from src.adapter import N_SIMPLE
def left_marker(frame):
 p=e.m.components(frame)
 u=[x for x in p.get(11,[]) if 5<=x['size']<=18]
 if len(u)<2:return None
 L=min(u,key=lambda q:q['x']);R=max(u,key=lambda q:q['x'])
 return round(L['y']-R['y'],2)
def vector(frame):
 a=np.asarray(frame,dtype=np.int8)
 return {'marker_y_offset':left_marker(frame),
  'black_columns':[int((a[3:58,x]==0).sum()) for x in (6,13,28,43,55)],
  'blue_counts':[int((a[:,x]==1).sum()) for x in (13,28)],
  'changed_after_discrete_click':None}
def run(seq):
 s=e.origin()
 assert s.tracker.high_water==3
 obs=[np.asarray(s.obs.frame,dtype=np.int8).copy()];rewards=[]
 for xy in seq:
  idx=N_SIMPLE+xy[1]*64+xy[0]
  if not s.obs.mask[idx]:raise ValueError('illegal observed action '+str(xy))
  t=s.step(idx)
  obs.append(np.asarray(t.next_obs.frame,dtype=np.int8).copy())
  rewards.append(float(t.reward))
 return obs,rewards,int(s.tracker.high_water)
def main():
 from src.e027.reproducibility import install_reproducibility
 install_reproducibility()
 dst=Path('/home-mscluster/astrauss/e102_single_game_prerequisite')/('E102_'+os.environ['SLURM_JOB_ID'])
 if dst.exists():raise FileExistsError(dst)
 dst.mkdir(parents=True)
 ctrl=e.candidate_sites(e.origin().obs)
 assert len(ctrl)==6
 A=ctrl[0];neutral=(32,16)
 initial,rewards,_=run([A,A,A])
 initial_vec=[vector(x) for x in initial]
 print('E102_PRETEST_REPEATED_A',json.dumps({'control_A':A,'state_vectors':initial_vec,
  'native_rewards':rewards},sort_keys=True),flush=True)
 records=[]
 for B in ctrl[1:]:
  aa,ra,lvla=run([A,B,A])
  bb,rb,lvlb=run([A,B,neutral])
  for i in range(3):
   assert np.array_equal(aa[i],bb[i]),'Matched-prefix replay divergence!'
  diff=int((aa[-1]!=bb[-1]).sum())
  u={'tested_B':B,'third_A_causal_difference_vs_neutral':diff,
     'A_B_A_final':vector(aa[-1]),'A_B_neutral_final':vector(bb[-1]),
     'A_B_before_second_A':vector(aa[-2]),
     'A_first_effect':vector(aa[1]),
     'A_reenabled':bool(diff>=15),'net_marker_progress_after_A_B_A':
       None if left_marker(aa[-1]) is None or left_marker(aa[0]) is None else
       round(left_marker(aa[0])-left_marker(aa[-1]),2),
     'native_reward':[ra,rb],'native_level':[lvla,lvlb]}
  records.append(u);print('E102_MATCHED_PREREQUISITE_TEST',json.dumps(u,sort_keys=True),flush=True)
 out={'experiment':'E102_LEVEL4_PRECONDITION_CAUSAL_RESTORATION',
  'one_studied_game':'vc33','nonautonomous_lab_reset_uses_E088_trajectory':True,
  'native_initial_level':3,'controls_derived_only_from_pixels':True,
  'parent_E090_sha256':EXP,'goals_not_assumed':True,
  'heldout_games_opened':False,'results':records}
 with (dst/'E102_CAUSAL_PREREQUISITES.json').open('x') as f:json.dump(out,f,indent=2)
 print('E102_COMPLETED',str(dst/'E102_CAUSAL_PREREQUISITES.json'),flush=True)
if __name__=='__main__':main()
