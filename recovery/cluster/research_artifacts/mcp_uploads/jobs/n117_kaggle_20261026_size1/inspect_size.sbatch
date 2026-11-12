#!/bin/bash
#SBATCH --job-name=arc3n117size
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:04:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json,zlib,lzma,bz2
p=Path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/kaggle_kernel/submission.ipynb")
raw=p.read_bytes()
n=json.loads(raw)
print("raw_bytes",len(raw))
print("cells",len(n['cells']))
for i,c in enumerate(n['cells']):
 s=''.join(c.get('source',[]))
 print("cell",i,"type",c.get('cell_type'),"source_size",len(s),"first120",repr(s[:120]),"outputs_bytes",len(json.dumps(c.get('outputs',[]))))
 if len(s)>400000:
  print("big_cell_compressed",len(zlib.compress(s.encode(),9)),len(lzma.compress(s.encode(),preset=9)),len(bz2.compress(s.encode(),9)))
for c in n['cells']:
 c.pop('outputs',None)
 c.pop('execution_count',None)
 c['metadata']={}
n['metadata']={}
compact=json.dumps(n,separators=(',',':')).encode()
print("compact_bytes",len(compact))
code='\n\n'.join(''.join(c.get('source',[])) for c in n['cells'] if c['cell_type']=='code')
print("code_bytes",len(code.encode()))
print("code_zlib9",len(zlib.compress(code.encode(),9)))
print("code_lzma9",len(lzma.compress(code.encode(),preset=9)))
print("code_bz29",len(bz2.compress(code.encode(),9)))
PY