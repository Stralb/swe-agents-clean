#!/bin/bash
#SBATCH --job-name=E075_l3_wall_audit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
import hashlib,json,collections
ROOT=Path('/home-mscluster/astrauss/e075_one_game_runs')
runs=[(28901,ROOT/'E075_VC33_71743'),(28902,ROOT/'E075_VC33_71744_seed28902'),(28903,ROOT/'E075_VC33_71744_seed28903')]
for seed,p in runs:
 d=json.loads((p/'E075_REPORT.json').read_text())
 for mode in ('repeat','blind_repeat','belief_verify','structured'):
  row=next(x for x in d['rows'] if x['mode']==mode)
  trace=Path(row['trace_jsonl'])
  assert hashlib.sha256(trace.read_bytes()).hexdigest()==row['trace_sha256']
  tr=[json.loads(s) for s in trace.read_text().splitlines()]
  levels=[t['action_number'] for t in tr if t['native_level_reward']>0]
  last=levels[-1] if levels else 0
  aft=[t for t in tr if t['action_number']>last]
  positive=[t for t in aft if t['effect']]
  changed=[t for t in aft if t['changed_fraction']>=.004]
  choices=collections.Counter(str(t['xy']) for t in aft)
  routes=collections.Counter(t['reason'] for t in aft)
  print('E075_L3_STALL',json.dumps({
   'seed':seed,'mode':mode,'level_up_steps':levels,'final_levels':row['levels_completed'],
   'actions_after_last_progress':len(aft),'effectful_after':len(positive),
   'meaningful_change_after':len(changed),
   'unique_post_progress_coordinates':len(choices),
   'top_five_post_progress_coordinates':choices.most_common(5),
   'post_progress_reason_counts':dict(routes),
   'preliminary_failure':'no additional native advancement after last level event'
  }),flush=True)
print('E075_L3_WALL_AUDIT_END',flush=True)
PY