#!/bin/bash
#SBATCH --job-name=e122inspect
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
python3 - <<'PY'
import ast,hashlib
from pathlib import Path
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
code=p.read_text()
lines=code.splitlines()
t=ast.parse(code)
print('SOURCE_SHA',hashlib.sha256(code.encode()).hexdigest())
for cls in t.body:
 if not isinstance(cls,ast.ClassDef) or cls.name not in ('BeliefMemory','BeliefStore','PortableAgentCore','PretrainedPUCTCore','AuditedCrossLevelCore'):continue
 print('===',cls.name,cls.lineno,cls.end_lineno)
 for fn in cls.body:
  if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name in ('candidates','node','puct_probabilities','choose','observe','_rank_ties','_expand','_memory_bonus','describe','_stat','_stage','_observe_q'):
   print('METHOD',fn.name,fn.lineno,fn.end_lineno)
   if cls.name in ('PortableAgentCore','PretrainedPUCTCore') or fn.name in ('_stat','_memory_bonus'):
    for i in range(fn.lineno-1,min(fn.end_lineno,fn.lineno+95)): print(str(i+1)+' '+lines[i][:230])
    print('END_METHOD')
print('RELATED_CLASSES')
for cls in t.body:
 if isinstance(cls,ast.ClassDef) and any(k in cls.name.lower() for k in ('belief','descriptor','effect')):
  print(cls.name,cls.lineno,cls.end_lineno)
  for fn in cls.body:
   if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):print(fn.name,fn.lineno)
PY