#!/bin/bash
#SBATCH --job-name=E075_procedure_forensic
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
"$PY" - <<'PY'
from pathlib import Path
import hashlib,json
root=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
rep=json.loads((root/'E075_REPORT.json').read_text())
assert rep['same_initial_frame'] and rep['development_game_only']=='vc33'
rows={}
for r in rep['rows']:
 p=Path(r['trace_jsonl'])
 assert hashlib.sha256(p.read_bytes()).hexdigest()==r['trace_sha256']
 rows[r['mode']]=[json.loads(line) for line in p.read_text().splitlines()]
 print('VERIFIED_TRACE',r['mode'],'rows',len(rows[r['mode']]),'hash',r['trace_sha256'],flush=True)
for mode in rows:
 rr=rows[mode]
 level=[dict(step=x['action_number'],reward=x['native_level_reward'],xy=x['xy'],
              action=x['action_id'],reason=x['reason'],effect=x['changed_fraction']) for x in rr if x['native_level_reward']>0]
 print('LEVEL_EVENTS',mode,json.dumps(level),flush=True)
for mode in ('blind_repeat','belief_verify','structured','random'):
 a=rows['repeat'];b=rows[mode];div=None
 for i,(x,y) in enumerate(zip(a,b)):
  if x['frame_sha_before']!=y['frame_sha_before'] or x['action_index']!=y['action_index']:
   div=(i,x,y);break
 if div:
  k,x,y=div
  print('FIRST_DIVERGENCE',mode,'index',k,
   'repeat_action',x['action_index'],'other_action',y['action_index'],
   'same_preframe',x['frame_sha_before']==y['frame_sha_before'],
   'repeat_reason',x['reason'],'other_reason',y['reason'],
   'repeat_progress',x['progress'],'other_progress',y['progress'],flush=True)
for name in ('repeat','blind_repeat','belief_verify'):
 rr=rows[name]
 for i,x in enumerate(rr):
  if x['native_level_reward']>0:
   print('REWARD_WINDOW',name,'step',x['action_number'],flush=True)
   for y in rr[max(0,i-3):min(len(rr),i+3)]:
    print(' TRANSITION',y['action_number'],y['action_id'],y['xy'],
     y['reason'],'effect',y['changed_fraction'],'progress',y['progress'],
     'state',y['game_state'],flush=True)
print('E075_FORENSIC_COMPLETE',flush=True)
PY