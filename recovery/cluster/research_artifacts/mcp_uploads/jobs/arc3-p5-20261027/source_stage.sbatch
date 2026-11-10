#!/bin/bash
#SBATCH --job-name=arc3-srcstage
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:02:00
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/stage-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3-p5-20261027/logs/stage-%j.err
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import os,re,hashlib,json,shutil,ast
base=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project')
dst=Path('out/cluster_neural_source_20261027')
dirs=['src','tests','configs']
patterns={
 'src':['*.py','dqn_v1/*.py'],
 'tests':['test_dqn*.py','test_random_agent.py','test_core.py','test_ppo*.py','test_baseline*.py','conftest.py'],
 'configs':['*.json']
}
chosen=[]
for folder in dirs:
 for pat in patterns[folder]:
  for p in sorted((base/folder).glob(pat)):
   if p.is_file() and p.stat().st_size<80000:
    chosen.append(p)
for rel in ['README.md','requirements.txt','run_v0_v1_smoke.slurm','scripts/compare_dqn_baselines.sh','kaggle/my_agent.py','kaggle/learner_agent.py']:
 p=base/rel
 if p.is_file() and p.stat().st_size<50000:chosen.append(p)
def matchedconfig(p):
 l=p.name.lower()
 return l in ['splits.json'] or 'baseline' in l or 'dqn' in l or 'ppo' in l or 'e013' in l or 'e014' in l
chosen=[x for x in chosen if not str(x.relative_to(base)).startswith('configs/') or matchedconfig(x)]
data=[];duplicates=set()
for p in chosen:
 rel=p.relative_to(base)
 if str(rel) in duplicates:continue
 duplicates.add(str(rel))
 content=p.read_bytes()
 dstpath=dst/rel
 dstpath.parent.mkdir(parents=True,exist_ok=True);dstpath.write_bytes(content)
 record={'file':str(rel),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
 if p.suffix=='.py':
  txt=content.decode('utf8','replace')
  try:
   tree=ast.parse(txt)
   record['imports']=sorted(set((n.module or '') if isinstance(n,ast.ImportFrom) else ','.join(y.name for y in n.names) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))))
   record['functions']=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
   record['has_gradient']=bool(re.search('optimizer\\.step\\(|backward\\(|optim\\.step\\(',txt))
   record['mask_terms']=len(re.findall('masked_fill|log_prob|Categorical|mask|clip_ratio|ratio',txt))
  except SyntaxError as e:record['syntax_error']=str(e)
 data.append(record)
result={'project_root':str(base),'staged_dir':str(dst.resolve()),'files':data}
(dst/'SOURCE_SHA256_MANIFEST.json').write_text(json.dumps(result,indent=2))
print('STAGED_FILES',len(data),'TOTAL_BYTES',sum(z['bytes'] for z in data))
for d in data:
 if d['file'].startswith(('src/','tests/')):print('SOURCE',d['file'],d['bytes'],'IMPORTS',d.get('imports',[]),'GRAD',d.get('has_gradient'),'MASKTERMS',d.get('mask_terms'))
print('TESTS', [d['file'] for d in data if d['file'].startswith('tests/')])
print('CONFIGS', [d['file'] for d in data if d['file'].startswith('configs/')])
PY