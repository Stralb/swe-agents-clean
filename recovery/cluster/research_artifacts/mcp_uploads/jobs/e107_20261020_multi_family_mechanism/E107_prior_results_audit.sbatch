#!/bin/bash
#SBATCH --job-name=E107_e106_frozen_audit
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import defaultdict
import json,hashlib
HOME=Path('/home-mscluster/astrauss')
sources={
 'pilot':HOME/'e106_multifamily_development/E106_pilot_five_games_72009/E106_EVALUATION_RESULT.json',
 'dev_extra':HOME/'e106_multifamily_replications/E106_five_game_replication_72014/E106_EVALUATION_RESULT.json',
 'cross_validation':HOME/'e106_crossfamily_validation/E106_frozen_cross_game_72015/E106_EVALUATION_RESULT.json'}
by=defaultdict(dict);studies={}
for name,file in sources.items():
 d=json.loads(file.read_text())
 assert d['failed']==0 and d['completed']==d['expected']
 for row in d['results']:
  key=(row['game'],int(row['policy_seed']),row['mode'])
  assert key not in by[name],key
  by[name][key]=row
 studies[name]={'count':len(d['results']),
    'native_advances':sum(x['native_levels'] for x in d['results']),
    'reward_episodes':sum(x['native_levels']>0 for x in d['results'])}
 print('E107_PREVIOUS_FROZEN',name,json.dumps(studies[name]),flush=True)
families=['sb26','s5i5','lf52','tn36','g50t']
validation=['bp35','ka59','ls20']
for game in families+validation:
 recs=[]
 for seed in (28901,28902,28903):
  a=by['pilot'] if seed==28901 and game in families else by['dev_extra'] if game in families else by['cross_validation']
  full=a[(game,seed,'full')]
  repeat=a[(game,seed,'event_repeat')]
  random=a[(game,seed,'type_random')]
  recs.append([full['native_levels'],repeat['native_levels'],random['native_levels']])
 print('E107_GAME_GROUP_AGGREGATE',json.dumps({'game':game,'scores_by_seed':recs,
 'full_progress_seeds':sum(x[0]>0 for x in recs),
 'baseline_progress_seeds':sum(x[1]>0 for x in recs),
 'all_episodes_identical_start_sha':len(set(
   (by['pilot'] if seed==28901 and game in families else by['dev_extra'] if game in families else by['cross_validation'])[(game,seed,'full')]['first_frame'] for seed in (28901,28902,28903)))==1},
 sort_keys=True),flush=True)
print('E107_E106_AUDIT_FINISHED',flush=True)
PY