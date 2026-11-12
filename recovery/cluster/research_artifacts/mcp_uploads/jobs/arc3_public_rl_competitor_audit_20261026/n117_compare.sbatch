#!/bin/bash
#SBATCH --job-name=arc3n117compare
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
python3 - <<'PY'
import ast,re
from pathlib import Path
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
s=p.read_text()
t=ast.parse(s)
for c in t.body:
 if isinstance(c,ast.ClassDef) and c.name in ('PortableAgentCore','PretrainedPUCTCore','HypothesisMemory'):
  print('\n===CLASS',c.name,c.lineno,'===',flush=True)
  for m in c.body:
   if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)):
    nm=m.name
    if re.search('choose|click|cand|action|rank|effect|score|grid|memory|plan|probe|target|legal',nm,re.I):
     print('METHOD',nm,m.lineno,m.end_lineno,flush=True)
     if re.search('click|cand|rank|choose',nm,re.I):
      lines=s.splitlines()
      for i in range(m.lineno-1,min(m.end_lineno,m.lineno+24)):
       print(i+1,lines[i][:155],flush=True)
print('DONE')
PY