#!/bin/bash
#SBATCH --job-name=arc3-inspect
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/inspect-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/inspect-%j.err
set -euo pipefail
python3 - <<'PY'
import json,os
from pathlib import Path
b=Path('/home-mscluster/astrauss')
all_dirs=sorted(x.name for x in b.iterdir() if x.is_dir() and ('arc' in x.name.lower() or 'rl' in x.name.lower()))
out={'dirs':all_dirs,'projects':{}}
for name in ['e078_course_recovery','arc_rl_final_e012','arc_rl_persistence_e007']:
 root=b/name
 if not root.exists():continue
 files=[]
 for d,sub,items in os.walk(root):
  sub[:]=[x for x in sub if x not in {'.git','venv','.venv','runs','frames','recordings','node_modules'}]
  if len(Path(d).relative_to(root).parts)>=4:sub[:]=[]
  for f in items:
   path=Path(d)/f
   if path.suffix.lower() not in {'.py','.ipynb','.md','.json','.sbatch','.yaml','.yml','.toml','.pt','.pth'}:continue
   if len(files)>=1200:break
   files.append(str(path.relative_to(root)))
 out['projects'][name]={'count':len(files),'source':sorted(files)}
Path('out/source_inventory.json').write_text(json.dumps(out,indent=2))
print('SUCCESS',json.dumps({k:{'count':v['count'],'source':v['source'][:20]} for k,v in out['projects'].items()}))
print('DIRS',json.dumps(all_dirs))
PY
