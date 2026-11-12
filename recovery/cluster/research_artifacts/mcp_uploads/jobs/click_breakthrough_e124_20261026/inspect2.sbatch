#!/bin/bash
#SBATCH --job-name=e124inspect2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
s=p.read_text().splitlines()
for a,b in ((280,407),(14373,14443),(14585,14629)):
 print('=== SOURCE LINES',a,b,'===')
 for i in range(a-1,b):
  print(str(i+1)+': '+s[i][:220])
PY