#!/bin/bash
#SBATCH --job-name=e121inventory
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
r=Path('/home-mscluster/astrauss/research_artifacts')
for path in (r,r/'mcp_uploads/jobs',Path('/home-mscluster/astrauss')):
  a=sorted(x.name for x in path.iterdir())
  matches=[x for x in a if any(k in x.lower() for k in ('arc','n100','n117','n114','e121','rl_','e074','20261026','native','benchmark','repo'))]
  print('DIR',path,'COUNT',len(a),'MATCHES',len(matches),flush=True)
  for x in matches[:250]:print(x,flush=True)
  if len(matches)>250:print('... remaining',len(matches)-250)
PY