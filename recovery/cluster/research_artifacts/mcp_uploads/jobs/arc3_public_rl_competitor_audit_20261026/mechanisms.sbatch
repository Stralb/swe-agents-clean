#!/bin/bash
#SBATCH --job-name=arc3ashmechanisms
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
base=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3_public_rl_survey_20261026/source_archive')
segments={'ashvinsingh__ash-s-arc-agi-3-agent':[(175,242),(278,409),(442,579)],'projectforty2__forge-arc-agi-3-agent':[(604,720),(715,803)],'nihilisticneuralnet__0-46-arc-agi-3-persistent-memory-bfs-arc-solver':[(1225,1280),(1630,1705)]}
for name,spans in segments.items():
    p=next((base/name).glob('*.ipynb'))
    nb=json.loads(p.read_text())
    lines='\n'.join(''.join(c.get('source',[])) for c in nb.get('cells',[])).splitlines()
    print('====',name,'====',flush=True)
    for a,b in spans:
        print('----',a,b,'----')
        for i in range(a-1,min(b,len(lines))):
            print(str(i+1)+':'+lines[i][:180])
PY