#!/bin/bash
#SBATCH --job-name=E101_evidence_freeze
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,zipfile,statistics
H=Path('/home-mscluster/astrauss')
J=H/'research_artifacts/mcp_uploads/jobs'
ROOT=H/'e097_clean_mechanistic_ablation'
TARGET=H/'E097_AUTONOMOUS_CAUSAL_HYPOTHESIS_VERIFIED_20261020.zip'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
originals={
 'SOURCE/E075_existing_explorer.py':J/'e075_20261019_onegame_capability/E075_vc33_capability_v2.py',
 'SOURCE/E093_greedy_core_v0.py':J/'e093_20261020_online_hypothesis/E093_online_core_v0.py',
 'SOURCE/E093_greedy_runner_v0.py':J/'e093_20261020_online_hypothesis/E093_native_runner_v0.py',
 'SOURCE/E095_ASTAR_core_v1.py':J/'e095_20261020_multistep_replanning/E095_online_core_v1.py',
 'SOURCE/E095_ASTAR_runner_v1.py':J/'e095_20261020_multistep_replanning/E095_native_runner_v1.py',
 'SOURCE/E097_orthogonal_core_v3.py':J/'e097_20261020_clean_ablation_v3/E097_clean_core_v3.py',
 'SOURCE/E097_orthogonal_runner_v3.py':J/'e097_20261020_clean_ablation_v3/E097_native_runner_v3.py',
 'SLURM/E097_three_seed.sbatch':J/'e097_20261020_clean_ablation_v3/E097_v3_three_seed.sbatch',
 'SLURM/E095_astar_unit.sbatch':J/'e095_20261020_multistep_replanning_v1/E095_unit_v1.sbatch',
 'SLURM/E096_greedy_replica.sbatch':J/'e096_20261020_greedy_replication/E096_greedy_two_seeds.sbatch',
 'OTHER/E088_native_stage3_solution_record.json':H/'e088_visual_goal_planning/E088_vc33_71867/E088_RESULT.json',
 'OTHER/E090_stage4_intervention_census.json':H/'e090_single_game_stage4_causality/E090_vc33_71874/E090_STAGE4_CAUSAL_CONTRAST.json'
}
expected_sources={
 'SOURCE/E075_existing_explorer.py':'ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7',
 'SOURCE/E095_ASTAR_core_v1.py':'ed5c36f581ee834f35f4a1ef34e8f71311487d68a8800ab529fbbee5e41b0cb0',
 'SOURCE/E097_orthogonal_core_v3.py':'bd30c53e7abe5b63424aec23b949a685822c4ae3c9d89920ab5ed203c199a279',
 'SOURCE/E097_orthogonal_runner_v3.py':'965ba7161af4b25ae4f9b42b9eb44be887380a840f6348da1f9aa3f90210bcac'
}
for name,sha in expected_sources.items():
 assert digest(originals[name])==sha,(name,digest(originals[name]))
modes=['full','no_memory','no_causal','no_goal','frozen_repeat']
runs=[];counts={}
for seed in (28901,28902,28903):
 root=ROOT/('E097_v3_seed%d_71896'%seed)
 report=root/'E097_REPORT.json'
 data=json.loads(report.read_text())
 assert data['native_game']=='vc33' and data['policy_seed']==seed and data['env_seed']==0
 assert data['authoritative_initial_state_identical'] and data['identical_exploration_until_stage3']
 assert data['E097_core_sha256']==expected_sources['SOURCE/E097_orthogonal_core_v3.py']
 assert [r['mode'] for r in data['rows']]==modes
 originals[f'E097/seed{seed}/E097_REPORT.json']=report
 for record in data['rows']:
  mode=record['mode']
  assert record['native_game']=='vc33' and record['scorer_actions']==160
  assert record['recorded_trajectories_loaded'] is False
  expected=3 if mode in ('full','no_memory') else 2
  assert record['native_levels_completed']==expected,(seed,mode)
  trace=root/(mode+'.jsonl')
  frame=root/(mode+'_frames.npz')
  assert digest(trace)==record['trace_sha256']
  assert digest(frame)==record['frames_sha256']
  originals[f'E097/seed{seed}/{mode}.jsonl']=trace
  originals[f'E097/seed{seed}/{mode}_frames.npz']=frame
  runs.append({'seed':seed,'mode':mode,'levels':expected,
   'advance_actions':[q['action'] for q in record['native_progress']],
   'native_sdk_score':record['official_native_game_score'],
   'Astar_actions':record['agent_stats'].get('astar_actions_executed',0),
   'causal_action_predictions':record['agent_stats'].get('explicit_prediction_trials',0)})
counts={m:[r['levels'] for r in runs if r['mode']==m] for m in modes}
assert counts=={'full':[3,3,3],'no_memory':[3,3,3],
 'no_causal':[2,2,2],'no_goal':[2,2,2],'frozen_repeat':[2,2,2]}
for seed,folder in (
 (28901,H/'e093_from_reset_research/E093_seed28901_full_71884'),
 (28902,H/'e093_from_reset_research/E096_greedy_replica_seed28902_71897'),
 (28903,H/'e093_from_reset_research/E096_greedy_replica_seed28903_71897')):
 p=folder/'E093_REPORT.json'
 d=json.loads(p.read_text())
 assert d['rows'][0]['native_levels_completed']==2
 originals[f'E093_GREEDY/seed{seed}/E093_REPORT.json']=p
 for name in ('full.jsonl','full_frames.npz'):
  originals[f'E093_GREEDY/seed{seed}/'+name]=folder/name
for name,p in originals.items():
 if not p.is_file():raise FileNotFoundError(str(p))
 manifest={name:{'sha256':digest(path),'bytes':path.stat().st_size}
  for name,path in sorted(originals.items())}
summary={'experiment':'E097_ONLINE_CAUSAL_GOAL_HYPOTHESES_PLUS_ASTAR',
 'one_studied_game_only':'vc33','environment_seed':0,
 'policy_seeds':[28901,28902,28903],
 'native_scorer_actions_per_run':160,
 'three_seed_native_levels':counts,'native_detail':runs,
 'controls_separate_goal_from_causal_selection':True,
 'E093_GREEDY_LEVELS':[2,2,2],
 'E097_ASTAR_GOAL_LEVELS':[3,3,3],
 'E097_MEMORY_ABLATION_IDENTICAL_OUTCOME':True,
 'NO_TRAINED_NEURAL_RL':True,
 'operator_effects_estimated_online_from_current_episode_only':True,
 'recorded_action_prefix_not_injected':True,
 'evaluation_initial_state_provenance':'one game, same env seed 0, only independent policy randomness',
 'E098_ENV_SEED_TEST_NOT_EVIDENCE_OF_GENERALIZATION':True,
 'E098_env_seed_numbers':[1,2,3],
 'E098_all_initial_hashes_identical':True,
 'unseen_game_evaluation':False,
 'full_game_wins':0,
 'not_an_official_Kaggle_submission':True}
readme='''ARC-AGI-3 E097: native research evidence freeze (20 Oct 2026)
READ E097_RESULTS.json FIRST.

Scientific claim supported:
In previously studied public game vc33 with 160 native scorer actions,
an agent starting from reset learned abstract neighbouring transfer effects
during its own legal exploration, inferred a matching-color target from
pixels, planned across multi-step prerequisites with A* (including
temporarily worse-looking actions), and advanced to level 3 in all three
policy random seeds. This improved from 2/7 for a matched greedy
goal+causal agent (E093) and from 2/7 for baseline E075.

Mechanistic controls, same three policy seeds:
full 3,3,3; no temporal memory 3,3,3;
goal-only boundary probing without using learned action dynamics 2,2,2;
causal-only uncertainty exploration without an explicit goal 2,2,2;
original event repeat 2,2,2.

Interpretation:
This is evidence for a causal-goal planning mechanism within ONE exposed
training game. It DOES NOT prove a neural RL model learned reasoning or
generalized to other games. The algorithm contains handcrafted generic
visual predicates and abstract object-transfer inductive biases.
Removing four-frame memory did not hurt this game.
No separate heldouts were instantiated.
E098 changed env_seed=1,2,3 but all start frames and traces were IDENTICAL;
it supplies zero independent environment variation, so exclude it from
robustness claims. Independent policy RNG seeds do not imply new games.
Stage 4 remains unsolved at 160 actions. E090 stage-4 causal census included.

Integrity:
Source SHA and every native trace and observed frame sequence hashed in
SHA256_MANIFEST.json. No existing cluster files were overwritten/deleted.
Any controls tagged no_causal/no_goal should be used only for the revised
E097 version3 comparison; E097 earlier v2 had a failed A* NameError.
Detailed full timestamps and outcomes are in the individual JSON reports.
Not an academic paper or a graded course submission.
'''
if TARGET.exists():raise FileExistsError('Preserving existing archive; refusing overwrite '+str(TARGET))
with zipfile.ZipFile(TARGET,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 z.writestr('README_START_HERE.txt',readme)
 z.writestr('E097_RESULTS.json',json.dumps(summary,indent=2))
 z.writestr('SHA256_MANIFEST.json',json.dumps(manifest,indent=2))
 for name,p in sorted(originals.items()):z.write(p,name)
with zipfile.ZipFile(TARGET) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(originals)+3
print('E101_EVIDENCE_FROZEN',json.dumps({'path':str(TARGET),'bytes':TARGET.stat().st_size,
 'SHA256':digest(TARGET),'files':len(originals)+3,'three_seed_levels':counts},
 sort_keys=True),flush=True)
PY