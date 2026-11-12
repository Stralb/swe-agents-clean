#!/bin/bash
#SBATCH --job-name=E106_reward_action_audit
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import json,hashlib
D=Path('/home-mscluster/astrauss/e106_multifamily_development/E106_pilot_five_games_72009')
data=json.loads((D/'E106_EVALUATION_RESULT.json').read_text())
assert data['completed']==15 and data['failed']==0
for r in data['results']:
 if r['mode']!='full':continue
 p=D/r['game']/'28901'/'full'/'native_legal_interactions.jsonl'
 trace=[json.loads(line) for line in p.read_text().splitlines()]
 events=[{k:t[k] for k in ('native_charged_actions','action_type','xy','action_reason','native_reward','native_high_water')} for t in trace if t['native_reward']>0]
 reasons=Counter(t['action_reason'] for t in trace)
 useful=Counter(t['action_reason'] for t in trace if t['observed_update'].get('effect_meaningful'))
 print('E106_MECHANISM_AUDIT',json.dumps({'game':r['game'],'levels':r['native_levels'],
  'native_score':r['native_sdk_score'],'rewarded_events':events,'all_reason_counts':dict(reasons),
  'effectful_reason_counts':dict(useful),
  'stats':r['controller_stats'],'change_predictions_evaluated':r['controller_stats'].get('predictions_evaluated',0),
  'source_only_public_mask':True},sort_keys=True),flush=True)
PY