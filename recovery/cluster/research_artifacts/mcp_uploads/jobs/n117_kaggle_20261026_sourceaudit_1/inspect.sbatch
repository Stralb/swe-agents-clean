#!/bin/bash
#SBATCH --job-name=arc3n117sourcecheck
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=00:06:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import ast,hashlib,json,gzip,bz2,lzma,zlib
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
p=root/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py'
data=p.read_bytes()
print('SOURCE_SHA256',hashlib.sha256(data).hexdigest())
print('SOURCE_BYTES',len(data))
for label,f in [('zlib9',lambda x:zlib.compress(x,9)),('gzip9',lambda x:gzip.compress(x,compresslevel=9)),('bz2',lambda x:bz2.compress(x,compresslevel=9)),('xz6',lambda x:lzma.compress(x,preset=6))]:
    try:
        c=f(data)
        print('COMPRESSION',label,len(c),'estimated_base64_size',((len(c)+2)//3)*4)
    except Exception as e:
        print('COMPRESSION_EXCEPTION',label,type(e).__name__)
tree=ast.parse(data.decode(),filename=str(p))
print('IMPORTS',sorted(set((x.module if isinstance(x,ast.ImportFrom) else ','.join(a.name for a in x.names)) or '' for x in ast.walk(tree) if isinstance(x,(ast.Import,ast.ImportFrom)))))
print('CLASSES',[(x.name,[y.id for y in x.bases if isinstance(y,ast.Name)]) for x in tree.body if isinstance(x,ast.ClassDef)])
for x in tree.body:
    if isinstance(x,ast.ClassDef) and x.name=='MyAgent':
        print('MYAGENT_METHODS',[(a.name,a.lineno) for a in x.body if isinstance(a,(ast.FunctionDef,ast.AsyncFunctionDef))])
        print('MYAGENT_MAX_ACTIONS',[(a.lineno,ast.unparse(a)[:120]) for a in x.body if isinstance(a,(ast.Assign,ast.AnnAssign)) and 'MAX_ACTIONS' in ast.unparse(a)])
nb=json.loads((root/'n117_kaggle_20261026_v2/kernel/submission.ipynb').read_text())
print('NB_CELL_TYPES',[(i,c['cell_type'],len(''.join(c.get('source',[])))) for i,c in enumerate(nb['cells'])])
print('GATEWAY_CELL', ''.join(nb['cells'][3]['source'])[:3200])
PY
