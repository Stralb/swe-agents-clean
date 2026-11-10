#!/bin/bash
#SBATCH --job-name=arc3-diagnostic
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:01:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/diag-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/diag-%j.err
set -euo pipefail
python3 - <<'PY'
import json,csv
from pathlib import Path
src=Path('/home-mscluster/astrauss/e078_course_recovery')
out=Path('out/curves');out.mkdir(parents=True,exist_ok=True)
rows=[]
for root in sorted(src.glob('E078_native_vc33_160_seed*')):
 for p in sorted(root.glob('*/record.json')):
  x=json.loads(p.read_text())
  cfg=x.get('identity',{}).get('config',{})
  l=x.get('learner',{});d=x.get('diagnostics',{});c=x.get('counters',{});cost=x.get('cost',{});sc=x.get('official_score',{})
  rows.append(dict(algo=cfg.get('algo'),version=cfg.get('version'),policy_seed=cfg.get('seed'),game=cfg.get('game'),native_seed=cfg.get('env_seed'),action_ceiling=cfg.get('budget'),sdk_charged_actions=c.get('scorer_actions'),native_levels=sc.get('levels_completed'),native_sdk_score=sc.get('score'),rewarded_transitions=d.get('rewarded_transitions'),first_native_reward_action=d.get('first_reward_action'),frame_change_rate=d.get('frame_change_rate'),unique_state_rate=d.get('unique_state_rate'),unique_states=d.get('unique_states'),repeated_state_transitions=d.get('repeated_state_transitions'),gradient_steps=l.get('gradient_steps'),updates_disabled=l.get('updates_disabled'),parameter_update_status='updates_disabled' if l.get('updates_disabled') else 'updates_reported',intrinsic_reward_sum=l.get('training_intrinsic_reward_sum'),intrinsic_reward_steps=l.get('intrinsic_reward_steps'),wall_seconds=cost.get('wall_s'),exact_source=str(p),provenance='E078_ORIGINAL_160_ACTION_VC33_3_SEEDS'))
cols=list(rows[0]);p=out/'e078_native_24_full_diagnostics.csv'
with p.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def m(a):return sum(float(x) for x in a)/len(a)
summary={}
for k in sorted({r['algo']+'-'+r['version'] for r in rows}):
 r=[v for v in rows if v['algo']+'-'+v['version']==k]
 summary[k]={'n_runs':len(r),'native_level_sum':sum(int(v['native_levels']) for v in r),'total_native_sdk_score':sum(float(v['native_sdk_score']) for v in r),'mean_unique_state_rate':m([v['unique_state_rate'] for v in r]),'mean_frame_change_rate':m([v['frame_change_rate'] for v in r]),'mean_gradient_steps':m([v['gradient_steps'] for v in r]),'mean_wall_seconds':m([v['wall_seconds'] for v in r]),'mean_intrinsic_reward_sum':m([v['intrinsic_reward_sum'] for v in r])}
(out/'e078_native_24_summary.json').write_text(json.dumps({'method':'source-original 160-action vc33 seeded trial; separate from E128 256-action coursework panel','summary':summary},indent=2))
assert len(rows)==24 and all(r['action_ceiling']==160 for r in rows)
print('E078_EXTRACTED',len(rows))
print('E078_SUMMARY',json.dumps(summary))
PY
