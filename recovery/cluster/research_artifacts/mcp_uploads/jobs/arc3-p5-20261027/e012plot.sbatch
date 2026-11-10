#!/bin/bash
#SBATCH --job-name=arc3-e012-plot
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/e012plot-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/e012plot-%j.err
set -euo pipefail
mkdir -p out/curves
python3 - <<'PY'
from pathlib import Path
import csv,json
src=Path('/home-mscluster/astrauss/arc_rl_final_e012/results/ABLATION_RESULTS.json')
data=json.loads(src.read_text())
s=data['summaries']
out=Path('out/curves')
rows=[]
for r in s:
 for a in (0,50,100,250,600):
  rows.append({'arm':r['id'],'charged_actions':a,'mean_native_levels':0 if a==0 else r[f'progress_by_{a}'],'n_game_seed_runs':r['n_game_runs'],'mean_parameter_delta_l2':r['parameter_delta_l2'],'mean_updates':r['updates'],'source':str(src)})
with (out/'e012_original_progress_50_100_250_600.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
W,H=900,530;left=100;right=35;top=40;bottom=100;maxy=.18
def tx(x):return left+x/600*(W-left-right)
def ty(y):return H-bottom-y/maxy*(H-top-bottom)
col=['#0066aa','#d56700','#26824c','#9b50a0']
lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',f'<rect width="{W}" height="{H}" fill="white"/>']
for x in (0,50,100,250,600):
 lines.extend([f'<line x1="{tx(x)}" y1="{top}" x2="{tx(x)}" y2="{H-bottom}" stroke="#e5e5e5"/>',f'<text x="{tx(x)}" y="{H-bottom+25}" text-anchor="middle" font-size="17">{x}</text>'])
for k in (0,.04,.08,.12,.16):
 lines.extend([f'<line x1="{left}" y1="{ty(k)}" x2="{W-right}" y2="{ty(k)}" stroke="#e5e5e5"/>',f'<text x="{left-15}" y="{ty(k)+6}" text-anchor="end" font-size="17">{k:.2f}</text>'])
for j,r in enumerate(s):
 vals=[(x,0 if x==0 else r[f'progress_by_{x}']) for x in (0,50,100,250,600)]
 points=' '.join(f'{tx(x):.1f},{ty(y):.1f}' for x,y in vals)
 lines.append(f'<polyline points="{points}" fill="none" stroke="{col[j]}" stroke-width="3"/>')
 for x,y in vals:lines.append(f'<circle cx="{tx(x)}" cy="{ty(y)}" r="5" fill="{col[j]}"/>')
 lines.append(f'<line x1="{120+410*(j%2)}" y1="{H-55+28*(j//2)}" x2="{160+410*(j%2)}" y2="{H-55+28*(j//2)}" stroke="{col[j]}" stroke-width="4"/>')
 lines.append(f'<text x="{167+410*(j%2)}" y="{H-49+28*(j//2)}" font-size="14">{r["id"]}</text>')
lines += [f'<text x="{(W+left-right)/2}" y="{H-120/2+14}" text-anchor="middle" font-size="18">Charged environment actions</text>',f'<text transform="translate(24,{H/2}) rotate(-90)" text-anchor="middle" font-size="18">Mean completed native levels / game-seed run</text>','<text x="100" y="26" font-size="19" font-weight="bold">E012 DQN development: recorded budget-indexed progress (75 runs/arm)</text>','</svg>']
(out/'e012_original_progress.svg').write_text('\n'.join(lines))
print('E012_CURVES_SAVED',len(rows),'rows',len(s),'arms')
print('SERIES',json.dumps({r['id']:[r[f'progress_by_{a}'] for a in [50,100,250,600]] for r in s}))
PY
