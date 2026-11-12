#!/bin/bash
#SBATCH --job-name=arc3-core
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/core-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/core-%j.err
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import os,json
base=Path('/home-mscluster/astrauss')
names=['RL-ARC-AGI-3-Project','arc26','rl_lab3_run','E019_HIERARCHICAL_OPTIONS_PATCH','arc_rl_backbone_e008','arc_rl_exploration_e009']
ext={'.py','.ipynb','.json','.md','.sbatch','.yaml','.yml','.toml','.csv','.pt','.pth','.sh'}
skip={'.git','venv','.venv','__pycache__','node_modules','frames','video','recordings','.mypy_cache','runs'}
out={'projects':{},'ranked':[]}
for name in names:
 root=base/name
 if not root.is_dir(): continue
 docs=[]
 for current,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if d not in skip]
  rel=Path(current).relative_to(root)
  if len(rel.parts)>5:dirs[:]=[];continue
  for f in files:
   path=Path(current)/f
   if path.suffix.lower() not in ext:continue
   if len(docs)>=3000:break
   try:size=path.stat().st_size
   except OSError:continue
   if size>50000000:continue
   name_l=str(path.relative_to(root)).lower()
   score=sum(k in name_l for k in ['dqn','ppo','train','eval','runner','course','agent','checkpoint','rollout','protocol','config','reward','results'])
   rec={'path':str(path.relative_to(root)),'bytes':size,'score':score}
   docs.append(rec)
   if score>=2:out['ranked'].append({'project':name,**rec})
 out['projects'][name]={'count':len(docs),'paths':docs[:350]}
out['ranked'].sort(key=lambda z:(-z['score'],z['project'],z['path']))
Path('out/core_inventory.json').write_text(json.dumps(out,indent=2))
print('ARC3_CORE_SCAN_OK')
print('SUMMARY',json.dumps({k:v['count'] for k,v in out['projects'].items()}))
print('PRIORITY',json.dumps(out['ranked'][:45]))
PY
