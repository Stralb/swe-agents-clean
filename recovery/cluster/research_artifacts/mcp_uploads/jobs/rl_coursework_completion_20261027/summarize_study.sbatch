#!/bin/bash
#SBATCH --job-name=rl-study-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
#SBATCH --dependency=afterany:76239
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027
python3 - "$ROOT" <<'PY'
from pathlib import Path
import collections,csv,json,statistics,sys
p=Path(sys.argv[1]); o=p/'analysis';o.mkdir(exist_ok=True)
rows=[];curves=[]
for f in sorted((p/'records').glob('*.json')):
 try:
  d=json.loads(f.read_text());s=d['study'];sc=d.get('official_score') or {};L=d['learner'];co=d['cost'];cc=d['counters']
  row={'algo':s['algorithm'],'arm':s['arm'],'game':s['game'],'policy_seed':s['policy_seed'],
     'native_seed':s['native_seed'],'status':d['status'],'error':d['error'] or '',
     'score':sc.get('score',''),'levels':sc.get('levels_completed',''),
     'actions':cc['scorer_actions'],'gradient_steps':L.get('gradient_steps',0),
     'wall_s':co['wall_s'],'peak_rss_mb':co['peak_rss_mb'],
     'bonus':L.get('intrinsic_bonus',0),'rescue_decisions':L.get('rescue_decisions',0),
     'click_masked_states':L.get('masked_states',0),
     'frame_change_rate':d['diagnostics']['frame_change_rate'],
     'first_reward_action':d['diagnostics']['first_reward_action'] or ''}
  rows.append(row)
  events=d['diagnostics']['progress_curve']
  for t in range(0,257,32):
   level=max((int(level) for at,level in events if at<=t),default=0)
   curves.append({'algo':s['algorithm'],'arm':s['arm'],'game':s['game'],
     'seed':s['policy_seed'],'charged_action_cutoff':t,'levels_reached':level})
 except Exception as e:
  print('RECORD_FAIL',f,str(e),flush=True)
expected={(a,v,g,s) for a in ('dqn','ppo') for v in ('V0','I1','I2') for g in ('ar25','g50t','s5i5','vc33') for s in (301,302,303)}
actual={(x['algo'],x['arm'],x['game'],x['policy_seed']) for x in rows}
missing=sorted(expected-actual)
for filename,data in [('per_run.csv',rows),('curve.csv',curves)]:
 if data:
  with (o/filename).open('w',newline='') as g:
   w=csv.DictWriter(g,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
sums=[]
for a in ('dqn','ppo'):
 for v in ('V0','I1','I2'):
  z=[x for x in rows if x['algo']==a and x['arm']==v]
  ok=[x for x in z if x['error']=='' and isinstance(x['levels'],int) and isinstance(x['score'],(float,int))]
  y={'algo':a,'arm':v,'runs':len(z),'valid':len(ok),'levels':sum(x['levels'] for x in ok),
     'mean_sdk':round(statistics.mean([x['score'] for x in ok]),7) if ok else '',
     'min_sdk':round(min(x['score'] for x in ok),7) if ok else '',
     'max_sdk':round(max(x['score'] for x in ok),7) if ok else '',
     'actions':sum(x['actions'] for x in ok),'gradient_steps':sum(x['gradient_steps'] for x in ok),
     'wall_s':round(sum(x['wall_s'] for x in ok),1),
     'positive_runs':sum(x['levels']>0 for x in ok)}
  sums.append(y)
with (o/'summary.csv').open('w',newline='') as g:
 w=csv.DictWriter(g,fieldnames=list(sums[0]));w.writeheader();w.writerows(sums)
md=['# Matched six-arm ARC-AGI-3 public SDK study','',
    'Previously exposed four public games, policy seeds 301/302/303, native seed 47, 256 charged actions/run.',
    'Each run learns online from scratch in its on-policy/off-policy head. DQN V1 also has a frozen public-trained effect prior; training compute across arms is NOT matched.',
    'PPO novelty is training-only, never substituted for native scorecard reward.',
    '', '| Algorithm | Variant | Complete runs | Native levels | Mean local SDK score | Charged actions | Gradient steps |',
    '|---|---|---:|---:|---:|---:|---:|']
for s in sums:
 md.append(f"| {s['algo']} | {s['arm']} | {s['valid']}/{s['runs']} | {s['levels']} | {s['mean_sdk']} | {s['actions']} | {s['gradient_steps']} |")
md += ['', f'Missing expected run records: {len(missing)}.','',str(missing),'',
       'Curves are within-run cumulative native progression, not independent checkpoint learning curves.',
       'No claim of unseen-game transfer. Scores are local SDK v0.9.8, not Kaggle scores.']
(o/'REPORT.md').write_text('\n'.join(md)+'\n')
print('\n'.join(md),flush=True)
print('STUDY_AUDIT_COMPLETE',len(rows),len(missing),flush=True)
PY
