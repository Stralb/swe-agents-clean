#!/bin/bash
#SBATCH --job-name=arc3-curves
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/curves-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/curves-%j.err
set -euo pipefail
mkdir -p out/curves
python3 - <<'PY'
from pathlib import Path
from collections import Counter
import json,csv,re,os
base=Path('/home-mscluster/astrauss')
dest=Path('out/curves')
roots=sorted((base/'e078_course_recovery').glob('E078_native_vc33_160_seed*'))
meta={'source':'original E078 native records (not E128 4-game protocol)','records':[],'root_reports':{},'e012_files':{}}
records=[]
for root in roots:
 report=root/'E078_REPORT.json'
 if report.exists():
  x=json.loads(report.read_text())
  meta['root_reports'][root.name]=x
 for p in sorted(root.glob('*/record.json')):
  x=json.loads(p.read_text())
  ident=x.get('identity') or {}
  cfg=ident.get('config') or {}
  row={'path':str(p),'run_id':ident.get('run_id',''),'version':cfg.get('version',''),'algo':cfg.get('algo',''),'game':cfg.get('game',''),'seed':cfg.get('seed',''),'native_seed':cfg.get('env_seed',''),'budget':cfg.get('budget',''),'status':x.get('status'),'error':x.get('error'),'official_score':x.get('official_score'),'counters':x.get('counters'),'diagnostics':x.get('diagnostics'),'learner':x.get('learner'),'cost':x.get('cost'),'scorecard':x.get('scorecard')}
  records.append(row)
  meta['records'].append(row)
# E012 has separate 600-action experimental results, preserve as distinct source
for name in ['ABLATION_RESULTS.json','LOCK_IN.json']:
 p=base/'arc_rl_final_e012'/'results'/name
 if p.exists():
  data=json.loads(p.read_text())
  meta['e012_files'][name]={'source':str(p),'value':data}
for name in ['REPORT.md','EXPERIMENTS.md']:
 p=base/'arc_rl_final_e012'/'results'/name if name=='REPORT.md' else base/'arc_rl_final_e012'/name
 if p.exists():
  text=p.read_text(errors='replace')
  meta['e012_files'][name]={'source':str(p),'size':len(text),'lines_with_budget':[(i+1,v[:220]) for i,v in enumerate(text.splitlines()) if 'progress' in v.lower() or 'by_50' in v.lower() or 'curve' in v.lower()][:70]}
dest.joinpath('e078_native_records_and_e012_controls.json').write_text(json.dumps(meta,indent=2,default=str))
columns=['run_id','version','algo','game','seed','native_seed','budget','status','score','levels','steps','updates','grad_steps','first_reward_step','wall_seconds','source']
with (dest/'e078_all_24_native_records.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
 for r in records:
  c=r['counters'] if isinstance(r['counters'],dict) else {}
  d=r['diagnostics'] if isinstance(r['diagnostics'],dict) else {}
  l=r['learner'] if isinstance(r['learner'],dict) else {}
  sc=r['scorecard'] if isinstance(r['scorecard'],dict) else {}
  cost=r['cost'] if isinstance(r['cost'],dict) else {}
  score=r['official_score']
  if isinstance(score,dict): score=score.get('score',score.get('value',''))
  row=dict(run_id=r['run_id'],version=r['version'],algo=r['algo'],game=r['game'],seed=r['seed'],native_seed=r['native_seed'],budget=r['budget'],status=r['status'],score=score,levels=sc.get('completed_levels',sc.get('levels','')),steps=c.get('actions',c.get('sdk_calls','')),updates=l.get('updates',l.get('gradient_updates','')),grad_steps=l.get('gradient_steps',''),first_reward_step=sc.get('first_reward_step',d.get('first_reward_step','')),wall_seconds=cost.get('elapsed_seconds',cost.get('wall_seconds','')),source=r['path'])
  w.writerow(row)
print('E078_RUNS',len(records),'ROOTS',len(roots))
print('E078_FIRST_KEYS',json.dumps({k:v for k,v in records[0].items() if k not in ['path','run_id']},default=str)[:10000] if records else '{}')
print('E012_ABLATION_KEYS',json.dumps({k:list(v.get('value',{})) if isinstance(v.get('value'),dict) else [] for k,v in meta['e012_files'].items() if k.endswith('.json')}))
print('E012_EXCERPTS',json.dumps({k:v.get('lines_with_budget',[])[:12] for k,v in meta['e012_files'].items() if k.endswith('.md')}))
print('SAVED',str(dest.resolve()))
PY
