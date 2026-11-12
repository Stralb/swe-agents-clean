#!/bin/bash
#SBATCH --job-name=e122beliefaudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
set -euo pipefail
python3 - <<'PY'
import ast
from pathlib import Path
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
lines=p.read_text().splitlines()
tr=ast.parse('\n'.join(lines))
for cl in tr.body:
 if not isinstance(cl,ast.ClassDef):continue
 methods={m.name for m in cl.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef))}
 if ('describe' in methods or ('rank' in methods and 'observe' in methods) or cl.name=='AuditedCrossLevelCore'):
  print('CLASS',cl.name,cl.lineno,cl.end_lineno)
  for fn in cl.body:
   if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name in ('__init__','describe','rank','observe','choose','_memory_bonus'):
    print('METHOD',fn.name,fn.lineno,fn.end_lineno)
    if cl.name=='AuditedCrossLevelCore' and fn.name=='choose': print('SKIP LONG CHOOSE');continue
    for i in range(fn.lineno-1,min(fn.end_lineno,fn.lineno+75)):print(str(i+1)+': '+lines[i][:210])
PY