#!/bin/bash
#SBATCH --job-name=E080_three_seed_freeze
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json,statistics,zipfile
H=Path('/home-mscluster/astrauss')
W=H/'e080_course_development'
S=H/'research_artifacts/mcp_uploads/jobs/e080_20261019_online_rl_options/E080_native_option_prior_v0.py'
E078=H/'E078_THREE_SEED_COURSE_EVIDENCE_20261019.zip'
E075=H/'E075_TEAM_DEMO_WITH_VISUAL_20261019.zip'
K=H/'research_artifacts/mcp_uploads/jobs/e079_20261019_kaggle_contract/my_agent.py'
DEST=H/'E080_COMPLETE_MODULE_EVIDENCE_20261019.zip'
SOURCE_HASH='60c64687a4eed82dd3c0ed776241c65c43c2f945988e76ecb96a05bd0f40e7fd'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1<<20):h.update(b)
 return h.hexdigest()
assert sha(S)==SOURCE_HASH
assert sha(E078)=='5c7eb96195296f8a516c10811bf18a159297f58d17c4389454fcf1d0cd3800a7'
assert sha(E075)=='589efecb375d7060e3cf42641e00bf4eada7b9835bbdb0c7b783820b6390937a'
assert sha(K)=='2702a91dfd56423776dd7fd5db641e5e492c22b81260d2c0e31c159090b4f989'
SEEDS={28901:'E080_native_seed28901_71820',28902:'E080_native_seed28902_71822',28903:'E080_native_seed28903_71822'}
files={'SOURCE/E080_native_option_prior_v0.py':S,
 'SOURCE/E079_Kaggle_heuristic_my_agent.py':K,
 'PRIOR_EVIDENCE/E078_THREE_SEED_COURSE_EVIDENCE_20261019.zip':E078,
 'PRIOR_EVIDENCE/E075_TEAM_DEMO_WITH_VISUAL_20261019.zip':E075}
for name,relative in [
 ('E080_native_pilot.sbatch','e080_20261019_online_rl_options/E080_native_pilot.sbatch'),
 ('E080_two_seed_replication.sbatch','e080_20261019_two_seed_replication/E080_replicate_two_seeds.sbatch'),
 ('E080_unit_test.sbatch','e080_20261019_online_rl_options/E080_unit_test.sbatch')]:
 files['SOURCE/'+name]=H/'research_artifacts/mcp_uploads/jobs'/relative
rows=[]
for seed,dirname in SEEDS.items():
 d=W/dirname
 report=d/'E080_RESULTS.json'
 data=json.loads(report.read_text())
 assert data['kind']=='E080_OPTION_RL_ONE_GAME_NATIVE_PILOT'
 assert data['code_sha256']==SOURCE_HASH
 assert data['public_development_game']=='vc33' and not data['heldout_game_instantiated']
 results=data['methods']
 assert {(r['algo'],r['online_updated']) for r in results}=={('dqn',True),('dqn',False),('ppo',True),('ppo',False)}
 for row in results:
  assert row['seed']==seed and row['budget']==160 and row['game']=='vc33'
  expected=0 if not row['online_updated'] else (18 if row['algo']=='dqn' else 20)
  assert row['gradient_updates']==expected
  check=Path(row['checkpoint'])
  assert check.is_file(),check
  files[f'NATIVE/seed{seed}/'+check.parent.name+'/checkpoint.pt']=check
  record=check.parent/'record.json'
  actions=check.parent/'actions.npy'
  assert record.is_file() and actions.is_file()
  raw=json.loads(record.read_text())
  assert raw['official_score']['score']==row['native_sdk_score']
  assert raw['counters']['high_water']==row['levels']
  assert raw['learner']['gradient_steps']==expected
  files[f'NATIVE/seed{seed}/'+check.parent.name+'/record.json']=record
  files[f'NATIVE/seed{seed}/'+check.parent.name+'/actions.npy']=actions
  rows.append(row)
 files[f'NATIVE/seed{seed}/E080_RESULTS.json']=report
summary=[]
for algo in ('dqn','ppo'):
 for updated in (True,False):
  vals=sorted([r for r in rows if r['algo']==algo and r['online_updated']==updated],key=lambda x:x['seed'])
  assert [x['seed'] for x in vals]==[28901,28902,28903]
  scores=[x['native_sdk_score'] for x in vals]
  levels=[x['levels'] for x in vals]
  summary.append({'algo':algo,'training_enabled':updated,
   'levels_by_seed':levels,'mean_native_levels':statistics.mean(levels),
   'scores_by_seed':scores,'mean_native_score':statistics.mean(scores),
   'gradient_steps_per_seed':[v['gradient_updates'] for v in vals],
   'causal_option_activations_per_seed':[v['option_prior_enabled_when_effectful'] for v in vals],
   'native_game':'vc33','validation':'same 3 policy seeds, same game seed, 160 scorer actions'})
for row in summary:
 print('E080_THREE_SEED_AGGREGATE',json.dumps(row,sort_keys=True),flush=True)
readme='''# ARC-AGI-3: E074 -> E080 verified course + research evidence, 19 Oct 2026

## Start here
Prior hand-coded procedural controller E075: 2/7 levels in all 3 seeds in
previously exposed game vc33. No trained neural RL updates or generalization.

E078: two genuinely trained algorithms (Double DQN / PPO) and two incremental
candidate improvements: I1 local-effect reward, I2 I1 plus object click
masking. Native vc33 three-seed tests with 160 actions. DQN V0/I1/I2 0/7
in all seeds. PPO I2 1/7 on one seed; PPO I2 no-grad 1/7 on another seed.
Real gradient updates and original native score preserved. E078 complete
checkpoints and source are INSIDE nested E078 ZIP.

E080: I3 explicit effect-terminated repetition on top of I2.
DQN repeats last click after substantial visual effects; PPO uses same
observation-conditioned click/type prior in both action sampling and PPO
likelihood updates (no off-policy imitation). No human teacher, no privileged
game state and no extra heldout games. Source SHA and source included.
Results per 3 seeds from real native SDK (7 levels total):
                seed28901 seed28902 seed28903     mean
DQN I3 learn        2         1         1         1.333
DQN I3 no-grad      1         1         1         1.000
PPO I3 learn        0         1         2         1.000
PPO I3 no-grad      1         1         2         1.333

No compelling evidence gradient learning caused native progress.
DQN trained only outperformed its no-grad control on one seed.
PPO no-grad outperformed trained PPO overall. This is an informative
negative result; the effect-triggered procedure prior does help.

***IMPORTANT REPLAY LIMITATION***
E080 checkpoint.pt saves only neural weights/optimizer states. E080
behavior depends on external OptionIntervention code and reapplication
of PPO logit modifiers. Do not present .pt alone as deployable policy.

One-game training/evaluation, not heldout transfer or Kaggle leaderboard
performance. Kaggle candidate heuristic E079 is tested in the Agents
framework on vc33, reaching 2/7 (job71811), but NO live Kaggle submission,
not a trained RL architecture. E079 exact agent source included. For a
working starter notebook, use previously created
E078_E079_KAGGLE_CANDIDATE_20261019.zip (separate local artifact).

Preserve all original files; this is a read-only copy into NEW archive.
University RL assignment additionally requires documented evaluation,
Kaggle scored submission evidence, RLC2026 report <=8 pages,
Paper Track participation and reproducible notebook.
Kaggle entry/team-merger deadline reportedly 26 Oct 2026; Moodle final
27 Oct 2026 23:59 SAST; verify rules before submission.
No anonymized or user API keys included.
'''
if DEST.exists():raise FileExistsError('No existing archive will be overwritten '+str(DEST))
manifest={p:{'sha256':sha(source),'bytes':source.stat().st_size} for p,source in sorted(files.items())}
with zipfile.ZipFile(DEST,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 z.writestr('README_START_HERE.md',readme)
 z.writestr('E080_AGGREGATES.json',json.dumps({'experiment':'E080','source_sha256':SOURCE_HASH,
  'game':'vc33','game_seed':0,'policy_seeds':list(SEEDS),'results':summary,
  'heldout_games_opened':False,'training_causality_established':False},indent=2))
 z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
 for name,path in sorted(files.items()):z.write(path,name)
with zipfile.ZipFile(DEST) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)+3
print('E080_MODULE_EVIDENCE_ARCHIVE',str(DEST),'bytes',DEST.stat().st_size,
 'sha256',sha(DEST),'files',len(files)+3,flush=True)
PY