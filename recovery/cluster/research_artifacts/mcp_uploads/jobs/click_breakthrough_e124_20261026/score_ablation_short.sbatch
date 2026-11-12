#!/bin/bash
#SBATCH --job-name=e124abscore
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
R=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
M={p.name:json.loads(next(p.glob('*/metadata.json')).read_text())['baseline_actions'] for p in (R/'click_diversity_e121_20261026/runtime/environment_files').iterdir() if p.is_dir()}
B=R/'click_breakthrough_e124_20261026'
for arm in ('baseline','contingency','rarity_only','effect_only','random_bonus'):
 d=B/('results/seed76/baseline' if arm=='baseline' else 'ablation/seed76/'+arm)
 total=0.
 for game,h in M.items():
  s=json.loads((d/(game+'.json')).read_text())['summary']
  prev=0;v=0.
  for w in s['wins']:
   j=w['level'];steps=w['step']-prev;prev=w['step']
   v+=j*min(115.,100.*(h[j-1]/steps)**2)
  den=len(h)*(len(h)+1)/2
  total+=min(v/den,sum(range(1,s['levels_completed']+1))/den*100.)
 print('MEAN_SDK',arm,round(total/25,9),flush=True)
PY
