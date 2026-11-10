#!/bin/bash
#SBATCH --job-name=arc3n117audit2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
python3 - <<'PY'
import ast
from pathlib import Path
p=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_dataset1/private_dataset/my_agent.py')
tree=ast.parse(p.read_text())
print('RECORDER_COUNT',sum(isinstance(n,ast.Attribute) and n.attr=='recorder' for n in ast.walk(tree)))
print('MYAGENT_COUNT',sum(isinstance(n,ast.ClassDef) and n.name=='MyAgent' for n in tree.body))
PY