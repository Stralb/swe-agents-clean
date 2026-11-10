#!/bin/bash
#SBATCH --job-name=E108_rotation_release
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:08:00
#SBATCH --dependency=afterok:72172
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import hashlib,json,random,zipfile
H=Path('/home-mscluster/astrauss');W=H/'e108_random_development_rounds'
S=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds'
OUT=S/'ROTATION_VERIFIED_STATUS.json';Z=H/'E108_RANDOM_FIVE_ITERATIONS_20261020.zip'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
if OUT.exists() or Z.exists():raise FileExistsError('No evidence may be overwritten')
conditions=[('1','round_01'),('2','round_02'),('3','round_03'),('4_original','round_04'),('4_corrected','round_04_immutable_frames'),('5','round_05')]
records=[];files={};families=set();total_complete=0;total_failed=0;all_cost=0.;all_actions=0;all_raw=0
for name,subdir in conditions:
 root=W/subdir;selection=json.loads((root/'SELECTION_FROZEN.json').read_text())
 report=json.loads((root/'ROUND_RESULT.json').read_text())
 assert report['expected_trials']==60 and selection['budget']==512
 assert not set(selection['selected_games']).intersection(selection['protected_families'])
 for p,h in selection['source_hashes'].items():assert sha(Path(p))==h,(name,p)
 table={g:{a:[] for a in selection['arms']} for g in selection['selected_games']}
 stats=Counter();cpu=0.;actions=0;raw=0;complete=0;error=0;scores={a:[] for a in selection['arms']}
 for game in selection['selected_games']:
  for seed in selection['policy_seeds']:
   starts=[]
   for arm in selection['arms']:
    rows=[r for r in report['results'] if r.get('game')==game and r.get('seed')==seed and r.get('arm')==arm]
    assert len(rows)==1,(name,game,seed,arm)
    r=rows[0];folder=root/game/str(seed)/arm
    if 'error' in r:
     error+=1;table[game][arm].append('ERROR');actions+=r.get('known_charged_actions',0)
    else:
     assert sha(folder/'trace.jsonl')==r['trace_sha256']
     assert sha(folder/'observations.npz')==r['frames_sha256']
     assert sha(folder/'native_scorecard.json')==r['scorecard_sha256']
     assert r['actions']==r['decisions']+r['resets']-1
     assert r['raw_commands']==r['decisions']+r['resets']
     assert r['actions']<=512
     assert json.loads((folder/'native_scorecard.json').read_text())['score']==r['score']
     complete+=1;table[game][arm].append(r['completed_levels']);scores[arm].append(r['score'])
     actions+=r['actions'];raw+=r['raw_commands'];starts.append(r['initial_frame_sha256'])
     if arm=='candidate':stats.update(r['stats'])
    cpu+=r.get('cpu_seconds',0.)
    if folder.exists():
     for p in folder.iterdir():
      if p.is_file():files[subdir+'/'+str(p.relative_to(root))]=p
   assert len(set(starts))<=1,(name,game,seed)
 assert complete==report['completed_trials'] and error==len(report['errors'])
 if name=='4_corrected':assert complete==60 and error==0
 for p in root.glob('*.json'):files[subdir+'/'+p.name]=p
 if (root/'OBSERVATION_CONTRACT.json').is_file():
  contract=json.loads((root/'OBSERVATION_CONTRACT.json').read_text())
  for p,h in contract['additional_source_hashes'].items():assert sha(Path(p))==h
 row={'condition':name,'games':selection['selected_games'],'candidate_source':selection['candidate'],
  'previous_source':selection['previous'],'completed_trials':complete,'failed_trials':error,
  'per_game_levels':table,'mean_native_sdk_score':{a:sum(v)/len(v) if v else None for a,v in scores.items()},
  'candidate_successful_trials':sum(isinstance(v,int) and v>0 for g in table for v in table[g]['candidate']),
  'candidate_total_level_advances':sum(v for g in table for v in table[g]['candidate'] if isinstance(v,int)),
  'candidate_two_level_families':sum(all(isinstance(v,int) for v in table[g]['candidate']) and sum(table[g]['candidate'])/3>=2 for g in table),
  'candidate_stats':dict(stats),'cpu_seconds_all_arms':round(cpu,3),'native_charged_actions':actions,
  'raw_commands_completed_trials':raw,'errors_retained':report['errors'],
  'result_sha256':sha(root/'ROUND_RESULT.json'),'selection_sha256':sha(root/'SELECTION_FROZEN.json'),
  'random_seed_hex':selection['random_seed_hex'],'sampling':selection['sampling'],
  'recycled_development_families':selection.get('recycled_development_families',[])}
 records.append(row);families.update(selection['selected_games']);total_complete+=complete;total_failed+=error;all_cost+=cpu;all_actions+=actions;all_raw+=raw
 print('VERIFIED_ROTATION_CONDITION',json.dumps({k:row[k] for k in ('condition','games','completed_trials','failed_trials','per_game_levels','candidate_successful_trials','candidate_total_level_advances','candidate_two_level_families')},sort_keys=True),flush=True)
for p in S.iterdir():
 if p.is_file() and p.suffix in ('.py','.sbatch'):files['source/'+p.name]=p
for name in ('E106_perception_v0.py','E106_online_explorer_v0.py'):
 files['source/'+name]=H/'research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent'/name
files['source/original_adapter.py']=H/'RL-ARC-AGI-3-Project/src/adapter.py'
files['FRAME_ALIAS_FINDINGS.json']=H/'research_artifacts/mcp_uploads/jobs/e108_20261020_frame_contract/FRAME_ALIAS_FINDINGS.json'
summary={'experiment':'E108_ROTATING_RANDOM_DEVELOPMENT','random_panels':5,'distinct_families':len(families),
 'protocol':'sources frozen before each draw; 3 policy seeds and 512 scorer actions for every arm',
 'first_three_panels_disjoint':True,'later_panels_randomly_reuse_development_games':True,
 'protected_not_opened':True,'protected_families':selection['protected_families'],
 'candidate_versions_never_receive_game_ids':True,'no_trajectory_replay_or_hidden_state':True,
 'same_layout_with_policy_randomness_not_independent_scenarios':True,
 'completed_trial_executions':total_complete,'failed_trial_executions_retained':total_failed,
 'cpu_seconds_completed_and_failed':round(all_cost,3),'known_native_actions_total':all_actions,
 'raw_commands_completed_trials':all_raw,'results':records,
 'frame_contract_fix':'public SDK buffers are copied on receipt; previous observations cannot be mutated by future steps',
 'earlier_affected_action_effect_labels_need_review':True,
 'neural_gradient_updates':0,'R4_R5_online_tabular_TD_is_not_DQN_or_PPO':True,
 'target_two_levels_in_three_families_met':any(r['candidate_two_level_families']>=3 for r in records if r['condition']!='4_original'),
 'next_action':'Inspect paired native results and mechanism activations before choosing the next generic intervention; never tune to one game or open reserved families.'}
with OUT.open('x') as f:json.dump(summary,f,indent=2)
files['ROTATION_VERIFIED_STATUS.json']=OUT
manifest={k:{'sha256':sha(p),'bytes':p.stat().st_size} for k,p in files.items()}
with zipfile.ZipFile(Z,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for k,p in sorted(files.items()):z.write(p,k)
 z.writestr('SHA256_MANIFEST.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(Z) as z:assert z.testzip() is None
print('ROTATION_EVIDENCE_ARCHIVE',json.dumps({'path':str(Z),'sha256':sha(Z),'bytes':Z.stat().st_size,
 'summary_path':str(OUT),'summary_sha256':sha(OUT),'completed':total_complete,'failed':total_failed,
 'families':len(families),'target_met':summary['target_two_levels_in_three_families_met']}),flush=True)
PY
