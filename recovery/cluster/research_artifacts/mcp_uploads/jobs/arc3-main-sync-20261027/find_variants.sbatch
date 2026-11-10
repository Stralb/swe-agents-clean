#!/bin/bash
#SBATCH --job-name=arc3-variant-lookup
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/variants-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027/variants-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-main-sync-20261027
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json,os,re
base=Path('/home-mscluster/astrauss')
roots=[base/'RL-ARC-AGI-3-Project',base/'arc_rl_final_e012',base/'e078_course_recovery',base/'arc_rl_mechanics_killtest']
terms=[r'ppo.?i2',r'ppo.?i1',r'dqn.?i2',r'dqn.?i1',r'foreground',r'novelty',r'intrinsic_reward',r'epsilon_stall',r'stall.?epsilon',r'old_log_prob',r'masked_fill',r'policy_ratio',r'update.*mask']
regex=re.compile('|'.join(terms),re.I)
out={'source_hits':[],'project_files':{}}
for root in roots:
 if not root.is_dir():continue
 count=0;listed=[]
 for cur,dirs,fs in os.walk(root):
  dirs[:]=[d for d in dirs if d not in {'.git','venv','.venv','node_modules','__pycache__','recordings','frames','runs','checkpoints','results','assets','logs','vendor','build'} and len(Path(cur).relative_to(root).parts)<5]
  for f in fs:
   p=Path(cur)/f
   if p.suffix.lower() not in {'.py','.json','.md','.sh','.slurm'}:continue
   try:
    size=p.stat().st_size
    if size>300000:continue
    txt=p.read_text(errors='replace')
   except OSError:continue
   count+=1
   rel=str(p.relative_to(root))
   if root.name=='arc_rl_final_e012':listed.append({'path':rel,'bytes':size})
   matches=[(i+1,line[:180]) for i,line in enumerate(txt.splitlines()) if regex.search(line)]
   if matches:
    out['source_hits'].append({'root':root.name,'path':rel,'match_count':len(matches),'sample':matches[:12]})
   if count>=1000:break
  if count>=1000:break
 out['project_files'][root.name]={'scanned':count,'files':listed[:100]}
out['source_hits'].sort(key=lambda r:(-r['match_count'],r['root'],r['path']))
Path('evidence/variant_source_search.json').write_text(json.dumps(out,indent=2))
print('SOURCE_HITS',len(out['source_hits']))
print('BEST',json.dumps(out['source_hits'][:22])[:15000])
print('E012_FILES',json.dumps(out['project_files'].get('arc_rl_final_e012')))
PY
