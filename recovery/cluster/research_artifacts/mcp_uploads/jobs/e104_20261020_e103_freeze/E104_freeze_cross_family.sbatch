#!/bin/bash
#SBATCH --job-name=E104_unseen_evidence_freeze
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import hashlib,json,zipfile
H=Path('/home-mscluster/astrauss')
D=H/'e103_cross_family_holdout/E103_three_game_frozen_71979'
J=H/'research_artifacts/mcp_uploads/jobs'
Z=H/'E103_FROZEN_CROSS_FAMILY_HOLDOUT_20261020.zip'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
sources={
 'SOURCE/E097_FROZEN_CORE.py':(J/'e097_20261020_clean_ablation_v3/E097_clean_core_v3.py',
  'bd30c53e7abe5b63424aec23b949a685822c4ae3c9d89920ab5ed203c199a279'),
 'SOURCE/E075_BASELINE.py':(J/'e075_20261019_onegame_capability/E075_vc33_capability_v2.py',
  'ba7f315eca0ff1f75c185effa6144fda33823941a411aadae90026f191af70c7'),
 'SOURCE/E103_UNSEEN_HARNESS_V2.py':(J/'e103_20261020_cross_family_v4/E103_cross_game_eval_v2.py',
  'e49ed3ff37a50cedd32959ba4e815d7d379eab1d83f378efeabdf4414b88520f'),
 'SLURM/E103_EVALUATION.sbatch':(J/'e103_20261020_cross_family_v4/E103_unseen_three_games.sbatch',
  'd2f394975799e36b06370be0e99cf41250ca31cd48b346382cd3c3bbaa3a9ee1')}
for name,(p,expected) in sources.items():
 assert p.is_file() and digest(p)==expected,(name,str(p))
proto_path=D/'PREREGISTRATION_BEFORE_ANY_TEST_FRAME.json'
res_path=D/'E103_ALL_GAME_RESULTS.json'
proto=json.loads(proto_path.read_text())
res=json.loads(res_path.read_text())
assert proto['test_families']==['bp35','ka59','ls20']
assert proto['reserved_unopened']==['cn04','lp85','m0r0','r11l','sk48']
assert proto['source_sha256']['frozen_E097']==sources['SOURCE/E097_FROZEN_CORE.py'][1]
assert proto['source_sha256']['E103_runner']==sources['SOURCE/E103_UNSEEN_HARNESS_V2.py'][1]
assert res['completed_trials']==36 and res['errored_trials']==0
assert res['expected_trials']==36 and len(res['results'])==36
games=['bp35','ka59','ls20']
seeds=[28901,28902,28903]
modes=['full','full_from_reset','frozen_repeat','uniform_type_random']
files={'PROTOCOL/PREREGISTERED_BEFORE_ANY_GAME_FRAME.json':proto_path,
       'RESULTS/E103_ALL_GAME_RESULTS.json':res_path}
for name,(p,_) in sources.items():files[name]=p
outcomes={};stage_count={}
for g in games:
  outcomes[g]={}
  for mode in modes:outcomes[g][mode]=[]
  for seed in seeds:
   first_hashes=set()
   for mode in modes:
    matches=[r for r in res['results'] if r.get('game')==g and
      r.get('seed')==seed and r.get('mode')==mode]
    assert len(matches)==1,(g,seed,mode)
    r=matches[0]
    assert 'error_class' not in r and r['actions_charged']==160
    assert r['native_levels']==0 and r['native_sdk_score']==0
    assert r['frozen_E097_decisions']==0
    assert r['policy_core_source_SHA256']==sources['SOURCE/E097_FROZEN_CORE.py'][1]
    assert r['first_frame_SHA256'] and r['explicit_policy_decisions']>0
    assert r['only_sdk_observation_and_legal_actions_for_decision']
    prefix=f'NATIVE_TRACES/{g}/seed_{seed}/{mode}'
    folder=D/g/str(seed)/mode
    for target,actual in [('result.json','result.json'),
      ('observed_actions.jsonl','observed_actions.jsonl'),('frames.npz','frames.npz')]:
      path=folder/actual
      assert path.is_file(),str(path)
      files[f'{prefix}/{target}']=path
    assert digest(folder/'observed_actions.jsonl')==r['trajectory_SHA256']
    assert digest(folder/'frames.npz')==r['frames_SHA256']
    first_hashes.add(r['first_frame_SHA256'])
    outcomes[g][mode].append(r['native_levels'])
    stage_count[(g,mode)]=int(r['game_total_levels'])
   assert len(first_hashes)==1,(g,seed,first_hashes)
assert len(files)==114,len(files)
manifest={name:{'sha256':digest(p),'bytes':p.stat().st_size}
 for name,p in sorted(files.items())}
readme='''E103 PREREGISTERED CROSS-FAMILY HOLDOUT RESULTS — 20 Oct 2026

Scientific question: does the exact E097 policy developed on public game vc33
transfer to bp35, ka59, ls20 without changing code or using source/solutions?

Answer: NO. 36/36 native games completed with ZERO native level advances.
Each of 3 game families x 3 policy random seeds x 4 fixed arms received 160
native scorer actions, with exact family-level seed-matched starting frames.
All 36 had a native SDK score of 0 and NO E097 causal-planner decisions.

Arms: original E097 stage>=2 gate; E097 from first observation;
frozen E075 event-repeat; legal type-uniform random actions.

Root cause directly observed in traces: original E097 never reaches stage>=2
on any chosen cross-family game. Even forced from reset, the scene parser
produces no E097 control candidates, so execution falls back to E075.
This is a front-end interface/affordance discovery failure, not evidence of
a failed A* plan on another game (A* did not run).
Freeze the E097 controller; do not tune after looking at this test.

CAVEATS:
- The wider ARC-AGI-3 research project historically studied ALL 25 public
  game families, including these three. 'Unseen' here means held out from
  E097 design and tuning, NOT globally new, not an official private Kaggle
  score, and not a pristine zero-shot benchmark.
- Five E074 protected prospective source tests cn04 lp85 m0r0 r11l sk48
  were NOT instantiated by E103 and remain closed for that separate study.
- Each game has one fixed scenario with policy RNG varied 3 times; this is
  NOT three independent map/layout instances.
- The E097 3/7 vc33 advance at action 122 was independently revalidated
  before any cross-family game was opened.

Evidence: policy and runner SHA256, preregistration timestamp, every
episode's full legal action trace, native observation frames, and SDK native
advancement events are in this archive; file hashes are in SHA256_MANIFEST.
No source was modified or previous research directories deleted.
'''
counts={g:{m:outcomes[g][m] for m in modes} for g in games}
summary={'kind':'E104_FREEZE_OF_E103_PREREGISTERED_CROSS_GAME_EVALUATION',
 'cross_game_results':counts,
 'total_trials':36,'native_game_level_advances':0,
 'planner_control_decisions_total':0,
 'game_total_levels':{g:stage_count[(g,'full')] for g in games},
 'comparators':modes,
 'parent_code_frozen':True,
 'reserve_five_unopened':proto['reserved_unopened'],
 'this_is_not_globally_unseen':True,
 'all_sources_sha256_match':True,'all_native_trace_sha256_match':True}
if Z.exists():raise FileExistsError('Never overwrite or delete existing evidence '+str(Z))
with zipfile.ZipFile(Z,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 z.writestr('README_START_HERE.txt',readme)
 z.writestr('E103_SUMMARY_VERIFIED.json',json.dumps(summary,indent=2))
 z.writestr('SHA256_MANIFEST.json',json.dumps(manifest,indent=2))
 for name,p in sorted(files.items()):z.write(p,arcname=name)
with zipfile.ZipFile(Z) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)+3
print('E104_FROZEN_CROSS_FAMILY_EVIDENCE',json.dumps({
 'zip_path':str(Z),'SHA256':digest(Z),'bytes':Z.stat().st_size,
 'file_count':len(files)+3,'all_results':counts,
 'game_total_levels':summary['game_total_levels'],
 'total_native_advances':0,'planner_decisions':0},sort_keys=True),flush=True)
PY