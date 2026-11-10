#!/bin/bash
#SBATCH --job-name=E078_freeze_archive
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import defaultdict
import csv,hashlib,io,json,statistics,zipfile,os
H=Path('/home-mscluster/astrauss')
P=H/'RL-ARC-AGI-3-Project'
R=H/'e078_course_recovery'
STAGE=H/'research_artifacts/mcp_uploads/jobs'
S=STAGE/'e078_20261019_six_version_native/E078_six_version_native_v0.py'
SHA='dcb59636a9ffd7319ebd0a2ec692cd20200532845f00d6be1caba6927c6d0fd3'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1<<20):h.update(b)
 return h.hexdigest()
assert sha(S)==SHA
runs=((28901,'E078_native_vc33_160_seed28901_71805'),(28902,'E078_native_vc33_160_seed28902_71808'),(28903,'E078_native_vc33_160_seed28903_71808'))
rows=[];files={}
files['SOURCE/E078_six_version_native_v0.py']=S
for name in ('adapter.py','model.py','dqn.py','ppo.py','config.py','run.py','synthetic.py','learner.py'):
 files['SOURCE/original_Wits_src/'+name]=P/'src'/name
files['SOURCE/E078_native_pilot_seed28901.sbatch']=STAGE/'e078_20261019_six_version_native/E078_native_pilot_seed28901.sbatch'
files['SOURCE/E078_two_extra_seeds.sbatch']=STAGE/'e078_20261019_three_seed_eval/E078_two_extra_seeds.sbatch'
files['SOURCE/E078_two_algo_smoke.sbatch']=STAGE/'e078_20261019_two_algo_smoke/E078_two_algo_smoke.sbatch'
files['SOURCE/frozen_e075_candidates.py']=STAGE/'e075_20261019_onegame_capability/E075_vc33_capability_v2.py'
for seed,dirname in runs:
 directory=R/dirname
 report=directory/'E078_REPORT.json'
 if not report.is_file():raise FileNotFoundError(report)
 contents=json.loads(report.read_text())
 assert contents['source_sha256']==SHA and contents['arc_environment']=='vc33'
 assert contents['seed']==seed and contents['budget']==160
 assert contents['heldout_gamelist_closed']==['cn04','lp85','m0r0','r11l','sk48']
 per=contents['rows']
 assert len(per)==8
 modes={(r['algo'],r['stage'],r['disabled_gradient']) for r in per}
 assert len(modes)==8
 files[f'NATIVE/seed{seed}/E078_REPORT.json']=report
 for record in per:
  assert record['game']=='vc33' and record['seed']==seed and record['env_seed']==0
  assert record['scorer_actions']==160 and record['environment_commands']>=160
  assert record['status']=='budget' and record['official_sdk_score'] is not None
  expected=0 if record['disabled_gradient'] else (18 if record['algo']=='dqn' else 20)
  assert record['gradient_steps']==expected,(seed,record['algo'],record['stage'],record['gradient_steps'])
  rp=directory/record['run_id']/'record.json'
  ck=Path(record['checkpoint_path'])
  act=directory/record['run_id']/'actions.npy'
  assert rp.is_file() and ck.is_file() and act.is_file()
  native=json.loads(rp.read_text())
  assert native['identity']['run_id']==record['run_id']
  assert native['identity']['config_hash']==record['config_sha']
  assert native['official_score']['score']==record['official_sdk_score']
  assert native['learner']['gradient_steps']==record['gradient_steps']
  for file in (rp,ck,act):
   files[f'NATIVE/seed{seed}/'+record['run_id']+'/'+file.name]=file
  rows.append({k:record[k] for k in ('algo','stage','disabled_gradient','seed','budget',
    'scorer_actions','environment_commands','reset_count','native_levels','official_sdk_score',
    'gradient_steps','native_rewarded_transitions','intrinsic_reward_sum','novel_effect_signatures',
    'duration_s','run_id','config_sha','checkpoint_path')})
for d in (R/'synthetic_smoke_71801').glob('*'):
 if d.is_dir():
  for file in sorted(d.iterdir()):
   if file.suffix in ('.json','.npy','.pt'):
    files['SYNTHETIC/'+d.name+'/'+file.name]=file
for seed,dirname in ((28901,'E075_VC33_71743'),(28902,'E075_VC33_71744_seed28902'),(28903,'E075_VC33_71744_seed28903')):
 file=H/'e075_one_game_runs'/dirname/'E075_REPORT.json'
 assert file.is_file()
 files[f'E075_HANDDESIGNED_REFERENCE/seed{seed}_REPORT.json']=file
assert len(rows)==24
table=defaultdict(list)
for r in rows:table[(r['algo'],r['stage'],r['disabled_gradient'])].append(r)
summary=[]
for key,series in sorted(table.items()):
 assert len(series)==3
 scores=[r['official_sdk_score'] for r in series]
 levels=[r['native_levels'] for r in series]
 summary.append({'algorithm':key[0],'stage':key[1],'updates_disabled':key[2],
  'native_levels_per_seed':levels,'mean_native_levels':statistics.mean(levels),
  'native_scores_per_seed':scores,'mean_native_score':statistics.mean(scores),
  'mean_gradient_steps':statistics.mean([r['gradient_steps'] for r in series]),
  'mean_wall_seconds':statistics.mean([r['duration_s'] for r in series]),
  'mean_intrinsic_bonus':statistics.mean([r['intrinsic_reward_sum'] for r in series])})
assert len(summary)==8
for s in summary:print('E078_THREE_SEED_AGGREGATE',json.dumps(s,sort_keys=True),flush=True)
out=H/'E078_THREE_SEED_COURSE_EVIDENCE_20261019.zip'
if out.exists():raise FileExistsError('No archive replacement allowed: '+str(out))
fields=list(rows[0])
buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader();writer.writerows(rows)
manifest={name:{'sha256':sha(file),'bytes':file.stat().st_size} for name,file in sorted(files.items())}
discussion='''# E078 research and course evidence (19 October 2026)
Source: original Wits src.dqn and src.ppo (unchanged); E078 intervention wrapper source included.
Methods: Double DQN/epsilon type-uniform and PPO/GAE, real online updates during
evaluation. V0 baseline; I1 novel-action-effect intrinsic training reward, I2 adds
connected-component click proposal masking. Native high-water rewards and SDK
scorecard always stay unchanged. This is a single historically exposed development
game vc33; 160 scorer actions; 3 independent learner/policy seeds 28901-28903,
same environment seed 0. It is not proof of held-out generalization.
All versions have real training updates: DQN 18 and PPO 20 per run.
Two no-gradient I2 controls are included (one per algorithm).
The key limitation is sparse interactive reward and weak click grounding.
Synthetic click-task controls validated DQN and PPO objectives separately.
Results: all DQN arms 0 levels; both PPO V0/I1 0; trained PPO I2 1 level only
on seed 28902; no-gradient PPO I2 1 level only on seed 28901.
Mean levels of trained PPO I2 and its no-grad control are both 1/3, with
different success seeds. Improvement due to learning is NOT established.
E075 hand-coded event repetition 2 native levels in each of three seeds:
explicitly NOT a trained RL algorithm, and no hidden-game score claim.
No online Kaggle leaderboard submission was made by these Slurm jobs.
Course deliverables still need RLC report (<=8 main pages), Kaggle code submission
and its ID/time/score, Paper Track entry, team membership/contributions.
Competition entry and merger deadline in supplied rules: 26 October 2026,
and university Moodle deadline: 27 October 2026 23:59 SAST.
No archived logs containing anonymous API credentials are included.
All files were copied into NEW evidence ZIP without changing originals.
'''
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 z.writestr('README_E078.md',discussion)
 z.writestr('E078_SUMMARY.json',json.dumps({'kind':'E078_THREE_SEED_VERIFIED',
    'source_sha256':SHA,'scores':summary,'experiment_repeats':3,
    'scored_game':'vc33','heldout_opened':False},indent=2))
 z.writestr('E078_ALL_NATIVE_RUNS.csv',buf.getvalue())
 z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
 for name,p in sorted(files.items()):z.write(p,name)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)+4
print('E078_ARCHIVE_FROZEN',str(out),'bytes',out.stat().st_size,'sha256',sha(out),
 'archived_files',len(files)+4,flush=True)
PY