#!/bin/bash
#SBATCH --job-name=e127-108-run-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
from collections import defaultdict
import csv,json,statistics
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027/records')
out=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_e127_mechanism_audit_20261027/analysis')
out.mkdir(exist_ok=True,parents=True)
rows=[]
for p in sorted(root.glob('*.json')):
    d=json.loads(p.read_text())
    s=d['study'];L=d['learner'];sc=d.get('official_score') or {};cn=d['counters']
    rows.append(dict(algorithm=s['algorithm'],arm=s['arm'],game=s['game'],seed=s['policy_seed'],
         native_seed=s['native_seed'],charged_actions=cn['scorer_actions'],
         native_levels=sc.get('levels_completed',''),local_sdk_score=sc.get('score',''),
         gradient_steps=L.get('gradient_steps',0),intrinsic_bonus=L.get('intrinsic_bonus',0),
         masked_decisions=L.get('masked_states',0),rescue_decisions=L.get('rescue_decisions',0),
         frame_change_rate=d.get('diagnostics',{}).get('frame_change_rate',''),
         wall_seconds=d['cost']['wall_s'],error=d['error'] or '',
         original_record=p.name))
assert len(rows)==108
with (out/'original_108_run_ledger.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]))
    w.writeheader();w.writerows(rows)
grp=defaultdict(list)
for x in rows:grp[(x['algorithm'],x['arm'])].append(x)
print('AUDIT_108_ORIGINALS_SUMMARY')
for (alg,arm),z in sorted(grp.items()):
    levels=sum(int(x['native_levels']) for x in z)
    score=sum(float(x['local_sdk_score']) for x in z)/len(z)
    bonus=sum(float(x['intrinsic_bonus']) for x in z)
    masks=sum(int(x['masked_decisions']) for x in z)
    rescues=sum(int(x['rescue_decisions']) for x in z)
    grads=sum(int(x['gradient_steps']) for x in z)
    print(alg,arm,'n',len(z),'levels',levels,'mean_sdk',round(score,8),
      'gradients',grads,'intrinsic_bonus_sum',round(bonus,4),
      'masked_states',masks,'rescue_choices',rescues,'errors',sum(bool(x['error']) for x in z),flush=True)
print('SUM_NONZERO_RECORDS')
for x in rows:
    if int(x['native_levels'])>0:
        print(x['original_record'],x['native_levels'],x['local_sdk_score'],flush=True)
print('E127_READONLY_108_RECORDS_COMPLETE',flush=True)
PY