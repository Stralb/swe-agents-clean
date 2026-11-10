#!/bin/bash
#SBATCH --job-name=e127-trace-schema
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
python3 - <<'PY'
import json
from pathlib import Path
from zipfile import ZipFile
zpath=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_integrated_audit_e127_20261026/analysis/E124_E125_E126_FULL_NATIVE_EVIDENCE.zip')
with ZipFile(zpath) as z:
    names=z.namelist()
    for needle in ['click_hybrid_e126_20261026/results/seed76/hybrid_trained/s5i5.json',
                   'click_hybrid_e126_20261026/results/seed76/baseline/s5i5.json',
                   'click_breakthrough_e124_20261026/results/seed76/contingency/lf52.json']:
        matches=[n for n in names if needle in n]
        print('MATCH',needle,len(matches))
        if not matches: continue
        d=json.loads(z.read(matches[0]))
        print('ROOT_KEYS',list(d.keys()))
        for k,v in d.items():
            if isinstance(v,list):
                print('LIST',k,'len',len(v),'firsttype',type(v[0]).__name__ if v else '-')
                if v and isinstance(v[0],dict):
                    print('FIRST_DICT_KEYS',list(v[0].keys()))
                    print('FIRST_SCALARS',{a:val for a,val in v[0].items() if isinstance(val,(int,float,str,bool,type(None)))})
                    if len(v)>1 and isinstance(v[1],dict):
                        print('SECOND_SCALARS',{a:val for a,val in v[1].items() if isinstance(val,(int,float,str,bool,type(None)))})
            elif isinstance(v,dict):
                print('DICT',k,list(v.keys())[:35])
            elif isinstance(v,(str,int,float,bool,type(None))):
                print('SCALAR',k,repr(v)[:250])
print('TRACE_SCHEMA_READONLY_DONE')
PY