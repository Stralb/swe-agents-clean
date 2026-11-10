#!/bin/bash
#SBATCH --job-name=e124introspection
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
lines=p.read_text().splitlines()
root=ast.parse('\n'.join(lines))
print('SHA',hashlib.sha256(p.read_bytes()).hexdigest())
for cl in root.body:
 if isinstance(cl,ast.ClassDef) and cl.name in ('PortableAgentCore','AuditedCrossLevelCore','BeliefMemory','HypothesisMemory','BeliefStore','PretrainedPUCTCore'):
  print('CLASS',cl.name,cl.lineno,cl.end_lineno)
  for fn in cl.body:
   if isinstance(fn,ast.FunctionDef):
    print('METHOD',fn.name,fn.lineno,fn.end_lineno)
    if (cl.name in ('PortableAgentCore','AuditedCrossLevelCore') and fn.name in ('__init__','start_level','candidates','node','choose','observe','_rank_ties','_memory_bonus','report','prior_logits','_combine')) or ('Belief' in cl.name and fn.name in ('rank','observe','__init__')):
     lim=min(fn.end_lineno,fn.lineno+110)
     for i in range(fn.lineno-1,lim):
      print(str(i+1)+': '+lines[i][:205])
     print('FIN_METHOD')
PY